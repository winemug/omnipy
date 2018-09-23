import threading
import podcomm/radio

class pdm:

    def __init__(self, lot = None, tid = None):
        self.lot = lot
        self.tid = tid
        self.parametersObserved = threading.Event()
        self.radio = radio.Radio(0, self.recvData)

    def startObservation(self):
        self.parametersObserved.clear()
        self.radio.start()

    def stopObservation(self):
        self.radio.stop()

    def recvData(self, data, timestamp):
        #tbd
        self.parametersObserved.set()

