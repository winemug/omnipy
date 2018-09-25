import threading
import radio
from message import Message, MessageState
from enum import Enum
from packet import Packet
import Queue

class Pod:
    def __init__(self, msgHandler, errHandler, lot, tid, address = None):
        self.messageHandler = msgHandler
        self.errorHandler = errHandler
        self.lot = lot
        self.tid = tid
        self.address = address
        self.pdmMessage = None
        self.radio = radio.Radio(0)

    def start(self):
        self.messageSequence = None
        self.responding = False
        self.respondToPacket = None
        self.responsePacket = None
        self.responseQueue = Queue.Queue()
        self.lastReceivedPacketSequence = None
        self.radio.start(self.protocolHandler, listenAlways = True)

    def stop(self):
        self.radio.stop()

    def getNextSequence(self, sequence):
        return (sequence + 1) % 32

    def sendAckPacket(self, respondToPacket):
        ackPacket = Packet.Ack(self.address, self.getNextSequence(respondToPacket.sequence), True)
        self.respondToPacket = respondToPacket
        self.responsePacket = ackPacket
        self.radio.send(ackPacket)

    def sendMessage(self, respondToPacket, message):
        packets = message.getPackets(self.getNextSequence(self.messageSequence))
        if len(packets) > 1:
            for packet in packets[1:]:
                self.responseQueue.put(packet)

        self.respondToPacket = respondToPacket
        self.responsePacket = packets[0]
        self.responsePacket.setSequence(self.getNextSequence(respondToPacket.sequence))
        self.radio.send(self.responsePacket)

    def protocolHandler(self, packet):
        if not packet.valid:
            return

        if self.responding:
            if packet.sequence == self.respondToPacket.sequence and packet.type == self.respondToPacket.type:
                self.radio.send(self.responsePacket)
                return
            else:
                if not self.responseQueue.empty:
                    if packet.type != "ACK":
                        self.errorHandler() #tbd
                        self.responseQueue = Queue.Queue() # reset queue
                        # continue with message
                    else:
                        self.responsePacket = responseQueue.get()
                        self.respondToPacket = packet
                        self.responsePacket.setSequence(self.getNextSequence(packet.sequence))
                        self.radio.send(self.responsePacket)
                        return

            self.responding = False

        if self.lastReceivedPacketSequence == None:
            self.lastReceivedPacketSequence = packet.sequence
        elif packet.sequence == self.lastReceivedPacketSequence:
            return

        if self.address is None:
            self.address = packet.address
        elif self.address != packet.address:
            self.errorHandler() #tbd
            self.address = packet.address

        if self.pdmMessage is None and packet.type == "PDM":
            self.pdmMessage = Message.fromPacket(packet)
            self.messageSequence = self.pdmMessage.sequence
        elif self.pdmMessage is not None and self.pdmMessage.state == MessageState.Incomplete and packet.type == "CON":
            self.pdmMessage.addConPacket(packet)
        else:
            self.errorHandler() #tbd
            self.pdmMessage = None
            return

        if self.pdmMessage.state == MessageState.Incomplete:
            #auto ack partial pdm message
            self.sendAckPacket(packet)

        elif self.pdmMessage.state == MessageState.Complete:
            #we have a complete pdm message, either respond with ACK or POD message
            podMessage = self.messageHandler(self.pdmMessage)
            if podMessage is None:
                self.sendAckPacket(packet)
            else:
                self.sendMessage(packet, podMessage)
