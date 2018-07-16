import threading
import listener

class pdm:

    def __init__(self, lot = None, tid = None):
        self.lot = lot
        self.tid = tid
        self.parametersObserved = threading.Event()
        self.listener = listener.RFListener(0, self.processData)

    def startObservation(self):
        self.parametersObserved.clear()
        self.listener.startListening()

    def stopObservation(self):
        self.listener.stopListening()
        pass

    def processData(self, data, timestamp):
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

        #tbd
        self.parametersObserved.set()

