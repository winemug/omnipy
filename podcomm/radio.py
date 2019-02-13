from random import randint
import threading

from podcomm import crc
from podcomm.rileylink import RileyLink, RileyLinkError, Response
from .packet import Packet
import logging
from .message import Message, MessageState
import time


class RadioError(Exception):
    def __init__(self, message="Unknown"):
        self.error_message = message


class ProtocolError(Exception):
    def __init__(self, message="Unknown"):
        self.error_message = message


class Radio:
    def __init__(self, msg_sequence = 0, pkt_sequence = 0):
        self.stopRadioEvent = threading.Event()
        self.messageSequence = msg_sequence
        self.packetSequence = pkt_sequence
        self.lastPacketReceived = None
        self.responseTimeout = 1000
        self.rileyLink = RileyLink()
        self.rileyLink.connect()
        self.rileyLink.init_radio()
        self.rileyLink.disconnect()

    def __logPacket(self, p):
        logging.debug("Packet received: %s" % p)

    def __logMessage(self, msg):
        logging.debug("Message received: %s" % msg)

    def sendRequestToPod(self, message, responseHandler = None):
        try:
            self.rileyLink.connect()
            self.rileyLink.init_radio()
            while True:
                time.sleep(3)
                message.setSequence(self.messageSequence)
                logging.debug("SENDING MSG: %s" % message)
                packets = message.getPackets()
                received = None

                for i in range(0, len(packets)):
                    packet = packets[i]
                    if i == len(packets)-1:
                        exp = "POD"
                    else:
                        exp = "ACK"
                    received = self.__sendPacketAndGetPacketResponse(packet, exp)
                    if received is None:
                        raise ProtocolError()

                podResponse = Message.fromPacket(received)
                if podResponse is None:
                    raise ProtocolError()

                while podResponse.state == MessageState.Incomplete:
                    ackPacket = Packet.Ack(message.address, False)
                    received = self.__sendPacketAndGetPacketResponse(ackPacket, "CON")
                    podResponse.addConPacket(received)

                if podResponse.state == MessageState.Invalid:
                    raise ProtocolError()

                logging.debug("RECEIVED MSG: %s" % podResponse)
                respondResult = None
                if responseHandler is not None:
                    respondResult = responseHandler(message, podResponse)

                if respondResult is None:
                    ackPacket = Packet.Ack(message.address, True)
                    self.__sendPacketUntilQuiet(ackPacket)
                    self.messageSequence = (podResponse.sequence + 1) % 16
                    return podResponse
                else:
                    message = respondResult
        except:
            raise
        finally:
            self.rileyLink.disconnect()

    def __sendPacketUntilQuiet(self, packetToSend, trackSequencing = True):
        if trackSequencing:
            packetToSend.setSequence(self.packetSequence)
        logging.debug("SENDING PACKET expecting quiet: %s" % packetToSend)
        data = packetToSend.data
        data += bytes([crc.crc8(data)])

        while True:
            self.rileyLink.send_final_packet(data, 10, 25, 42)
            timed_out = False
            received = None
            try:
                received = self.rileyLink.get_packet(300)
            except RileyLinkError as rle:
                if rle.response_code != Response.RX_TIMEOUT:
                    raise rle
                else:
                    timed_out = True

            if not timed_out and received is not None:
                p = self.__getPacket(received)
                if p is not None:
                    continue

            if trackSequencing:
                self.packetSequence = (self.packetSequence + 1) % 32
            return

    def __sendPacketAndGetPacketResponse(self, packetToSend, expectedType, trackSequencing = True, retry_count = 3):
        expectedAddress = packetToSend.address
        retries = retry_count
        while retries > 0:
            if trackSequencing:
                packetToSend.setSequence(self.packetSequence)
            logging.debug("SENDING PACKET expecting response: %s" % packetToSend)
            data = packetToSend.data
            data += bytes([crc.crc8(data)])
            received = self.rileyLink.send_and_receive_packet(data, 0, 0, 300, 30, 127)
            p = self.__getPacket(received)
            if p is not None and p.address == expectedAddress:
                logging.debug("RECEIVED PACKET: %s" % p)
                packet_accepted = False
                if expectedType is None:
                    if self.lastPacketReceived is None:
                        packet_accepted = True
                    else:
                        if self.lastPacketReceived.data != p.data:
                            packet_accepted = True
                else:
                    if p.type == expectedType:
                        packet_accepted = True

                if packet_accepted:
                    logging.debug("received packet accepted. %s" % p)
                    if trackSequencing:
                        self.packetSequence = (p.sequence + 1) % 32
                    self.lastPacketReceived = p
                    return p
                else:
                    logging.debug("received packet does not match expected criteria. %s" % p)
                    if trackSequencing:
                        self.packetSequence = (p.sequence + 1) % 32
            retries = retries - 1
            logging.info("Retries left: %d" % retries)


    def __getPacket(self, data):
        if data is not None and len(data) > 2:
            calc = crc.crc8(data[2:-1])
            if data[-1] == calc:
                return Packet(0, data[2:-1])
        return None
