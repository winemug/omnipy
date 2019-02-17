#!/usr/bin/python3
from socketserver import UDPServer, BaseRequestHandler


class OmnipyBeacon(BaseRequestHandler):
    def handle(self):
        socket = self.request[1]
        socket.sendto("wut", self.client_address)


addr = ("", 6664)
server = UDPServer(addr, OmnipyBeacon)
server.serve_forever()
