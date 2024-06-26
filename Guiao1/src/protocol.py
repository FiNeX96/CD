#!/usr/bin/env python3
"""Protocol for chat server - Computação Distribuida Assignment 1."""
import json
from datetime import datetime
from socket import socket


class Message:
    
    # fazer um to Json e um from Json

    def __init__(self, msg_type: str):
        self.msg_type = msg_type

    def __str__(self) -> str:
        return f"command:" "{self.msg_type}"

    """Message Type."""

    
class JoinMessage(Message):

    def __init__(self, msg_type: str, channel: str ):
        super().__init__(msg_type)
        self.channel = channel
        self.msg_type = msg_type

    def __str__(self) -> str:
        return f'{{"command": "{self.msg_type}", "channel": "{self.channel}"}}'
    """Message to join a chat channel."""


class RegisterMessage(Message):

    def __init__(self, msg_type: str, user : str ):
        super().__init__("register")
        self.msg_type = msg_type
        self.user = user
        
    def __str__(self) -> str:
        return f'{{"command": "{self.msg_type}", "user": "{self.user}"}}'
    """Message to register username in the server."""

    
class TextMessage(Message):
    def __init__(self, msg_type: str, message: str, channel : str = "default_channel" ):
        super().__init__(msg_type)
        self.msg_type = msg_type
        self.message = message
        self.ts = int(datetime.now().timestamp())
        self.channel = channel
    
    def __str__(self) -> str:
        repr_dict = {"command": self.msg_type, "message": self.message, "ts": self.ts}
        if self.channel != "default_channel":
            repr_dict["channel"] = self.channel
        return json.dumps(repr_dict)

    """Message to chat with other clients."""


class CDProto:
    """Computação Distribuida Protocol."""

    @classmethod
    def register(cls, username: str) -> RegisterMessage:

        return RegisterMessage("register",username)
        """Creates a RegisterMessage object."""

    @classmethod
    def join(cls, channel: str) -> JoinMessage:

        return JoinMessage("join",channel)
        """Creates a JoinMessage object."""

    @classmethod
    def message(cls, message: str, channel: str = "default_channel" ) -> TextMessage:
        return TextMessage("message", message,channel)

    @classmethod
    def send_msg(cls, connection: socket, msg: Message):
      
        if (isinstance(msg, RegisterMessage)):
            msg = json.dumps({"command": "register", "user": msg.user}).encode("utf-8")         
        elif (isinstance(msg, JoinMessage)):
            msg = json.dumps({"command": "join", "channel": msg.channel}).encode("utf-8")
        elif (isinstance(msg, TextMessage)):
            msg = json.dumps({"command": "message", "message": msg.message,"channel" : msg.channel, "ts": msg.ts}).encode("utf-8")
            
        msg_header = len(msg).to_bytes(2,byteorder='big') # first 2 bytes are the header
        
        try:
            connection.sendall(msg_header + msg)
        except BrokenPipeError:
            return
        
        """Sends through a connection a Message object."""

    @classmethod
    def recv_msg(cls, connection: socket) -> Message:

        
        msg_length = int.from_bytes(connection.recv(2),"big") # first 2 bytes should be the header
            
        if msg_length == 0: # problems with clients disconnecting and sending length 0 messages for some reason
            return 
        
        message = connection.recv(msg_length).decode("utf-8") # the remaining bytes are the message
        #print(msg_length,message.decode("UTF-8"))
        message_dic = {}
        if message :
            try:
                message_dic = json.loads(message)
            except json.decoder.JSONDecodeError:
                print ("message with bad format -> " , message)
                raise CDProtoBadFormat

            
        #print(message_dic)        
        if message_dic["command"] == "register":
            return CDProto.register(message_dic["user"])      
        elif message_dic["command"] == "join":
            return CDProto.join(message_dic["channel"])

        elif message_dic["command"] == "message":
            if "channel" not in message_dic.keys():
                return CDProto.message(message_dic["message"],"default_channel") # if its the default channel, it will fill as none
            else:
                return CDProto.message(message_dic["message"],message_dic["channel"]) # if it has a channel 
        
        """Receives through a connection a Message object."""


class CDProtoBadFormat(Exception):
    """Exception when source message is not CDProto."""

    def __init__(self, original_msg: bytes=None) :
        """Store original message that triggered exception."""
        self._original = original_msg

    @property
    def original_msg(self) -> str:
        """Retrieve original message as a string."""
        return self._original.decode("utf-8")
