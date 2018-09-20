import queue
import binascii
from enum import Enum
from crc import crc16

class SessionBuilder():
    def __init__(self):
        self.sessions = []
        self.activeSession = MessageSession()
    
    def addPacket(self, timestamp, data):
        p = Packet(timestamp, data)
        if p.valid:
            if self.activeSession.add(timestamp, p):
                self.sessions.append(self.activeSession)
                self.activeSession = MessageSession()
            else:
                # look for previously incomplete sessions?
                # if not, start a new session
                pass

class SessionState(Enum):
    PdmMessageExpected = 0,
    PodMessageExpected = 1,
    PdmConExpected = 2,
    PodConExpected = 3,
    PodAckExpected = 4,
    PdmAckExpected = 5

# pdm talks, pod responds

class MessageSession():
    def __init__(self):
        self.packets = []
        self.state = SessionState.PdmMessageExpected
        self.nextSequence = None
        self.sequences = dict()
        self.address = None

    def add(self, timestamp, packet):

        if self.address is not None and packet.address != self.address:
            print "ERROR: Packet address mismatch, Expected: %s Got: %s" % self.address, packet.address
            return False

        if packet.type in self.sequences:
            lastSeq = self.sequences[packet.type]
            if packet.sequence == lastSeq:
                return True

        self.sequences[packet.type] = packet.sequence
        if self.nextSequence is None:
            self.nextSequence = packet.sequence

        if self.nextSequence != packet.sequence:
            print "WARNING: Expected packet sequence 0x%02x Got: 0x%02x, resetting sequence" % (self.nextSequence, packet.sequence)

        self.nextSequence = (packet.sequence + 1) % 32

        if self.state == SessionState.PdmMessageExpected:
            return self.addFirstPacket(timestamp, packet)
        # elif self.state == MessageSessionState.PdmPartialMessageReceived or self.state == MessageSessionState.PdmMessageReceived:
        #     return self.addAcknowledgement(timestamp, packet, "POD")
        # elif self.state == MessageSessionState.PdmPartialMessageAcknowledged:
        #     return self.addPartialMessage(timestamp, packet, "PDM")
        # elif self.state == MessageSessionState.PodPartialMessageReceived or self.state == MessageSessionState.PodMessageReceived:
        #     return self.addAcknowledgement(timestamp, packet, "POD")
        # elif self.state == MessageSessionState.PodPartialMessageAcknowledged:
        #     return self.addPartialMessage(timestamp, packet, "POD")
        return True

    def addFirstPacket(self, timestamp, packet):
        if packet.type != "PDM":
            # cannot start a session without a pdm packet
            print "ERROR: Expecting a PDM type packet to start session, got packet type: %s" % packet.type
            return False
        
        self.address = packet.address
        self.messageLength = packet.messageLength
        self.messageSequence = packet.messageSequence
        self.unknownTwoBits = packet.unknownTwoBits

        if len(packet.body) < self.pdmMessageLength + 2:
            self.partialMessage = packet.body
            self.state = SessionState.PodAckExpected
        elif len(packet.body) == self.pdmMessageLength + 2:
            if self.verifyCrc(packet.body):
                self.pdmMessage = packet.body
            else:
                print "ERROR: CRC verification failed for message: %s" bin.hexlify(packet.body)
                return False

        self.pdmPacketSequence = packet.sequence
        self.started = timestamp
        return True

    def addAcknowledgement(self, timestamp, packet, expectedType):
        if (packet.type == expectedType):
            if self.state == MessageSessionState.PdmMessageReceived:
                self.state = MessageSessionState.PdmMessageAcknowledged

        if packet.type != "ACK":
            return False

        if self.state == MessageSessionState.PdmPartialMessageReceived:
            self.state = MessageSessionState.PdmPartialMessageAcknowledged
        elif self.state == MessageSessionState.PdmMessageReceived:
            self.state = MessageSessionState.PdmMessageAcknowledged
        elif self.state == MessageSessionState.PodPartialMessageReceived:
            self.state = MessageSessionState.PodPartialMessageAcknowledged
        elif self.state == MessageSessionState.PodMessageReceived:
            self.state = MessageSessionState.PodMessageAcknowledged

    def addPodMessage(self, timestamp, packet):
        pass

    def addPartialMessage(self, timestamp, packet, expectedType):
        if packet.type != "CON":
            return False



    def verifyCrc(self, messageBody):
        if len(messageBody < 3):
            return False

        message = messageBody[0:-2]
        crc = ord(messageBody[-2:])
        return crc == crc16(message)

class Message():
    def __init__(self, timestamp, packet):
        self.unknownTwoBits = packet.b9 >> 6


class Packet():
    def __init__(self, timestamp, data):
        self.valid = False
        if len(data) < 5:
            return

        self.address = binascii.hexlify(data[0:4])

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
            return

        if self.type == "PDM" or self.type == "POD":
            if len(data < 12):
                return
            self.b9 = ord(data[9])
            self.messageLength = ord(data[10]) | (self.b9 & 3)<<8
            self.address2 = binascii.hexlify(data[5:9])
            self.messageSequence = (b9 & 0x3C) >> 2
            self.body = binascii.hexlify(data[11:])
        elif self.type == "ACK":
            if len(data) != 9:
                return
            self.address2 = binascii.hexlify(data[5:9])
            if self.address2 == self.address:
                self.ackFinal = False
            elif self.address2 == "00000000":
                self.ackFinal = True
            else:
                return
        elif self.type == "CON":
            if len(data) < 6:
                return
            self.body = binascii.hexlify(data[5:])


