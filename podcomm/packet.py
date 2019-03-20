import binascii
import struct
from .exceptions import ProtocolError

class Packet:
    def __init__(self):
        self.data = None
        self.address = None
        self.sequence = None
        self.type = None
        self.body = None

    @staticmethod
    def Ack(packet_address, message_address):
        data = struct.pack(">I", packet_address)
        data +=  b"\x40"
        data += struct.pack(">I", message_address)
        return Packet.from_data(data)

    @staticmethod
    def from_data(data):
        p = Packet()
        p.data = data
        if len(data) < 5:
            raise ProtocolError("Packet length too small")

        p.address = struct.unpack(">I", data[0:4])[0]

        t = data[4] >> 5
        p.sequence = data[4] & 0b00011111

        if t == 5:
            p.type = "PDM"
        elif t == 7:
            p.type = "POD"
        elif t == 2:
            p.type = "ACK"
        elif t == 4:
            p.type = "CON"
        else:
            raise ProtocolError("Unknown packet type: %s" % bin(t))

        if p.type == "PDM" or p.type == "POD":
            if len(data) < 12:
                raise ProtocolError("Packet length too small for type %s" % p.type)
        elif p.type == "ACK":
            if len(data) != 9:
                raise ProtocolError("Incorrect packet length for type ACK")
        elif p.type == "CON":
            if len(data) < 6:
                raise ProtocolError("Packet length too small for type CON")

        p.body = data[5:]
        return p

    def setSequence(self, sequence):
        self.sequence = sequence
        b4 = self.data[4] & 0b11100000 | sequence
        self.data = self.data[0:4] + bytes([b4]) + self.data[5:]

    def __str__(self):
        if self.type == "CON":
            return "Pkt %s Addr: 0x%08x                 Seq: 0x%02x Body: %s" % (self.type, self.address, self.sequence, binascii.hexlify(self.body))
        elif self.type == "ACK":
            return "Pkt ACK Addr: 0x%08x Seq: 0x%02x Body: %s" % (self.address, self.sequence, binascii.hexlify(self.body))
        else:
            return "Pkt %s Addr: 0x%08x Seq: 0x%02x Body: %s" % (self.type, self.address, self.sequence, binascii.hexlify(self.body))
