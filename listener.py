import time
import datetime
import threading
import Queue
import array
import manchester
import crc

from rflib import (RfCat, ChipconUsbTimeoutException, MOD_2FSK, SYNCM_CARRIER_16_of_16,
                    MFMCFG1_NUM_PREAMBLE0, MFMCFG1_NUM_PREAMBLE_2)


class RFListener:

    def __init__(self, usbInterface, processDataCallback):
        self.stopListeningEvent = threading.Event()
        self.usbInterface = usbInterface
        self.processDataCallback = processDataCallback
        self.manchester = manchester.ManchesterCodec()

    def startListening(self):
        self.listenerThread = threading.Thread(target = self.listenerLoop)
        self.listenerThread.start()

    def stopListening(self):
        self.stopListeningEvent.set()
        self.listenerThread.join()

    def listenerLoop(self):
        rfc = RfCat(self.usbInterface, debug=False)
        rfc.setFreq(433.91e6)
        rfc.setMdmModulation(MOD_2FSK)
        rfc.setMdmDeviatn(26370)
        rfc.setPktPQT(1)
        rfc.setMdmSyncMode(SYNCM_CARRIER_16_of_16)
        rfc.makePktFLEN(80)
        rfc.setEnableMdmManchester(False)
        rfc.setMdmDRate(40625)
        rfc.setRFRegister(0xdf18, 0x70)
        rfc.setMdmNumPreamble(MFMCFG1_NUM_PREAMBLE0)
        rfc.setMdmSyncWord(0xa55a)

        self.dataQueue = Queue.Queue()
        pp = threading.Thread(target = self.dataProcessor)
        pp.start()

        while True:
            try:
                if self.stopListeningEvent.wait(0):
                    break
                rfdata = rfc.RFrecv(timeout = 10000)
                self.dataQueue.put(rfdata)
            except ChipconUsbTimeoutException:
                pass
        rfc.cleanup()
        self.dataQueue.put(None)
        self.dataQueue.task_done()
        pp.join()

    def dataProcessor(self):
        while True:
            rfdata = self.dataQueue.get(block = True)
            if rfdata is None:
                break
                
            data, timestamp = rfdata
            data = self.manchester.Decode(data)
            if data is not None and len(data) > 1:
                calc = crc.crc8(data[0:-1])
                if ord(data[-1]) == calc:
                    self.processDataCallback(data[0:-1], timestamp)
