
from socketserver import UDPServer, BaseRequestHandler
import podcomm.definitions

class OmnipyBeacon(BaseRequestHandler):
    def __init__(self):
        self.logger = getLogger()

    def handle(self):
        try:
            data = self.request[0].strip()
            socket = self.request[1]
            host, port = self.client_address[0]
            self.logger.info("UDP broadcast message from %s: %s" % (host, data))
            socket.sendto("wut".encode("ascii"), (host, 6665))
        except Exception as e:
            self.logger.warning("Error while responding to udp broadcast: %s" % e)
            

try:
    configureLogging()
    addr = ("", 6664)
    server = UDPServer(addr, OmnipyBeacon)
    server.serve_forever()
except Exception as e:
    getLogger().error("Error while running omnipy beacon: %s" % e)
    raise e