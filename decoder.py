
import queue
import binascii
from enum import Enum
from podcomm/crc import crc16
from podcomm/message import Message, MessageState
from podcomm/packet import Packet

class Decoder():
    def __init__(self):
        self.nextSequence = None
        self.sequences = dict()
        self.address = None
        self.message = None

    def receivePacket(self, timestamp, data):
        packet = Packet(timestamp, data)
        if packet.valid:
            if packet.type in self.sequences:
                lastSeq = self.sequences[packet.type]
                if packet.sequence == lastSeq:
                    #ignoring repeat packets
                    return
            self.sequences[packet.type] = packet.sequence
            if self.nextSequence is None:
                self.nextSequence = packet.sequence
            if self.nextSequence != packet.sequence:
                print "Warning: Sequencing error. Expected sequence: 0x%2x Received: 0x%2x" % (self.nextSequence, packet.sequence)
            self.nextSequence = (packet.sequence + 1) % 32

            if self.address is None:
                self.address = packet.address

            if self.address != packet.address:
                print "Warning: address mismatch, expected address: %s received: %s, switching to new address" % (self.address, packet.address)
                self.address = packet.address

            if packet.type == "PDM" or packet.type == "POD":
                if self.message is not None:
                    if self.message.type != packet.type:
                        if not self.message.acknowledged:
                            self.message.acknowledged = True
                        else:
                            print "Warning: ACK received for already acknowledged message"
                    print self.message
                self.message = Message.fromPacket(packet)
            elif packet.type == "CON":
                if self.message is not None:
                    if self.message.state == MessageState.Incomplete:
                        self.message.addConPacket(packet)
                    else:
                        print "Error: Unexpected packet type CON, message abandoned"
                        print self.message
                        self.message = None
                else:
                    print "Error: CON packet received without previous message"
            else:
                if self.message is not None:
                    if not self.message.acknowledged:
                        self.message.acknowledged = True
                    else:
                        print "Warning: ACK received for already acknowledged message"

                    if self.message.state == MessageState.Complete:
                        print self.message
                        self.message = None
                else:
                    print "Warning: ACK received without a previous message"