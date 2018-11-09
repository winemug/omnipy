import time
import datetime
import threading
import Queue
import array
import manchester
import crc
import packet
import enum.Enum

from rflib import (RfCat, ChipconUsbTimeoutException, MOD_2FSK, SYNCM_CARRIER_16_of_16,
                    MFMCFG1_NUM_PREAMBLE0, MFMCFG1_NUM_PREAMBLE_2)

class RadioMode(Enum):
    Sniffer,
    Pdm
    Pod

class Radio:
    def __init__(self, usbInterface):
        self.stopRadioEvent = threading.Event()
        self.usbInterface = usbInterface
        self.manchester = manchester.ManchesterCodec()

    def start(self, recvCallback, radioMode = RadioMode.Sniffer):
        self.recvCallback = recvCallback
        self.sendRequested = threading.Event()
        self.sendComplete = threading.Event()
        self.recvQueue = Queue.Queue()
        self.responseTimeout = 1000
        self.radioMode = radioMode
        self.radioThread = threading.Thread(target = self.radioLoop)
        self.radioThread.start()

    def stop(self):
        self.stopRadioEvent.set()
        self.radioThread.join()

    def sendAndReceive(self, packet, expectResponse, responseTimeout = 10000):
        self.packetToSend = packet
        self.responseTimeout = responseTimeout
        self.expectResponse = expectResponse
        self.sendRequested.set()
        self.sendComplete.wait()
        self.sendComplete.clear()
        self.sendRequested.clear()
        if expectResponse:
            return self.response

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
        rfc = self.initializeRfCat()

        if self.radioMode == RadioMode.Sniffer:
            pp = threading.Thread(target = self.recvProcessor)
            pp.start()

        while not self.stopRadioEvent.wait(0):
            if self.radioMode == RadioMode.Pdm:
                if self.sendRequested.wait(3000):
                    data = self.packetToSend.data
                    data += chr(crc.crc8(data))
                    data = self.manchester.encode(data)

                    rfc.RFxmit(data)
                    recvdata = rfc.RFrecv(timeout = self.responseTimeout)

                    self.sendComplete.set()

                pass
            elif self.radioMode == RadioMode.Pod:
                self.receive(timeout = 3000)
                if recvdata is not None:
                    self.recvQueue.put(recvdata)
            else:
                self.receive(timeout = 3000)
                if recvdata is not None:
                    self.recvQueue.put(recvdata)

        rfc.cleanup()

        if self.radioMode == RadioMode.Sniffer:
            self.recvQueue.put(None)
            self.recvQueue.task_done()
            pp.join()

    def receive(self, receiveTimeout):
        try:
            data = rfc.RFrecv(timeout = receiveTimeout)
        except ChipconUsbTimeoutException:
            return None
        return data

    def recvProcessor(self):
        while True:
            rfdata = self.recvQueue.get(block = True)
            if rfdata is None:
                break
                
            data, timestamp = rfdata
            data = self.manchester.decode(data)
            if data is not None and len(data) > 1:
                calc = crc.crc8(data[0:-1])
                if ord(data[-1]) == calc:
                    p = packet.Packet(timestamp, data[:-1])
                    self.recvCallback(p)

