import struct
import binascii
from datetime import datetime

class Packet():
    @staticmethod
    def Ack(address, sequence, fromPOD):
        data = struct.pack(">I", address)
        data += chr(sequence | 0b01000000)
        if fromPOD:
            data += "\0\0\0\0"
        else:
            data += struct.pack(">I", address)
        return Packet(0, data)

    def setSequence(self, sequence):
        self.sequence = sequence
        b4 = ord(self.data[4]) & 0b11100000 | sequence
        self.data = self.data[0:4] + chr(b4) + self.data[5:]

    def __init__(self, timestamp, data):
        self.timestamp = timestamp
        self.data = data
        self.valid = False
        self.error = None
        if len(data) < 5:
            self.error = "Packet length too small"
            return

        self.address = struct.unpack(">I", data[0:4])[0]

        t = ord(data[4]) >> 5
        self.sequence = ord(data[4]) & 0b00011111

        if t == 5:
            self.type = "PDM"
        elif t == 7:
            self.type = "POD"
        elif t == 2:
            self.type = "ACK"
        elif t == 4:
            self.type = "CON"
        else:
            self.error = "Unknown packet type: 0b" + bin(t)
            return

        if self.type == "PDM" or self.type == "POD":
            if len(data) < 12:
                self.error = "Packet length too small for type " + self.type
                return
            self.body = data[9:]
            self.address2 = struct.unpack(">I", data[5:9])[0]
            if self.address2 == self.address:
                self.ackFinal = False
            elif self.address2 == 0:
                self.ackFinal = True
            else:
                self.error = "Address mismatch in packet"
                return
            self.valid = True
        elif self.type == "ACK":
            if len(data) != 9:
                self.error = "Incorrect packet length for type ACK"
                return
            self.address2 = struct.unpack(">I", data[5:9])[0]
            if self.address2 == self.address:
                self.ackFinal = False
            elif self.address2 == 0:
                self.ackFinal = True
            else:
                self.error = "Address mismatch in packet"
                return
            self.valid = True
        elif self.type == "CON":
            if len(data) < 6:
                self.error = "Packet length too small for type CON"
                return
            self.body = data[5:]
            self.valid = True

    def __str__(self):
        timestr = datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")
        if self.valid:
            if self.type == "CON":
                return "%s Pkt %s Addr: 0x%08x                 Seq: 0x%02x Body: %s" % (timestr, self.type, self.address, self.sequence, binascii.hexlify(self.body))
            elif self.type == "ACK":
                return "%s Pkt ACK Addr: 0x%08x Addr2: 0x%08x Seq: 0x%02x" % (timestr, self.address, self.address2, self.sequence)
            else:
                return "%s Pkt %s Addr: 0x%08x Addr2: 0x%08x Seq: 0x%02x Body: %s" % (timestr, self.type, self.address, self.address2, self.sequence, binascii.hexlify(self.body))
        else:
            return "%s Pkt invalid. Error: %s Body: %s" % (timestr, self.error, binascii.hexlify(self.data))