"""Message Broker"""
import enum
import socket
from typing import Dict, List, Any, Tuple
import selectors
import json
import xml.etree.ElementTree as xml
import pickle


class Serializer(enum.Enum):
    """Possible message serializers."""

    JSON = 0
    XML = 1
    PICKLE = 2


class Broker:
    """Implementation of a PubSub Message Broker."""

    def __init__(self):
        """Initialize broker."""
        self.topic_subscribers = {}
        # method: Dict[str, Tuple(socket,serializer)]
        self.topics_lastmsg = {}  # method: Dict[str, str]
        self.serializers = {}  # method: Dict[socket.socket, Serializer]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.canceled = False
        self._host = "localhost"
        self._port = 5000
        self.sel = selectors.DefaultSelector()
        self.socket.bind((self._host, self._port))
        self.socket.listen(50)
        self.sel.register(self.socket, selectors.EVENT_READ, self.accept)

    def accept(self, sock, mask):
        conn, addr = sock.accept()
        self.sel.register(conn, selectors.EVENT_READ, self.read)
        #print ("New connection from ", addr)

    def msg_deserializer(self, msg, serializer):
        if serializer == Serializer.JSON:
            message = json.loads(msg)
        elif serializer == Serializer.XML:
            message_xml = xml.fromstring(msg)
            message = {}
            for node in message_xml:
                message[node.tag] = node.attrib["value"]
            #print("XML Message Received: ", message)
        elif serializer == Serializer.PICKLE:  # should be pickle
            message = pickle.loads(msg)
        else:
            return
        return message
        #print (message)

    def read(self, conn, mask):
        msg_header = int.from_bytes(conn.recv(2), byteorder="big")
        if msg_header:
            #print ("Broker received message header with length:", msg_header)
            msg = conn.recv(msg_header)
            # print(conn)
            if conn in self.serializers.keys():
                message = self.msg_deserializer(msg, self.serializers[conn])
            else:
                #print ("No serializer registered for this socket" , conn)
                message = self.msg_deserializer(msg, Serializer.PICKLE)
        else:  # dont read empty messages
            for topic in self.topic_subscribers.keys():
                self.unsubscribe(topic, conn)
            self.sel.unregister(conn)
            conn.close()
            #print("Client disconnected")
            return

        #print ("Broker received message: ", message)

        #print("Message method: ", message["method"])

        if message["method"] == "ser_register":
            # message to register serializer
            serializer = message["serializer"]
            if serializer == "JSON":
                self.serializers[conn] = Serializer.JSON
            elif serializer == "XML":
                self.serializers[conn] = Serializer.XML
            elif serializer == "PICKLE":
                self.serializers[conn] = Serializer.PICKLE
            else:
                print("Invalid serializer")
            #print("New socket registered: ", serializer)

        if message["method"] == "subscribe":
            self.subscribe(message["topic"], conn, self.serializers[conn])

        if message["method"] == "unsubscribe":
            self.unsubscribe(message["topic"], conn)

        if message["method"] == "last_message":
            print(message["message"])

        if message["method"] == "publish":
            topico = message["topic"]
            #print ("Subscribers do topico ", topico , "-> ", sock_address)

            #print("Publishing message to topic: ", topico)
            # save last message to topic
            self.topics_lastmsg[topico] = message["message"]
            
            if topico not in self.topic_subscribers.keys():
                self.topic_subscribers[topico] = []

            
            for subscriber in self.topic_subscribers[topico]:
                sub_address = subscriber[0]
                sub_format = subscriber[1]
                msg_to_send = {
                "method": "publish", "topic": message["topic"], "message": message["message"]}
                self.send(sub_address, msg_to_send, sub_format)

            for subtopic in self.topic_subscribers.keys():  # mandar para os subscribers de subtopicos tambem
                if subtopic.startswith(topico+"/"):
                    for subscriber in self.topic_subscribers[topico]:
                        sub_address = subscriber[0]
                        sub_format = subscriber[1]
                        msg_to_send = {
                            "method": "publish", "subtopic": subtopic, "message": message["message"]}
                        self.send(sub_address, msg_to_send, sub_format)
           

        if message["method"] == "list":
            topics = self.list_topics()
            self.send(conn, {"method": "list", "topics": topics},
                      self.serializers[conn])

    def send(self, conn, msg, serializer):
        """Send a message to a connection."""
        if serializer == Serializer.JSON:
            send_msg = json.dumps(msg).encode("utf-8")
        elif serializer == Serializer.XML:
            xml_root = xml.Element("root")
            for key in msg.keys():
                # create a new XML element for each key-value pair
                xml.SubElement(xml_root, str(key)).set("value", str(msg[key]))
                send_msg = xml.tostring(xml_root)
        elif serializer == Serializer.PICKLE:
            send_msg = pickle.dumps(msg)
        else:
            print("Invalid serializer")
        #print(msg, "decoded with", serializer)
        msg_header = len(send_msg).to_bytes(2, byteorder="big")
        conn.send(msg_header + send_msg)

    def list_topics(self) -> List[str]:
        """Returns a list of strings containing all topics containing values."""
        # values = mensagens
        # não é preciso criar outra lista, esta ja tem todos os topicos com mensagens (values)
        return list(self.topic_subscribers.keys())

    def get_topic(self, topic):
        """Returns the currently stored value in topic."""
        if topic not in self.topics_lastmsg.keys():
            return None
        return self.topics_lastmsg[topic]

    def put_topic(self, topic, value):
        """Store in topic the value."""
        self.topics_lastmsg[topic] = value
        self.topic_subscribers[topic] = []

    def list_subscriptions(self, topic: str) -> List[Tuple[socket.socket, Serializer]]:
        """Provide list of subscribers to a given topic."""
        #print ("List of subscribers to topic: ", topic)
        #print (self.topic_subscribers[topic])
        return self.topic_subscribers[topic]

    def subscribe(self, topic: str, address: socket.socket, _format: Serializer = None):
        """Subscribe to topic by client in address."""
        if topic not in self.topic_subscribers:
            self.topic_subscribers[topic] = []
        self.topic_subscribers[topic].append((address, _format))
        #print("New subscriber to topic: ", topic,
              #" -> ", address, " with format: ", _format)
        # send last message
        if topic not in self.topics_lastmsg.keys():
            return
        if self.topics_lastmsg[topic] is None:
            return
        self.send(address, {"method": "last_message", "topic": topic,
                  "message": self.topics_lastmsg[topic]}, _format)
        #print("Last message sent to subscriber: ", self.topics_lastmsg[topic])

    def unsubscribe(self, topic, address):
        """Unsubscribe to topic by client in address."""
        for (endereco, format) in self.topic_subscribers[topic]:
            if endereco == address:
                self.topic_subscribers[topic].remove((address, format))
                #print("Unsubscribed from topic: ", topic)
                return

    def run(self):
        """Run until canceled."""
        while not self.canceled:
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
