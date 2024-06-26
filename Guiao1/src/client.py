import logging
import socket
import sys
import selectors
import fcntl
import os
from .protocol import CDProto, CDProtoBadFormat

logging.basicConfig(filename=f"{sys.argv[0]}.log", level=logging.DEBUG, filemode="w")

class Client:
    def __init__(self, name: str = "Foo"):
        self.name = name
        #initialize socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #initialize selector
        self.selector = selectors.DefaultSelector()
        #initialize protocol
        self.protocol = CDProto
        #initialize channel list, by default everyone is in default_channel
        self.channel = ["default_channel"]
        
        
    def process_keyboard_input(self, stdin, mask):
        try:
            message = sys.stdin.readline().rstrip("\n")
            if not message: # empty message, dont allow enter spam, it crashes the server
                return
            command, *args = message.split() # split message into command (1st entry of list) and arguments ( the other entries )
            if command == "/join":
                channel = args[0]
                # add the channel to the list of channels the client is in
                self.channel.append(channel)
                # send join message to server
                join_msg = self.protocol.join(channel)
                self.protocol.send_msg(self.socket, join_msg)
                print(f"Joined {channel} channel sucessfully")
            elif command == "exit":
                print(f"Client {self.name} disconnecting from server")
                self.socket.close()
                self.selector.unregister(self.socket)
                exit()
            else:
                # send normal message to server
                text_msg = self.protocol.message(message, self.channel[-1])
                self.protocol.send_msg(self.socket, text_msg)
        except Exception as e:
            print(f"Error processing message given: {e}") 
       
    def process_server_message(self, conn, mask):
        # function to handle messages sent from server and print them to the terminal
        msg = self.protocol.recv_msg(self.socket)
        logging.debug(f"Received message: {msg}")
        
        message_type = msg.msg_type
        
        if message_type == "message":
            print(msg.message)
    
    def connect(self):
        # connect to the server
        self.socket.connect(("localhost", 9876))
        print("Successfully connected to server")
        # send register message
        register_message = self.protocol.register(self.name) 
        self.protocol.send_msg(self.socket, register_message)
        # set all the stdin flags to non blocking
        self.selector.register(self.socket, selectors.EVENT_READ, self.process_server_message)
        orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)
        # register stdin to selector so it triggers the function when there is input in the terminal
        self.selector.register(sys.stdin, selectors.EVENT_READ, self.process_keyboard_input)

    def loop(self):
        while True:
            sys.stdout.write('')
            sys.stdout.flush()
            for k, mask in self.selector.select():
                callback = k.data
                callback(self, k.fileobj)    
        
