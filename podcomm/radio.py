import threading
import manchester
import crc
from packet import Packet
from enum import Enum
import logging
from message import Message, MessageState

from rflib import (RfCat, ChipconUsbTimeoutException, MOD_2FSK, SYNCM_CARRIER_16_of_16, SYNCM_NONE,
                    MFMCFG1_NUM_PREAMBLE0, MFMCFG1_NUM_PREAMBLE_2)

class CommunicationError(Exception):
    pass

class ProtocolError(Exception):
    pass

class RadioMode(Enum):
    Sniffer = 0,
    Pdm = 1,
    Pod = 2

class Radio:
    def __init__(self, usbInterface, msgSequence = 0, pktSequence = 0):
        self.stopRadioEvent = threading.Event()
        self.usbInterface = usbInterface
        self.manchester = manchester.ManchesterCodec()
        self.messageSequence = msgSequence
        self.packetSequence = pktSequence

    def __logPacket(self, p):
        logging.debug("Packet received: %s", p)

    def __logMessage(self, msg):
        logging.debug("Message received: %s", msg)
        return None

    def start(self, packetReceivedCallback = None, messageCallback = None, radioMode = RadioMode.Sniffer, address = None, sendPacketLength = 128):
        logging.debug("starting radio in %s", radioMode)
        self.lastPacketReceived = None
        self.addressToCheck = address
        self.responseTimeout = 1000
        self.radioMode = radioMode
        self.radioPacketLength = sendPacketLength
        self.__initializeRfCat()

        if packetReceivedCallback is None:
            self.packetReceivedCallback = self.__logPacket
        else:
            self.packetReceivedCallback = packetReceivedCallback

        if messageCallback is None:
            self.messageCallback = self.__logMessage
        else:
            self.messageCallback = packetReceivedCallback

        if radioMode == RadioMode.Sniffer:
            self.radioThread = threading.Thread(target = self.__snifferLoop)
            self.radioThread.start()
        elif radioMode == RadioMode.Pod:
            self.radioThread = threading.Thread(target = self.__podLoop)
            self.radioThread.start()

    def stop(self):
        if self.radioMode == RadioMode.Sniffer or self.radioMode == RadioMode.Pod:
            self.stopRadioEvent.set()
            self.radioThread.join()
        self.rfc.cleanup()

    def __initializeRfCat(self):
        rfc = RfCat(self.usbInterface, debug=False)
        rfc.setModeIDLE()
        rfc.setFreq(433.91e6)
        rfc.setMdmModulation(MOD_2FSK)
        rfc.setMdmDeviatn(26370)
        rfc.setPktPQT(1)
        rfc.setEnableMdmManchester(False)
        rfc.setMdmDRate(40625)
        rfc.setRFRegister(0xdf18, 0x70)
        self.rfc = rfc

    def __rfEnterTX(self):
        success = False
        while not success:
            try:
                self.rfc.setMdmSyncMode(SYNCM_NONE)
                self.rfc.makePktFLEN(self.radioPacketLength)
                self.rfc.setMdmNumPreamble(MFMCFG1_NUM_PREAMBLE0)
                self.rfc.setModeTX()
                success = True
            except ChipconUsbTimeoutException:
                success = False

# AB3C actual sync word before manchester encoding
# after encoding: 6665a55a
# actual encoded packet looks like this:

# 0x6665 (repeated > 200 times) 0xa55a 

# possible syncwords:
# 0x5a
# 0xa55a
# 0x65a55a
# 0x6665a55a
# 0x656665a55a
# 0x66656665a55a
# etc..
    def __rfEnterRX(self):
        success = False
        while not success:
            try:
                self.rfc.setMdmSyncMode(SYNCM_CARRIER_16_of_16)
                self.rfc.makePktFLEN(80)
                self.rfc.setMdmNumPreamble(MFMCFG1_NUM_PREAMBLE_2)
                self.rfc.setMdmSyncWord(0xa55a)
                self.rfc.setModeRX()
                success = True
            except ChipconUsbTimeoutException:
                success = False

    def __rfEnterIdle(self):
        success = False
        while not success:
            try:
                self.rfc.setModeIDLE()
                success = True
            except ChipconUsbTimeoutException:
                success = False


    def __snifferLoop(self):
        self.__rfEnterRX()
        while not self.stopRadioEvent.wait(0):
            try:
                rfdata = self.__receive(1000)
                if rfdata is not None:
                    p = self.__getPacket(rfdata)
                    if p is not None:
                        if self.lastPacketReceived is None or self.lastPacketReceived.sequence != p.sequence:
                            self.lastPacketReceived = p
                            self.packetReceivedCallback(p)
            except ChipconUsbTimeoutException:
                pass

    def __podLoop(self):
        pass

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

    def sendPdmMessageAndGetPodResponse(self, message):
        packets = message.getPackets()
        self.messageSequence = (message.sequence + 1) % 16
        received = None
        for i in range(0, len(packets)):
            packet = packets[i]
            packet.setSequence(self.packetSequence)
            self.packetSequence = (self.packetSequence + 2) % 32
            received = self.__sendPacketAndGetPacketResponse(packet)
            if received is None:
                raise CommunicationError()
            if i < len(packets) -1:
                if received.type != "ACK":
                    raise ProtocolError()

        if received.type != "POD":
            raise ProtocolError()

        podResponse = Message.fromPacket(received)
        if podResponse.sequence != self.messageSequence:
            raise ProtocolError()

        self.messageSequence = (self.messageSequence + 1) % 32

        while podResponse.state == MessageState.Incomplete:
            ackPacket = Packet.Ack(message.address, self.packetSequence, False)
            self.packetSequence = (self.packetSequence + 2) % 32
            received = self.__sendPacketAndGetPacketResponse(ackPacket, 30)
            if received is None or received.type != "CON":
                raise CommunicationError()
            podResponse.addConPacket(received)

        if podResponse.state == MessageState.Invalid:
            raise ProtocolError()

        ackPacket = Packet.Ack(message.address, self.packetSequence, False)
        self.__sendPacket(ackPacket)

        return podResponse

    def __sendPacket(self, packetToSend, sendTimes = 20):
        data = packetToSend.data
        data += chr(crc.crc8(data))
        data = self.manchester.encode(data, self.radioPacketLength)
        self.__rfEnterTX()
        while sendTimes > 0:
            self.__send(data)
            sendTimes -= 1

    def __sendPacketAndGetPacketResponse(self, packetToSend, sendTimes = 20):
        data = packetToSend.data
        data += chr(crc.crc8(data))
        data = self.manchester.encode(data, self.radioPacketLength)
        retries = 0
        expectedSequence = (packetToSend.sequence + 1) % 32
        expectedAddress = packetToSend.address
        while retries < sendTimes:
            retries += 1
            self.__rfEnterTX()
            self.__send(data)
            self.__rfEnterRX()
            rfData = self.__receive(timeout = 100)
            if rfData is not None:
                p = self.__getPacket(rfData)
                if p is not None:
                    if p.sequence == expectedSequence and p.address == expectedAddress:
                        return p
        return None

    def __getPacket(self, rfdata):
        data, timestamp = rfdata
        data = self.manchester.decode(data)
        if data is not None and len(data) > 1:
            calc = crc.crc8(data[0:-1])
            if ord(data[-1]) == calc:
                return Packet(timestamp, data[:-1])
        return None