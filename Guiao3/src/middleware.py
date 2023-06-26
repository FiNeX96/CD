"""Middleware to communicate with PubSub Message Broker."""
from collections.abc import Callable
from enum import Enum
from queue import LifoQueue, Empty
from typing import Any,Tuple
import socket
import json,pickle
import xml.etree.ElementTree as xml


class MiddlewareType(Enum):
    """Middleware Type."""

    CONSUMER = 1
    PRODUCER = 2


class Queue:
    """Representation of Queue interface for both Consumers and Producers."""

    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        """Create Queue."""
        self.socket_type = _type
        self.topic = topic
        self.broker_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = "localhost"
        self.port = 5000
        self.broker_conn.connect((self.host,self.port)) # connect to broker socket
        #print ("Queue sucessfully connected to broker")
        
        
    def push(self, value):
        """Sends data to broker."""
        msg_header = len(value).to_bytes(2, byteorder="big")
        #print (msg_header)
        #print (value)
        self.broker_conn.send(msg_header + value)
        
        

    def pull(self) -> Tuple[str, Any]:
        """Receives (topic, data) from broker.
        Should BLOCK the consumer!"""
        msg_header = int.from_bytes(self.broker_conn.recv(2), byteorder="big")
        if msg_header == 0:
            return
        else:
            msg = self.broker_conn.recv(msg_header)
        return msg
        

    def list_topics(self, callback: Callable):
        """Lists all topics available in the broker."""
        self.push({"method": "list"}) # ask broker for list of topics
        
        

    def cancel(self):
        """Cancel subscription."""
        self.push({"method": "unsubscribe", "topic": self.topic})
        
    def send_to_broker(self, topic, value):
        """Send message to broker."""
        msg = {"method": "publish", "topic": topic, "data": value}
        self.broker_conn.send(msg)


class JSONQueue(Queue):
    """Queue implementation with JSON based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        
        
        super().__init__(topic, _type)
        serializer_msg = {"method": "ser_register", "serializer": "JSON"}
        super().push(pickle.dumps(serializer_msg))
        if _type == MiddlewareType.CONSUMER:
            subscribe_msg = {"method": "subscribe", "topic": topic}
            super().push(json.dumps(subscribe_msg).encode("utf-8"))
            
    def push(self, value):
        """Sends message to broker."""
        message_dic = {"method": "publish", "topic": self.topic, "message": value}
        super().push(json.dumps(message_dic).encode("utf-8"))
        
    def pull(self):
        msg = json.loads(super().pull())
        return msg["topic"], msg["message"]
        
    
class XMLQueue(Queue):
    """Queue implementation with XML based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        
        super().__init__(topic, _type)
        serializer_msg = {"method": "ser_register", "serializer": "XML"}
        super().push(pickle.dumps(serializer_msg))
        
        if _type == MiddlewareType.CONSUMER:
            xml_root = xml.Element("root")
            # set root to subscribe and value to topic
            xml.SubElement(xml_root, "method").set("value","subscribe")
            xml.SubElement(xml_root, "method").set("value",str(topic))
            super().push(xml.tostring(xml_root))
            
            
            
    def push(self, value):
        """Sends message to broker."""
        
        #setup the xml tree object 
        
        xml_root = xml.Element("root")
        xml.SubElement(xml_root, "method").set("value","publish")
        xml.SubElement(xml_root, "topic").set("value",self.topic)
        xml.SubElement(xml_root, "message").set("value",str(value))
        
        # send the xml tree object stringified to the broker
        super().push(xml.tostring(xml_root))
        print (" XML MESSAGE PUSHED TO BROKER")
        
    def pull(self):
        msg = super().pull()
        msg_tree = xml.fromstring(msg)
        xml_dic = {}
        for node in msg_tree:
            xml_dic[node.tag] = node.attrib["value"]
        return xml_dic["topic"], xml_dic["message"]


class PickleQueue(Queue):
    """Queue implementation with Pickle based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)

        serializer_msg = {"method": "ser_register", "serializer": "PICKLE"}
        super().push(pickle.dumps(serializer_msg))
        if _type == MiddlewareType.CONSUMER:
            subscribe_msg = {"method": "subscribe", "topic": topic}
            super().push(pickle.dumps(subscribe_msg))
            
    def push(self, value):
        """Sends message to broker."""
        message_dic = {"method": "publish", "topic": self.topic, "message": value}
        super().push(pickle.dumps(message_dic))
        #print ("Producer pushed a message" + str(value) + " to topic " + self.topic)
        
    def pull(self):
        msg = pickle.loads(super().pull())
        #print ("Consumer pulled a message" + msg["message"] + " from topic " + msg["topic"])
        return msg["topic"], msg["message"]
