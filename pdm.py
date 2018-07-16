import threading

class pdm:

    def __init__(self, lot, tid):
        self.lot = lot
        self.tid = tid
        self.parametersObserved = threading.Event()

    def startObservation(self):
        self.parametersObserved.clear()
        self.parametersObserved.set()

    def stopObservation(self):
        pass
