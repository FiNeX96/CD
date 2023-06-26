"""CD Chat client program"""
import logging
import sys
import fcntl
import os
import selectors
import socket

from .protocol import CDProto, CDProtoBadFormat

logging.basicConfig(filename=f"{sys.argv[0]}.log", level=logging.DEBUG, filemode="w")


class Client:
    """Chat Client process."""

    def __init__(self, name: str = "Foo"):
        """Initializes chat client."""
        self.name = name
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.m_selector = selectors.DefaultSelector()
        self.protocol = CDProto
        self.channel = ["default"] # tá no canal default, e depois vai ser atribuido o canal que o user escolher
        print("Client starting ...")

    def connect(self):
        """Connect to chat server and setup stdin flags."""
        self.socket.connect(('localhost', 11001)) # host e porta
        self.m_selector.register(self.socket, selectors.EVENT_READ,self.read_from_server)

        #Incializar o protocolo, em que se vai usar o RegisterMessage
        registerProtocol = self.protocol.register(self.name)
        self.protocol.send_msg(self.socket, registerProtocol) #Envia a mensagem para o servidor
        print("Mandei a mensagem para o servidor")

    def read_from_server(self, conn,mask):
        """Reads data from server and prints it to stdout."""
        MessageRc = self.protocol.recv_msg(self.socket)
        if MessageRc:
            logging.debug('received message no cliente: %s', MessageRc)
            if MessageRc:
                print("Mensagem recebida do servidor no cliente",MessageRc.message)
            else:
                print('closing', conn)
                self.m_selector.unregister(conn)
                conn.close()

    def got_keyboard_data(self, stdin, mask):
        """Callback for keyboard input."""
        user_input = stdin.read().strip()       # lê a mensagem do user e retira o \n do fim
        if user_input != "":
            command= user_input.split()[0].strip()  
            print("Comando",command)
            if command == "/join":
                self.channel.append(user_input.split()[1])
                join_msg = self.protocol.join(self.channel[-1])
                self.protocol.send_msg(self.socket, join_msg)
            else: #TextMessage
                if self.channel:
                    std_msg = self.protocol.message(user_input, self.channel[-1])
                    self.protocol.send_msg(self.socket, std_msg)
                else:
                    std_msg = self.protocol.message(user_input)
                    self.protocol.send_msg(self.socket, std_msg)

    def loop(self):
    # set sys.stdin non-blocking
        orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)

        # register event
        self.m_selector.register(sys.stdin, selectors.EVENT_READ, self.got_keyboard_data)
        
        while True:
            sys.stdout.write('Type something and hit enter: \n')
            sys.stdout.flush()
            for k, mask in self.m_selector.select():
                callback = k.data
                callback(k.fileobj, mask)

#recebe do teclado e da rede