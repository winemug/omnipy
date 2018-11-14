from packet import Packet
from enum import Enum
from crc import crc16
import binascii
import struct
from datetime import datetime

class MessageState(Enum):
    Incomplete = 0,
    Invalid = 1,
    Complete = 2

class Message():
    def __init__(self, timestamp, mtype, address, unknownBits, sequence):
        self.timestamp = timestamp
        self.type = mtype
        self.address = address
        self.unknownBits = unknownBits
        self.sequence = sequence
        self.length = 0
        self.body = chr(0) + chr(0)
        self.acknowledged = False
        self.state = MessageState.Incomplete

    def addContent(self, ctype, cbody, clen = -1):
        if clen < 0:
            clen = len(cbody)
        copy = self.body[0:-2]
        copy += chr(ctype) + chr(clen) + cbody
        self.length = len(copy)
        self.body = copy + self.calculateChecksum(copy)
        self.state = MessageState.Complete

    @staticmethod
    def fromPacket(packet):
        if packet.type != "PDM" and packet.type != "POD":
            raise ValueError()
        b0 = ord(packet.body[0])
        b1 = ord(packet.body[1])
        unknownBits = b0 >> 6
        sequence = (b0 & 0x3C) >> 2
        m = Message(packet.timestamp, packet.type, packet.address, unknownBits, sequence)
        m.length = ((b0 & 3) <<8) | b1
        m.body = packet.body[2:]
        m.updateMessageState()
        m.acknowledged = False
        return m

    def addConPacket(self, packet):
        if packet.type != "CON":
            raise ValueError()
        self.body = self.body + packet.body
        self.acknowledged = False
        self.updateMessageState()

    def getPackets(self):
        if self.state != MessageState.Complete:
            raise ValueError()
        data = struct.pack(">I", self.address)

        if self.type == "PDM":
            data += chr(0b10100000)
            data += struct.pack(">I", self.address)
        else:
            data += chr(0b11100000)
            data += struct.pack(">I", 0)

        data += chr((self.unknownBits << 6) | (self.sequence << 2) | ((self.length >> 8) & 0x03))
        data += chr(self.length & 0xff)

        # max first packet 31 - 11 = 20bytes with crc -- 18 without
        # max con packet: 31 - 5 = 26 bytes with crc -- 24 without

        maxLength = 18
        bodyToWrite = self.body[:-2]
        crc = self.body[-2:]

        lenToWrite = min(maxLength, len(bodyToWrite))
        data += bodyToWrite[0:lenToWrite]
        bodyToWrite = bodyToWrite[lenToWrite:]

        maxLength = 24
        conData = []
        while (len(bodyToWrite) > 0):
            lenToWrite = min(maxLength, len(bodyToWrite))
            cond = struct.pack(">I", self.address)
            cond += chr(0b10000000)
            cond += bodyToWrite[0:lenToWrite]
            bodyToWrite = bodyToWrite[lenToWrite:]
            conData.append(cond)

        packets = [ Packet(0, data) ]
        for cond in conData:
            packets.append(Packet(0, cond))

        packets[-1].data += crc
        return packets

    def updateMessageState(self):
        if len(self.body) == self.length + 2:
            if self.verifyChecksum():
                self.state = MessageState.Complete
            else:
                self.state = MessageState.Invalid
        elif len(self.body) < self.length + 2:
            self.state = MessageState.Incomplete
        else:
            self.state = MessageState.Invalid

    def verifyChecksum(self):
        checksum = self.calculateChecksum(self.body[:-2])
        return checksum == self.body[-2:]

    def calculateChecksum(self, body):
        a = struct.pack(">I", self.address)
        b0 = self.unknownBits << 6 | (len(body) >> 8 & 3) | (self.sequence & 0x0f) << 2
        b1 = len(body) & 0xff
        crcBody = a + chr(b0) + chr(b1) + body
        crcVal = crc16(crcBody)
        return chr(crcVal >> 8) + chr (crcVal & 0xff)

    def getContents(self):
        ptr = 0
        contents = []
        while ptr < self.length:
            contentType = ord(self.body[ptr])
            contentLength = ord(self.body[ptr+1])
            content = self.body[ptr+2:ptr+2+contentLength]
            contents.append((contentType, content))
            ptr += 2 + contentLength
        return contents

    def __str__(self):
        timestr = datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")
        #return "%s From: %s Addr: %s Seq: 0x%02x Len: 0x%02x Msg: %s Ack: %s (%s)" % (self.timestamp, self.type, self.address, self.sequence, self.length, binascii.hexlify(self.body[:-2]), self.acknowledged, self.state)
        return "%s Msg %s: %s (%s, %s) (seq: 0x%02x, unkn.: 0x%02x)" % (timestr, self.type, binascii.hexlify(self.body[:-2]),
            "OK" if self.state == MessageState.Complete else "ERROR", "ACK'd" if self.acknowledged else "NOACK",
            self.sequence, self.unknownBits)
