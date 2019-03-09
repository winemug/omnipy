import binascii
import struct
from .exceptions import ProtocolError

class Packet:
    def __init__(self):
        self.data = None
        self.address = None
        self.address2 = None
        self.sequence = None
        self.type = None
        self.body = None
        self.ack_final = False

    @staticmethod
    def Ack(address, ack_final, address2=None):
        data = struct.pack(">I", address)
        data +=  b"\x40"
        if address2 is not None:
            data += struct.pack(">I", address2)
        elif ack_final:
            data += b"\x00\x00\x00\x00"
        else:
            data += struct.pack(">I", address)
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
            p.body = data[9:]
            p.address2 = struct.unpack(">I", data[5:9])[0]
            if p.address2 != 0 and p.address != p.address2 and p.address != 0xffffffff:
                raise ProtocolError("Address mismatch in packet. Addr1: 0x%08X Addr2: 0x%08X"
                                    % (p.address, p.address2))
        elif p.type == "ACK":
            if len(data) != 9:
                raise ProtocolError("Incorrect packet length for type ACK")

            p.address2 = struct.unpack(">I", data[5:9])[0]
            if p.address2 == p.address:
                p.final_ack = False
            elif p.address2 == 0:
                p.final_ack = True

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
            return "Pkt ACK Addr: 0x%08x Addr2: 0x%08x Seq: 0x%02x" % (self.address, self.address2, self.sequence)
        else:
            return "Pkt %s Addr: 0x%08x Addr2: 0x%08x Seq: 0x%02x Body: %s" % (self.type, self.address, self.address2, self.sequence, binascii.hexlify(self.body))
