from .packet import Packet
from .exceptions import ProtocolError
from enum import Enum
from .crc import crc16, crc8
import struct

class MessageState(Enum):
    Incomplete = 0,
    Invalid = 1,
    Complete = 2

class MessageType(Enum):
    PDM = 0,
    POD = 1

# class PodMessage:
#     def __init__(self):
#         self.address = None
#         self.sequence = None
#         self.expect_critical_followup = False
#         self.body_length = 0
#         self.body = None
#
#     def add_packet_data(self, data):
#         t = data[4] >> 5
#         packet_sequence = data[4] & 0b00011111
#         if t == 7:
#             type = "POD"
#             self.address = struct.unpack(">I", data[5:9])[0]
#             self.sequence = (data[10] >> 2) & 0x0f
#             self.expect_critical_followup = (data[10] & 0x80) > 0
#             self.body_length = ((data[10] & 0x03) << 8) | data[11]
#             self.body = data[12:]
#         elif t == 4:
#             self.body += data[5:]
#         else:
#             raise ProtocolError("Packet type invalid")
#
#         return self.body_length == len(self.body) + 2
#
# class PdmMessage:
#     def __init__(self, cmd_type, cmd_body):
#         self.parts = []
#         self.add_part(cmd_type, cmd_body)
#
#     def get_packets(self, packet_address,
#                     first_packet_sequence,
#                     message_sequence,
#                     expect_critical_follow_up=False):
#
#         message_body_len = 0
#         for _, cmd_body, nonce in self.parts:
#             message_body_len += len(cmd_body) + 2
#             if nonce is not None:
#                 message_body_len += 4
#
#         if expect_critical_follow_up:
#             b0 = 0x80
#         else:
#             b0 = 0x00
#
#         b0 |= (message_sequence << 2)
#         b0 |= (message_body_len >> 8) & 0x03
#         b1 = message_body_len & 0xff
#
#         message_body +=  bytes([b0, b1])
#         for cmd_type, cmd_body, nonce in self.parts:
#             if nonce is None:
#                 message_body += bytes([cmd_type, len(cmd_body)])
#             else:
#                 message_body += bytes([cmd_type, len(cmd_body) + 4])
#                 message_body += struct.pack(">I", nonce)
#             message_body += cmd_body
#
#         crc_calculated = crc16(message_body)
#         message_body += struct.pack(">H", crc_calculated)
#
#         index = 0
#         first_packet = True
#         sequence = first_packet_sequence
#         total_body_len = len(message_body)
#         packets = []
#         while(index < total_body_len):
#             packet_data = struct.pack(">I", address)
#             seq_byte = sequence
#
#             if first_packet:
#                 first_packet = False
#                 seq_byte |= 0xa0
#             else:
#                 seq_byte |= 0x80
#
#             packet_data += bytes([seq_byte])
#             to_write = min(25, total_body_len - index)
#             packet_data += message_body[index:index+to_write]
#             packet_data += bytes([crc8(packet_data)])
#             packets.append(packet_data)
#             index += to_write
#             sequence = (sequence + 2) % 32
#
#         return packets
#
#     def add_part(self, cmd_type, cmd_body):
#         part_tuple = cmd_type, cmd_body, None
#         self.parts.append(part_tuple)
#
#     def set_nonce(self, nonce):
#         cmd_type, cmd_body, _ = self.parts[0]
#         self.parts[0] = cmd_type, cmd_body, nonce


class Message:
    def __init__(self, mtype, address, unknownBits=0, sequence=0):
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

        msg_addr = struct.unpack(">I", packet.body[0:4])
        b0 = packet.body[4]
        b1 = packet.body[5]
        unknownBits = b0 >> 6
        sequence = (b0 & 0x3C) >> 2

        m = Message(mType, msg_addr, unknownBits, sequence)
        m.length = ((b0 & 3) <<8) | b1
        m.body = packet.body[6:]
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

