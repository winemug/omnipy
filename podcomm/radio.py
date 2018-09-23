import time
import datetime
import threading
import Queue
import array
import manchester
import crc
import packet

from rflib import (RfCat, ChipconUsbTimeoutException, MOD_2FSK, SYNCM_CARRIER_16_of_16,
                    MFMCFG1_NUM_PREAMBLE0, MFMCFG1_NUM_PREAMBLE_2)


class Radio:
    def __init__(self, usbInterface):
        self.stopRadioEvent = threading.Event()
        self.usbInterface = usbInterface
        self.manchester = manchester.ManchesterCodec()

    def start(self, recvCallback):
        self.recvCallback = recvCallback
        self.recvQueue = Queue.Queue()
        self.sendQueue = Queue.Queue()
        self.radioThread = threading.Thread(target = self.radioLoop)
        self.radioThread.start()

    def stop(self):
        self.stopRadioEvent.set()
        self.radioThread.join()

    def send(self, packet):
        data += chr(crc.crc8(data))
        data = self.manchester.encode(packet.data)
        self.sendQueue.put(data)

    def radioLoop(self):
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

        pp = threading.Thread(target = self.recvProcessor)
        pp.start()

        while not self.stopRadioEvent.wait(0):
            try:
                while not self.sendQueue.empty:
                    sendData = self.sendQueue.get()
                    rfc.RFsend(sendData)
                recvdata = rfc.RFrecv(timeout = 100)
                self.recvQueue.put(recvdata)
            except ChipconUsbTimeoutException:
                pass
        rfc.cleanup()
        self.recvQueue.put(None)
        self.recvQueue.task_done()
        pp.join()

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
