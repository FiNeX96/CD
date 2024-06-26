"""CD Chat server program."""
import logging
import socket
import selectors

from .protocol import CDProto, CDProtoBadFormat 

logging.basicConfig(filename="server.log", level=logging.DEBUG, filemode="w")


class Server:
    """Chat Server process."""
    
    def __init__(self):
        """Initializes chat server."""
        self.sel = selectors.DefaultSelector()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # reuse address
        self.protocol = CDProto
        self.socket.bind(("localhost", 9876))
        self.socket.listen(10) # 10 connections, its enough
        #self.socket.setblocking(False) # it doesnt work for mock socket 
        self.sel.register(self.socket, selectors.EVENT_READ,self.accept)
        self.channels = {} # channel name : [connections]
        #print("Server started")
        
    def accept(self,sock,mask):
        conn, addr = sock.accept()  # Should be ready
        #print('accepted', conn, 'from', addr)
        #conn.setblocking(False)
        self.sel.register(conn, selectors.EVENT_READ, self.read_server)
        self.channels[conn] = ["default_channel"] # create list of channels for the client
        #print(self.channels)
        #print(self.channels[conn][1])
        #exit()
        #print("-- Listening for client input --")  
        #self.clients.append(conn)
        
    def read_server(self,conn,mask):
        echoed_msg = self.protocol.recv_msg(conn)
        #print(echoed_msg)
        if echoed_msg:
            if echoed_msg.msg_type == "join":
                print ("Client " , conn , " joined " , echoed_msg.channel , " channel")
                if echoed_msg.channel not in self.channels[conn]:
                    self.channels[conn].append(echoed_msg.channel)
            elif echoed_msg.msg_type == "message":
                actual_channel = echoed_msg.channel
                #print(actual_channel)
                logging.debug(f"Received message: {echoed_msg}")
                for connection in self.channels.keys() :
                    if actual_channel in self.channels[connection]:
                        print("Sending message to " , connection, " in channel " , actual_channel)
                        self.protocol.send_msg(connection, echoed_msg)                        
            elif echoed_msg.msg_type == "register":
                print("Client " , echoed_msg.user , " connected")
            else:
                self.selector.unregister(conn)
                conn.close()
                print("Client disconnected")
            
    def loop(self):
        while True:
            events = self.sel.select()
            #print("triggered read?")
            for key, mask in events:
                callback = key.data
                callback(key.fileobj,mask)
            #print ("looping")
        exit()
        
        
        """Loop indefinetely."""

