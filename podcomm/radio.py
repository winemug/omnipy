import time
import datetime
import threading
import Queue
import array
import manchester
import crc
import packet
from enum import Enum
import logging

from rflib import (RfCat, ChipconUsbTimeoutException, MOD_2FSK, SYNCM_CARRIER_16_of_16,
                    MFMCFG1_NUM_PREAMBLE0, MFMCFG1_NUM_PREAMBLE_2)

class RadioMode(Enum):
    Sniffer = 0,
    Pdm = 1,
    Pod = 2

class Radio:
    def __init__(self, usbInterface):
        self.stopRadioEvent = threading.Event()
        self.usbInterface = usbInterface
        self.manchester = manchester.ManchesterCodec()

    def start(self, recvCallback = None, radioMode = RadioMode.Sniffer):
        logging.debug("starting radio with %s", radioMode)
        self.recvCallback = recvCallback
        self.recvQueue = Queue.Queue()
        self.responseTimeout = 1000
        self.radioMode = radioMode
        self.rfc = self.initializeRfCat()
        if self.radioMode != RadioMode.Pdm:
            self.radioThread = threading.Thread(target = self.radioLoop)
            self.radioThread.start()

    def stop(self):
        if self.radioMode != RadioMode.Pdm:
            self.stopRadioEvent.set()
            self.radioThread.join()
        self.rfc.cleanup()

    def initializeRfCat(self):
        rfc = RfCat(self.usbInterface, debug=False)
        rfc.setModeIDLE()
        rfc.setFreq(433.91e6)
        rfc.setMdmModulation(MOD_2FSK)
        rfc.setMdmDeviatn(26370)
        rfc.setPktPQT(1)
        rfc.setMdmSyncMode(SYNCM_CARRIER_16_of_16)
        rfc.makePktFLEN(74)
        rfc.setEnableMdmManchester(False)
        rfc.setMdmDRate(40625)
        rfc.setRFRegister(0xdf18, 0x70)
        rfc.setMdmNumPreamble(MFMCFG1_NUM_PREAMBLE0)
        rfc.setMdmSyncWord(0xa55a)
        return rfc

    def radioLoop(self):
        self.rfc.setModeRX()
        while not self.stopRadioEvent.wait(0):
            if self.radioMode == RadioMode.Pod:
                rfdata = self.receive(receiveTimeout = 3000)
                if rfdata is not None:
                    p = self.getPacket(rfdata)
                    while p is not None:
                        logging.debug("Received packet data over radio %s", p)
                        self.packetToSend = self.recvCallback(p)
                        self.responseTimeout = 30000
                        p = self.sendAndReceive(packetToSend)
            else:
                rfdata = self.receive(receiveTimeout = 3000)
                if rfdata is not None:
                    p = self.getPacket(rfdata)
                    if p is not None and self.recvCallback is not None:
                        self.recvCallback(p)

    def sendAndReceive(self, packetToSend, timeout = 30000):
        data = packetToSend.data
        data += chr(crc.crc8(data))
        data = self.manchester.encode(data)
        expectedSequence = (packet.sequence + 1) % 32
        logging.debug("sending packet over radio with sequence %d and will be expecting %d" % (packet.sequence, expectedSequence))
        start = time.clock()
        noResponseCount = 0
        retries = 1
        while time.clock() - start < self.responseTimeout:
            try:
                self.rfc.setModeTX()
                logging.debug("retry %d: sending packet via radio")
                rfc.RFxmit(data)
                logging.debug("retry %d: waiting for packet on radio")
                self.rfc.setModeRX()
                rfdata = rfc.RFrecv(timeout = 100)
                if rfdata is not None:
                    receivedPacket = self.getPacket(rfdata)
                    if receivedPacket is not None and receivedPacket.address == packet.address:
                        if receivedPacket.sequence == expectedSequence:
                            logging.debug("retry %d: received expected packet %s, handing over" % (retries, packet))
                            return receivedPacket
                        else:
                            logging.debug("retry %d: received unexpected packet %s" % (retries, packet))
                            noResponseCount = -1
                    else:
                            logging.debug("retry %d: received data is invalid" % (retries))
                else:
                    logging.debug("retry %d: nothing received" % retries)
            except ChipconUsbTimeoutException:
                logging.debug("retry %d: usb timeout" % retries)
                pass

            noResponseCount += 1
            if noResponseCount > 5:
                logging.debug("retry %d: received %d times no response" % (retries, noResponseCount))
                return None
        raise RuntimeError()

    def receive(self, receiveTimeout):
        try:
            data = self.rfc.RFrecv(timeout = receiveTimeout)
        except ChipconUsbTimeoutException:
            return None
        return data

    def getPacket(self, rfdata):
        data, timestamp = rfdata
        data = self.manchester.decode(data)
        if data is not None and len(data) > 1:
            calc = crc.crc8(data[0:-1])
            if ord(data[-1]) == calc:
                return packet.Packet(timestamp, data[:-1])
        return None