
from socketserver import UDPServer, BaseRequestHandler
from podcomm.definitions import getLogger, configureLogging


class OmnipyBeacon(BaseRequestHandler):
    def handle(self):
        try:
            data = self.request[0].strip()
            socket = self.request[1]
            host, port = self.client_address[0]
            getLogger().info("UDP broadcast message from %s: %s" % (host, data))
            socket.sendto("wut".encode("ascii"), (host, 6665))
        except Exception as e:
            getLogger().warning("Error while responding to udp broadcast: %s" % e)
            

try:
    configureLogging()
    address = ("", 6664)
    server = UDPServer(address, OmnipyBeacon)
    server.serve_forever()
except Exception as e:
    getLogger().error("Error while running omnipy beacon: %s" % e)
    raise e
