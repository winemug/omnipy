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
import threading

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
        self.lastPacketReceived = None
        self.addressToCheck = None
        self.responseTimeout = 1000
        self.radioMode = radioMode
        self.rfc = self.initializeRfCat()
        self.sendLock = threading.Lock()
        self.dataToSend = None

        self.radioThread = threading.Thread(target = self.radioLoop)
        self.radioThread.start()


    def stop(self):
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
        while not self.stopRadioEvent.wait(0):
            self.rfc.setModeRX()
            rfdata = self.receive(receiveTimeout = 100)
            if rfdata is not None:
                p = self.getPacket(rfdata)
                while p is not None:
                    if self.lastPacketReceived is None or \
                        (self.lastPacketReceived.sequence != p.sequence and self.lastPacketReceived.address != p.address):
                        logging.debug("Received packet data over radio %s", p)
                        self.lastPacketReceived = p
                        self.recvCallback(p)
            self.sendLock.acquire()
            if self.dataToSend is not None:
                if self.sendUntil < time.clock():
                    self.rfc.setModeTX()
                    logging.debug("sending packet via radio: %s", self.packetToSend)
                    rfc.RFxmit(data)
                else:
                    self.dataToSend = None
            self.sendLock.release()

    def send(self, packetToSend, sendFor = 10000):
        self.sendLock.acquire()
        data = packetToSend.data
        data += chr(crc.crc8(data))
        data = self.manchester.encode(data)
        self.dataToSend = data
        self.sendUntil = time.clock() + sendFor
        self.sendLock.release()

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