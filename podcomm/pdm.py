import random
from radio import Radio, RadioMode
from pod import Pod
from message import Message, MessageState, MessageType
from datetime import date, datetime, time, timedelta

def currentTimestamp():
    return datetime.utcnow() - datetime.utcfromtimestamp(0)

class PdmError(Exception):
    pass

class Pdm:
    def __init__(self, existingPod = None):
        if existingPod is not None:
            if not existingPod.isInitialized():
                raise PdmError()
        self.pod = existingPod
        self.radio = Radio()
        self.radio.start(radioMode = RadioMode.Pdm)

    def cleanUp(self):
        if self.radio is not None:
            self.radio.stop()

    def initializePod(self, addressToAssign = None):
        if self.pod is not None:
            raise PdmError()

        if addressToAssign is None:
            addressToAssign = random.randint(0x18000000, 0xea000000)
        success = False

        #TODO: get these values from initialization process
        tid = 0
        lot = 0

        self.pod = Pod(lot, tid, addressToAssign)
        success = True

        return success

    def updatePodStatus(self):
        if self.pod is None or not self.pod.isInitialized():
            raise PdmError()

        commandType = 0x0e
        commandBody = "\00"
        msg = self.createMessage(commandType, commandBody)
        self.radio.sendRequestToPod(msg, self.handlePodResponse)

    def handlePodResponse(self, messageSent, messageReceived):
        contents = messageReceived.getContents()
        for (ctype, content) in contents:
            if ctype == 0x1d:
                self.pod.updateStatus(content)
                return None

    def createMessage(self, commandType, commandBody):
        msg = Message(currentTimestamp(), MessageType.PDM, self.pod.address)
        msg.addCommand(commandType, commandBody)
        return msg
        