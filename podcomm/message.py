from packet import Packet
from enum import Enum
from crc import crc16
import binascii
from datetime import datetime

class MessageState(Enum):
    Incomplete = 0,
    Invalid = 1,
    Complete = 2

class Message():
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

    def getPackets(self, sequence):
        if self.state != MessageState.Complete:
            raise ValueError()

        addrInt = self.address.decode("hex")
        data = ""
        data += addrInt >> 24 & 0xff
        data += addrInt >> 16 & 0xff
        data += addrInt >> 8 & 0xff
        data += addrInt & 0xff

        if self.type == "PDM":
            data += chr(sequence | 0b10100000)
        else:
            data += chr(sequence | 0b11100000)
            addrInt = 0

        data += addrInt >> 24 & 0xff
        data += addrInt >> 16 & 0xff
        data += addrInt >> 8 & 0xff
        data += addrInt & 0xff

        data += char((m.unknownBits << 6) | (m.sequence << 2) | ((m.length << 8) & 0xff))
        data += char(m.length & 0xff)

        # max first packet 31 - 11 = 20bytes with crc -- 18 without
        # max con packet: 31 - 5 = 26 bytes with crc -- 24 without

        maxLength = 18
        bodyToWrite = self.bodyWithCrc[:-2]
        crc = self.bodyWithCrc[-2:]

        lenToWrite = min(maxLength, len(bodyToWrite))
        data += bodyToWrite[0:lenToWrite]
        bodyToWrite = bodyToWrite[lenToWrite:]

        maxLength = 24
        conData = []
        while (len(bodyToWrite) > 0):
            sequence = (sequence + 1) % 32
            lenToWrite = min(maxLength, len(bodyToWrite))
            addrInt = self.address.decode("hex")
            cond = ""
            cond += chr(addrInt >> 24 & 0xff)
            cond += chr(addrInt >> 16 & 0xff)
            cond += chr(addrInt >> 8 & 0xff)
            cond += chr(addrInt & 0xff)
            cond += chr(sequence | 0b10000000)
            cond += bodyToWrite[0:lenToWrite]
            bodyToWrite = bodyToWrite[lenToWrite:]
            conData.append(cond)

        packets = [ Packet(0, data) ]
        for cond in conData:
            packets.append(Packet(0, cond))

        packets[-1].data += crc
        return packets

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
        timestr = datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")
        #return "%s From: %s Addr: %s Seq: 0x%02x Len: 0x%02x Msg: %s Ack: %s (%s)" % (self.timestamp, self.type, self.address, self.sequence, self.length, binascii.hexlify(self.bodyWithCrc[:-2]), self.acknowledged, self.state)
        return "%s Msg %s: %s (%s, %s) (seq: 0x%02x, unkn.: 0x%02x)" % (timestr, self.type, binascii.hexlify(self.bodyWithCrc[:-2]),
            "OK" if self.state == MessageState.Complete else "ERROR", "ACK'd" if self.acknowledged else "NOACK",
            self.sequence, self.unknownBits)
