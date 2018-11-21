from random import randint
import threading
import manchester
import crc
from packet import Packet
from enum import Enum
import logging
from message import Message, MessageState
from Queue import Queue, Empty

from rflib import (RfCat, ChipconUsbTimeoutException, MOD_2FSK, SYNCM_CARRIER_16_of_16, SYNCM_NONE,
                    MFMCFG1_NUM_PREAMBLE0, MFMCFG1_NUM_PREAMBLE_2, SYNCM_CARRIER)

class CommunicationError(Exception):
    pass

class ProtocolError(Exception):
    pass

class RadioMode(Enum):
    Sniffer = 0,
    Pdm = 1,
    Relay = 2

class Radio:
    def __init__(self, usbInterface = 0, msgSequence = 0, pktSequence = 0):
        self.stopRadioEvent = threading.Event()
        self.usbInterface = usbInterface
        self.manchester = manchester.ManchesterCodec()
        self.messageSequence = msgSequence
        self.packetSequence = pktSequence

    def __logPacket(self, p):
        logging.debug("Packet received: %s" % p)

    def __logMessage(self, msg):
        logging.debug("Message received: %s" % msg)

    def start(self):
        logging.debug("starting radio in %s" % radioMode)
        self.lastPacketReceived = None
        self.responseTimeout = 1000
        self.radioMode = radioMode
        self.rfc = RfCat(self.usbInterface, debug=False)
        self.rfc.setFreq(433.91e6)
        self.rfc.setMdmModulation(MOD_2FSK)
        self.rfc.setMdmDeviatn(26370)
        self.rfc.setPktPQT(1)
        self.rfc.setEnableMdmManchester(False)
        self.rfc.setMdmDRate(40625)
        self.rfc.setRFRegister(0xdf18, 0x70)
        self.rfc.setMdmSyncMode(SYNCM_CARRIER_16_of_16)
        self.rfc.setMdmNumPreamble(MFMCFG1_NUM_PREAMBLE_2)
        self.rfc.setMdmSyncWord(0xa55a)
        self.rfc.makePktFLEN(80)

    def stop(self):
        self.rfc.cleanup()

    def __receive(self, timeout):
        rfdata = None
        try:
            rfdata = self.rfc.RFrecv(timeout = timeout)
        except ChipconUsbTimeoutException:
            rfdata = None
        return rfdata

    def __send(self, data):
        success = False
        try:
            self.rfc.RFxmit(data)
        except ChipconUsbTimeoutException:
            pass
        return success

    def sendRequestToPod(self, message, responseHandler = None):
        while True:
            message.sequence = self.messageSequence
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
                    raise CommunicationError()

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

    def __sendPacketUntilQuiet(self, packetToSend, trackSequencing = True):
        if trackSequencing:
            packetToSend.setSequence(self.packetSequence)
        logging.debug("SENDING PACKET expecting quiet: %s" % packetToSend)
        data = packetToSend.data
        data += chr(crc.crc8(data))
        data = self.manchester.encode(data)
        sendTimes = 0
        for i in range(0, 10):
            self.__send(data)
            rfData = self.__receive(timeout = 500)
            sendTimes += 1
            if rfData is not None:
                p = self.__getPacket(rfData)
                if p is not None and p.address == packetToSend.address:
                    continue
            if trackSequencing:
                self.packetSequence = (self.packetSequence + 1) % 32
            return
    def __sendPacketAndGetPacketResponse(self, packetToSend, expectedType, trackSequencing = True):
        expectedAddress = packetToSend.address
        longTimeout = 0
        loopies = 0
        while loopies < 3:
            if trackSequencing:
                packetToSend.setSequence(self.packetSequence)
            logging.debug("SENDING PACKET expecting response: %s" % packetToSend)
            data = packetToSend.data
            data += chr(crc.crc8(data))
            data = self.manchester.encode(data)
            retries = 0

            if trackSequencing:
                expectedSequence = (packetToSend.sequence + 1) % 32
            while retries < 20:
                retries += 1
                self.__send(data)
                if longTimeout == 0:
                    tmout = randint(1000, 1300)
                else:
                    tmout = longTimeout
                    longTimeout = 0
                rfData = self.__receive(timeout = tmout)
                if rfData is not None:
                    p = self.__getPacket(rfData)
                    if p is not None and p.address == expectedAddress:
                        logging.debug("RECEIVED PACKET: %s" % p)
                        if (expectedType is None and (self.lastPacketReceived is None or self.lastPacketReceived.data != p.data)) \
                            or (expectedType is not None and p.type == expectedType and p.sequence == expectedSequence):
                            logging.debug("received packet accepted" % p)
                            if trackSequencing:
                                self.packetSequence = (p.sequence + 1) % 32
                            self.lastPacketReceived = p
                            return p
                        else:
                            logging.debug("received packet does not match expected criteria" % p)
                        loopies += 1
                        if loopies == 1:
                            longTimeout = randint(4700,5300)
                        else:
                            longTimeout = randint(9700, 10300)
                            if trackSequencing:
                                logging.debug("moving sequence backwards as there seems to be a problem")
                                self.packetSequence = (self.packetSequence + 31) % 32
                        break
        raise ProtocolError()

    def __getPacket(self, rfdata):
        data, timestamp = rfdata
        data = self.manchester.decode(data)
        if data is not None and len(data) > 1:
            calc = crc.crc8(data[0:-1])
            if ord(data[-1]) == calc:
                return Packet(timestamp, data[:-1])
        return None