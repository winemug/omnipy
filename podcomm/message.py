from packet import Packet
from enum import Enum
from crc import crc16
import binascii

class MessageState(Enum):
    Incomplete = 0,
    Invalid = 1,
    Complete = 2

class Message():
    # def __init__(self, timestamp, address, msgType, unknownBits, sequence, data):
    #     if msgType != "PDM" and msgType != "POD":
    #         raise ValueError()
    #     self.timestamp = timestamp
    #     self.type = msgType
    #     self.unknownBits = unknownBits
    #     self.length = len(data)
    #     self.sequence = sequence
    #     self.bodyWithCrc = data + self.calculateChecksum(data)
    #     self.address = address
    #     self.state = MessageState.Complete

    @staticmethod
    def fromPacket(packet):
        if packet.type != "PDM" and packet.type != "POD":
            raise ValueError()
        m = Message()
        m.timestamp = packet.timestamp
        m.type = packet.type
        m.address = packet.address
        b0 = ord(packet.body[0])
        b1 = ord(packet.body[1])
        m.unknownBits = b0 >> 6
        m.length = ((b0 & 3) <<8) | b1
        m.sequence = (b0 & 0x3C) >> 2
        m.bodyWithCrc = packet.body[2:]
        m.updateMessageState()
        m.acknowledged = False
        return m

    def addConPacket(self, packet):
        if packet.type != "CON":
            raise ValueError()
        self.bodyWithCrc = self.bodyWithCrc + packet.body
        self.acknowledged = False
        self.updateMessageState()

    def updateMessageState(self):
        if len(self.bodyWithCrc) == self.length + 2:
            if self.verifyChecksum():
                self.state = MessageState.Complete
            else:
                self.state = MessageState.Invalid
        elif len(self.bodyWithCrc) < self.length + 2:
            self.state = MessageState.Incomplete
        else:
            self.state = MessageState.Invalid

    def verifyChecksum(self):
        checksum = self.calculateChecksum(self.bodyWithCrc[:-2])
        return checksum == self.bodyWithCrc[-2:]

    def calculateChecksum(self, body):
        a = self.address.decode("hex")
        b0 = self.unknownBits << 6 | (len(body) >> 8 & 3) | (self.sequence & 0x0f) << 2
        b1 = len(body) & 0xff
        crcBody = a + chr(b0) + chr(b1) + body
        crcVal = crc16(crcBody)
        return chr(crcVal >> 8) + chr (crcVal & 0xff)

    def __str__(self):
        #return "%s From: %s Addr: %s Seq: 0x%02x Len: 0x%02x Msg: %s Ack: %s (%s)" % (self.timestamp, self.type, self.address, self.sequence, self.length, binascii.hexlify(self.bodyWithCrc[:-2]), self.acknowledged, self.state)
        return "%s %s: %s (%s, %s)" % (self.timestamp, self.type, binascii.hexlify(self.bodyWithCrc[:-2]),
            "OK" if self.state == MessageState.Complete else "ERR", "ACK" if self.acknowledged else "NOT")
