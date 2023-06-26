"""CD Chat server program."""
import logging
import selectors
import socket

from .protocol import CDProto, CDProtoBadFormat

logging.basicConfig(filename="server.log", level=logging.DEBUG, filemode="w")


class Server:
    """Chat Server process."""
    def __init__(self):
        """Initializes chat server."""
        self.selector = selectors.DefaultSelector()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # para evitar o erro de "address already in use"
        self.socket.bind(('localhost', 11001))
        self.socket.listen(10) # 10 é o numero maximo de clientes conectados
        self.selector.register(self.socket, selectors.EVENT_READ, self.accept)
        print("Server starting ...")
        self.data_clients = {} # dicionario que vai guardar os dados dos clientes

    def accept(self,sock, mask):
        conn, addr = sock.accept()  # Should be ready
        self.data_clients[conn] = ["default"] # inicia o dicionário com os valores do user e o seu canal default
        print('accepted', conn, 'from', addr)
        conn.setblocking(False)
        self.selector.register(conn, selectors.EVENT_READ, self.read)

    def read(self,conn, mask):
        message = CDProto.recv_msg(conn) 
        if message:
            logging.debug('received message no server: %s', message)
            if message.command == 'register':
                print('User {} connected'.format(message.user))
            elif message.command == "join":
                if message.channel not in self.data_clients[conn]:
                    self.data_clients[conn].append(message.channel) # não pode ser com o pop e in, porque senão nunca mais adicionas   
            elif message.command == 'message':
                for connect in self.data_clients.keys():
                    if message.channel in self.data_clients[connect]:# se o canal da mensagem for igual ao canal do user
                        CDProto.send_msg(connect, message) 
        else:
                print('closing', conn)
                self.data_clients.pop(conn) # remove o user do dicionário
                self.selector.unregister(conn)
                conn.close()

    def loop(self):
        """Loop indefinetely."""
        while True:
            events = self.selector.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)