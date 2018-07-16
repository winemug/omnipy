#!/usr/bin/python

import time
import datetime
import threading
import Queue

from rflib import (RfCat, ChipconUsbTimeoutException, MOD_2FSK, SYNCM_CARRIER_16_of_16,
    MFMCFG1_NUM_PREAMBLE0, MFMCFG1_NUM_PREAMBLE_2, MFMCFG1_NUM_PREAMBLE_8)


stopListeningEvent = threading.Event()

def main():
    listenerThread = threading.Thread(target = listenerLoop)
    listenerThread.start()

    raw_input("Listening.. Press Enter to exit\n")

    stopListeningEvent.set()
    listenerThread.join()

def listenerLoop():
    rfc = RfCat(0, debug=False)
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

    dataQueue = Queue.Queue()
    pp = threading.Thread(target = dataProcessor, args = [dataQueue])
    pp.start()

    while True:
        try:
            if stopListeningEvent.wait(0):
                break
            rfdata = rfc.RFrecv(timeout=1000)
            dataQueue.put(rfdata)
        except ChipconUsbTimeoutException:
            pass
    dataQueue.put(None)
    rfc.cleanup()
    dataQueue.task_done()

def dataProcessor(queue):
    while True:
        rfdata = queue.get(block = True)
        if rfdata is None:
            break
            
        data, timestamp = rfdata
        bytes = map(lambda x: ord(x) ^ 0xff, data)
        data = bytearray(bytes).__str__()

        p_addr1 = data[0:4].encode("hex").zfill(4)
        p_type = ord(data[4]) >> 5
        if p_type == 5:
            p_typestr = "PDM"
        elif p_type == 7:
            p_typestr = "POD"
        elif p_type == 2:
            p_typestr = "ACK"
        elif p_type == 4:
            p_typestr = "CON"
        else:
            p_typestr = bin(p_type)[2:5].zfill(3)

        p_seq = hex(ord(data[4]) & 0b00011111)[2:3].zfill(2)
        p_addr2 = data[5:9].encode("hex").zfill(4)
        if p_type == 5 or p_type == 7:
            p_bodylen = ord(data[10])
            p_body = data[11:11+p_bodylen].encode("hex")
        else:
            p_body = data[10:].encode("hex")
            pass
        
        print(timestamp, p_seq, p_typestr, p_addr1, p_addr2, p_body)


if __name__== "__main__":
  main()