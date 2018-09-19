import queue
import binascii
from enum import Enum

class SessionBuilder():
    def __init__(self):
        self.sessions = []
        self.activeSession = MessageSession()
    
    def addPacket(self, timestamp, data):
        p = Packet(timestamp, data)
        if p.valid:
            if self.activeSession.add(p):
                self.sessions.append(self.activeSession)
                self.activeSession = MessageSession()
            else:
                # look for previously incomplete sessions?
                # if not, start a new session
                pass

class MessageSessionState(Enum):
    Initialized = 0,
    PdmPartialMessageReceived = 1,
    PdmPartialMessageAcknowledged = 2,
    PdmMessageReceived = 3,
    PdmMessageAcknowledged = 4,
    PodPartialResponseReceived = 5,
    PodPartialResponseAcknowledged = 6,
    PodMessageReceived = 7,
    PodMessageAcknowledged = 8,
    Closed = 9

class MessageSession():
    def __init__(self):
        self.packets = []
        self.closed = False
        self.state = MessageSessionState.Initialized

    def add(self, packet):
        return True

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
            b9 = ord(data[9])
            self.messageLength = ord(data[10]) | (b9 & 3)<<8
            self.address2 = binascii.hexlify(data[5:9])
            self.messageSequence = (b9 & 0x3C) >> 2
            self.unknownTwoBits = b9 >> 6
            self.body = binascii.hexlify(data[11:])
        elif self.type == "ACK":
            if len(data) != 9:
                return
            self.address2 = binascii.hexlify(data[5:9])
            if self.address2 == self.address:
                self.ackFrom = "PDM"
            elif self.address2 == "00000000":
                self.ackFrom = "POD"
            else:
                return
        elif self.type == "CON":
            if len(data) < 6:
                return
            self.body = binascii.hexlify(data[5:])


