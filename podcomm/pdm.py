import threading
import radio
from message import Message, MessageState

class Pdm:
    def __init__(self, lot = None, tid = None, address = None):
        self.lot = lot
        self.tid = tid
        self.address = address
        self.nextPacketSequence = None
        self.packetSequences = dict()
        self.address = None
        self.message = None
        self.radio = radio.Radio(0)

    def start(self, messageHandler, listenOnly = False):
        self.messageHandler = messageHandler
        if listenOnly:
            self.radio.start(self.recvListenOnlyProtocolHandler)
        else:
            self.radio.start(self.recvProtocolHandler)

    def stop(self):
        self.radio.stop()

    def sendMessage(self, message):
        pass

    def recvProtocolHandler(self):
        pass

    def recvListenOnlyProtocolHandler(self, packet):
        if packet.valid:
            if packet.type in self.packetSequences:
                lastSeq = self.packetSequences[packet.type]
                if packet.sequence == lastSeq:
                    #ignoring repeat packets
                    return
            self.packetSequences[packet.type] = packet.sequence
            if self.nextPacketSequence is None:
                self.nextPacketSequence = packet.sequence
            if self.nextPacketSequence != packet.sequence:
                print "Warning: Sequencing error. Expected sequence: 0x%2x Received: 0x%2x" % (self.nextSequence, packet.sequence)
            self.nextPacketSequence = (packet.sequence + 1) % 32

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
                    self.messageHandler(self.message)
                self.message = Message.fromPacket(packet)
            elif packet.type == "CON":
                if self.message is not None:
                    if self.message.state == MessageState.Incomplete:
                        self.message.addConPacket(packet)
                    else:
                        print "Error: Unexpected packet type CON, message abandoned"
                        self.messageHandler(self.message)
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
                        self.messageHandler(self.message)
                        self.message = None
                else:
                    print "Warning: ACK received without a previous message"
            if self.message is not None and self.message.state == MessageState.Complete:
                self.messageHandler(self.message)