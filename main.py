from socketserver import ThreadingMixIn, TCPServer, StreamRequestHandler
from sys import argv
import struct
import select
import socket
import logging
SOCKS_VERSION = 5
logging.basicConfig(level=logging.DEBUG)


class Proxy(StreamRequestHandler):
    def handle(self):
        logging.info('Try to connect with %s:%s' % self.client_address)
        header = self.connection.recv(2)
        version, count_of_methods = struct.unpack("!BB", header)

        if not (version == SOCKS_VERSION and count_of_methods > 0):
            print("Wrong version", SOCKS_VERSION)
            self.server.close_request(self.request)
            return

        methods = self.get_methods(count_of_methods)
        if 0 not in set(methods):
            self.server.close_request(self.request)
            return
        self.connection.sendall(struct.pack("!BB", SOCKS_VERSION, 0))
        version, connect_type, inf, address_type = struct.unpack("!BBBB", self.connection.recv(4))

        if not (version == SOCKS_VERSION):
            print("Wrong version", SOCKS_VERSION)
            self.server.close_request(self.request)
            return
        address = None
        bind_address = None
        remote = None
        if address_type == 1:
            address = socket.inet_ntoa(self.connection.recv(4))
        elif address_type == 3:
            domain_length = self.connection.recv(1)[0]
            address = self.connection.recv(domain_length)
            address = socket.gethostbyname(address)
        client_port = struct.unpack('!H', self.connection.recv(2))[0]
        try:
            if connect_type == 1:
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.connect((address, client_port))
                bind_address = remote.getsockname()
                logging.info('Connected to %s %s' % (address, client_port))
            else:
                self.server.close_request(self.request)
            addr = struct.unpack("!I", socket.inet_aton(bind_address[0]))[0]
            port = bind_address[1]
            reply = struct.pack("!BBBBIH", SOCKS_VERSION, 0, 0, 1, addr, port)
        except Exception as err:
            logging.error(err)
            reply = struct.pack("!BBBBIH", SOCKS_VERSION, 5, 0, address_type, 0, 0)
        self.connection.sendall(reply)
        if reply[1] == 0 and connect_type == 1:
            self.working_loop(self.connection, remote)
        self.server.close_request(self.request)

    def get_methods(self, n):
        methods = []
        for i in range(n):
            methods.append(ord(self.connection.recv(1)))
        return methods

    def working_loop(self, client, remote):
        while True:
            r, w, e = select.select([client, remote], [], [])
            if client in r:
                data = client.recv(1024 * 1024)
                if remote.send(data) <= 0:
                    break
            if remote in r:
                data = remote.recv(1024 * 1024)
                if client.send(data) <= 0:
                    break


class MultiThreadTCPServer(ThreadingMixIn, TCPServer):
    pass


if __name__ == '__main__':
    script, port = argv
    with MultiThreadTCPServer(('127.0.0.1', int(port)), Proxy) as server:
        server.serve_forever()