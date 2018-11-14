from radio import Radio, RadioMode
from message import Message, MessageState

class Sniffer:
    def __init__(self, pktHandler, msgHandler, errHandler, lot = None, tid = None, address = None):
        self.pktHandler = pktHandler
        self.messageHandler = msgHandler
        self.errHandler = errHandler
        self.lot = lot
        self.tid = tid
        self.address = address
        self.nextPacketSequence = None
        self.packetSequences = dict()
        self.address = None
        self.message = None
        self.radio = Radio(0)

    def start(self):
        self.radio.start(packetReceivedCallback = self.protocolHandler, radioMode = RadioMode.Sniffer)

    def stop(self):
        self.radio.stop()

    def raiseErrHandler(self, errmsg):
        if self.errHandler is not None:
            self.errHandler(errmsg)

    def raiseMsgHandler(self, msg):
        if self.messageHandler is not None:
            self.messageHandler(msg)

    def raisePktHandler(self, pkt):
        if self.pktHandler is not None:
            self.pktHandler(pkt)

    def protocolHandler(self, packet):
        self.raisePktHandler(packet)
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
                self.raiseErrHandler("Warning: Sequencing error. Expected sequence: 0x%02x Received: 0x%02x" % (self.nextPacketSequence, packet.sequence))
            self.nextPacketSequence = (packet.sequence + 1) % 32

            if self.address is None:
                self.address = packet.address

            if self.address != packet.address:
                self.raiseErrHandler("Warning: address mismatch, expected address: %s received: %s, switching to new address" % (self.address, packet.address))
                self.address = packet.address

            if packet.type == "PDM" or packet.type == "POD":
                if self.message is not None:
                    if self.message.type != packet.type:
                        if not self.message.acknowledged:
                            self.message.acknowledged = True
                        else:
                            self.raiseErrHandler("Warning: ACK received for already acknowledged message")
                    self.raiseMsgHandler(self.message)
                self.message = Message.fromPacket(packet)
            elif packet.type == "CON":
                if self.message is not None:
                    if self.message.state == MessageState.Incomplete:
                        self.message.addConPacket(packet)
                    else:
                        self.raiseErrHandler("Error: Unexpected packet type CON, message abandoned")
                        self.raiseMsgHandler(self.message)
                        self.message = None
                else:
                    self.raiseErrHandler("Error: CON packet received without previous message")
            else:
                if self.message is not None:
                    if not self.message.acknowledged:
                        self.message.acknowledged = True
                    else:
                        self.raiseErrHandler("Warning: ACK received for already acknowledged message")

                    if self.message.state == MessageState.Complete:
                        self.raiseMsgHandler(self.message)
                        self.message = None
                else:
                    self.raiseErrHandler("Warning: ACK received without a previous message")
