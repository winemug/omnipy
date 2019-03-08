from .packet import Packet
from .exceptions import ProtocolError
from enum import Enum
from .crc import crc16
import struct

class MessageState(Enum):
    Incomplete = 0,
    Invalid = 1,
    Complete = 2

class MessageType(Enum):
    PDM = 0,
    POD = 1

class Message:
    def __init__(self, mtype, address, unknownBits = 0, sequence = 0):
        self.type = mtype
        self.address = address
        self.unknownBits = unknownBits
        self.sequence = sequence
        self.length = 0
        self.body = b"\x00\x00"
        self.acknowledged = False
        self.state = MessageState.Incomplete

    def addCommand(self, cmdtype, cmdbody, cmdlen = -1):
        if cmdlen < 0:
            cmdlen = len(cmdbody)
        copy = self.body[0:-2]
        copy += bytes([cmdtype, cmdlen]) + cmdbody
        self.length = len(copy)
        self.body = copy + self.calculateChecksum(copy)
        self.state = MessageState.Complete

    def setNonce(self, nonce):
        copy = self.body[0:2]
        copy += struct.pack(">I", nonce)
        copy += self.body[6:-2]
        self.body = copy + self.calculateChecksum(copy)
        self.state = MessageState.Complete

    @staticmethod
    def fromPacket(packet):
        if packet.type == "PDM":
            mType = MessageType.PDM
        elif packet.type == "POD":
            mType = MessageType.POD
        else:
            raise ProtocolError("Packet type %s not valid for a first packet in a message" % packet.type)

        b0 = packet.body[0]
        b1 = packet.body[1]
        unknownBits = b0 >> 6
        sequence = (b0 & 0x3C) >> 2

        m = Message(mType, packet.address, unknownBits, sequence)
        m.length = ((b0 & 3) <<8) | b1
        m.body = packet.body[2:]
        m.updateMessageState()
        m.acknowledged = False
        return m

    def addConPacket(self, packet):
        if packet.type != "CON":
            raise ProtocolError("Packet type is not CON.")
        self.body = self.body + packet.body
        self.acknowledged = False
        self.updateMessageState()

    def setSequence(self, sequence):
        self.sequence = sequence

    def getPackets(self):
        self.body = self.body[0:-2] + self.calculateChecksum(self.body[0:-2])

        data = struct.pack(">I", self.address)

        if self.type == MessageType.PDM:
            data += b"\xA0"
            data += struct.pack(">I", self.address)
        else:
            data += b"\xE0"
            data += struct.pack(">I", 0)

        data += bytes([(self.unknownBits << 6) | (self.sequence << 2) | ((self.length >> 8) & 0x03)])
        data += bytes([(self.length & 0xff)])

        maxLength = 25
        bodyToWrite = self.body[:-2]
        crc = self.body[-2:]

        lenToWrite = min(maxLength, len(bodyToWrite))
        data += bodyToWrite[0:lenToWrite]
        bodyToWrite = bodyToWrite[lenToWrite:]

        maxLength = 31
        conData = []
        while len(bodyToWrite) > 0:
            lenToWrite = min(maxLength, len(bodyToWrite))
            cond = struct.pack(">I", self.address)
            cond += b"\x80"
            cond += bodyToWrite[0:lenToWrite]
            bodyToWrite = bodyToWrite[lenToWrite:]
            conData.append(cond)

        packets = [Packet.from_data(data)]
        for cond in conData:
            packets.append(Packet.from_data(cond))

        packets[-1].data += crc
        return packets

    def updateMessageState(self):
        if len(self.body) == self.length + 2:
            if self.verifyChecksum():
                self.state = MessageState.Complete
            else:
                self.state = MessageState.Invalid
                raise ProtocolError("Message checksum failed")
        elif len(self.body) < self.length + 2:
            self.state = MessageState.Incomplete
        else:
            self.state = MessageState.Invalid
            raise ProtocolError("Message data exceeds announced message length")

    def verifyChecksum(self):
        checksum = self.calculateChecksum(self.body[:-2])
        return checksum == self.body[-2:]

    def calculateChecksum(self, body):
        a = struct.pack(">I", self.address)
        b0 = (self.unknownBits << 6) | (len(body) >> 8 & 0x03) | (self.sequence & 0x0f) << 2
        b1 = len(body) & 0xff
        crcBody = a + bytes([b0, b1]) + body
        crcVal = crc16(crcBody)
        return bytes([crcVal >> 8, crcVal & 0xff])

    def getContents(self):
        ptr = 0
        contents = []
        while ptr < self.length:
            contentType = self.body[ptr]
            if contentType == 0x1d:
                contentLength = len(self.body) - 3
                ptr -= 1
            else:
                contentLength = self.body[ptr+1]
            content = self.body[ptr+2:ptr+2+contentLength]
            contents.append((contentType, content))
            ptr += 2 + contentLength
        return contents

    def __str__(self):
        s = "%s %s %s\n" % (self.type, self.sequence, self.unknownBits)
        for contentType, content in self.getContents():
            s += "Type: %02x " % contentType
            if contentType == 0x1a:
                s += separate(content, [4, 1, 2, 1, 2]) + "\n"
            elif contentType == 0x16:
                s += separate(content, [1, 1, 2, 4, 2, 4]) + "\n"
            else:
                s += "Body: %s\n" % (content.hex())
        return s


def separate(content, separations):
    r = ""
    ptr = 0
    s = 0
    for s in separations:
        if r != "":
            r += " "
        r += content[ptr:ptr+s].hex()
        ptr += s
    else:
        while ptr<len(content)-1:
            r += " "
            r += content[ptr:ptr+s].hex()
            ptr += s
    return r

