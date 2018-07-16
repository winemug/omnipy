
import time
import datetime
import threading
import Queue

from rflib import (RfCat, ChipconUsbTimeoutException, MOD_2FSK, SYNCM_CARRIER_16_of_16,
    MFMCFG1_NUM_PREAMBLE0, MFMCFG1_NUM_PREAMBLE_2, MFMCFG1_NUM_PREAMBLE_8)


class RFListener:

    def __init__(self, usbInterface, processDataCallback):
        self.stopListeningEvent = threading.Event()
        self.usbInterface = usbInterface
        self.processDataCallback = processDataCallback

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
        rfc.setPktPQT(1)
        rfc.setMdmSyncMode(SYNCM_CARRIER_16_of_16)
        rfc.makePktFLEN(50)
        rfc.setEnableMdmManchester(True)
        rfc.setMdmDRate(40625)
        rfc.setRFRegister(0xdf18, 0x70)
        rfc.setMdmNumPreamble(MFMCFG1_NUM_PREAMBLE_2)
        rfc.setMdmSyncWord(0x54c3)

        self.dataQueue = Queue.Queue()
        pp = threading.Thread(target = self.dataProcessor)
        pp.start()

        while True:
            try:
                if self.stopListeningEvent.wait(0):
                    break
                rfdata = rfc.RFrecv(timeout=1000)
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
            bytes = map(lambda x: ord(x) ^ 0xff, data)
            data = bytearray(bytes).__str__()

            self.processDataCallback(data, timestamp)
