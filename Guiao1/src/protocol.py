"""Protocol for chat server - Computação Distribuida Assignment 1."""
import json
from datetime import datetime
from socket import socket


class Message:
    """Message Type."""

    def __init__(self, command):
        self.command = command
    
class JoinMessage(Message): # está a herdar de Message, é uma subclasse
    """Message to join a chat channel."""
    def __init__(self,comand, channel):
        super().__init__(comand) # chama o construtor da classe mãe
        self.channel = channel
    
    def __str__(self): # é basicamente um toString() do Java
        return f"{{\"command\": \"{self.command}\", \"channel\": \"{self.channel}\"}}"

class RegisterMessage(Message):
    """Message to register username in the server."""
    def __init__(self,comand, user):
        super().__init__(comand) # chama o construtor da classe mãe
        self.user = user
    
    def __str__(self):
        return f"{{\"command\": \"{self.command}\", \"user\": \"{self.user}\"}}"
    
class TextMessage(Message):
    """Message to chat with other clients."""
    def __init__(self,comand, message, channel = "default"):
        super().__init__(comand)
        self.message = message
        self.channel = channel
        self.ts = int(datetime.now().timestamp())

    def __str__(self):
        if self.channel != "default":
            return f"{{\"command\": \"{self.command}\", \"message\": \"{self.message}\", \"channel\": \"{self.channel}\", \"ts\": \"{self.ts}\"}}"
        else:
            return f"{{\"command\": \"{self.command}\", \"message\": \"{self.message}\", \"ts\": {self.ts}}}"

class CDProto: # é uma classe abstrata. Assim dá para fazer CDProto.register noutros casos
    # Isto é um padrão de software chamado Factory Method
    """Computação Distribuida Protocol."""

    @classmethod
    def register(cls, username: str) -> RegisterMessage:
        """Creates a RegisterMessage object."""
        return RegisterMessage("register", username)

    @classmethod
    def join(cls, channel: str) -> JoinMessage:
        """Creates a JoinMessage object."""
        return JoinMessage("join", channel)

    @classmethod
    def message(cls, message: str, channel: str = "default") -> TextMessage:
        """Creates a TextMessage object."""
        return TextMessage("message", message, channel)

    @classmethod
    def send_msg(cls, connection: socket, msg: Message):
        """Sends through a connection a Message object."""
        data = bytes(msg.__str__(),encoding="utf-8") 
        header = len(data)
        header = header.to_bytes(2, "big") ## Por cusa da notação big-endian
        
        try:
            connection.sendall(header + data)
        except BrokenPipeError:
            return
        
    @classmethod
    def recv_msg(cls, connection: socket) -> Message:
        """Receives through a connection a Message object."""
        header = int.from_bytes(connection.recv(2), "big") # Verificar se o header está bem ou não
        if header == 0: return # O sor disse que não é para fazer recv quando a mensagem tem tamanho 0
        
        rcv_message = connection.recv(header).decode("utf-8")
        
        if rcv_message:
            try:
                rcv_message = json.loads(rcv_message)
            except json.decoder.JSONDecodeError:
                raise CDProtoBadFormat
        
        if rcv_message["command"] == "register":
            return CDProto.register(rcv_message["user"])
        elif rcv_message["command"] == "join":
            return CDProto.join(rcv_message["channel"])
        elif rcv_message["command"] == "message":
            if "channel" not in rcv_message.keys():
                return CDProto.message(rcv_message["message"],"default")
            else:
                return CDProto.message(rcv_message["message"],rcv_message["channel"])
        else:
            raise CDProtoBadFormat(rcv_message)

class CDProtoBadFormat(Exception):
    """Exception when source message is not CDProto."""

    def __init__(self, original_msg: bytes=None) :
        """Store original message that triggered exception."""
        self._original = original_msg

    @property
    def original_msg(self) -> str:
        """Retrieve original message as a string."""
        return self._original.decode("utf-8")
