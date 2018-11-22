import random
from nonce import Nonce
from radio import Radio
from pod import Pod, BasalState, BolusState, PodAlarm, PodProgress, PodStatus
from message import Message, MessageState, MessageType
from datetime import date, datetime, time, timedelta
import struct
from threading import RLock
import time

def currentTimestamp():
    return datetime.utcnow() - datetime.utcfromtimestamp(0)

class PdmError(Exception):
    pass

class Pdm:
    def __init__(self, existingPod = None):
        self.commandLock = RLock()
        if existingPod is not None:
            if not existingPod.isInitialized():
                raise PdmError()
            self.nonce = Nonce(existingPod.lot, existingPod.tid)
        self.pod = existingPod
        self.radio = Radio()
        self.radio.start()
        self.nonceSyncWord = None

    def cleanUp(self):
        if self.radio is not None:
            self.radio.stop()

    def initializePod(self, addressToAssign = None):
        raise PdmError() #not implemented
        with self.commandLock:
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
        with self.commandLock:
            if self.pod is None or not self.pod.isInitialized():
                raise PdmError()

            commandType = 0x0e
            commandBody = "\00"
            msg = self.createMessage(commandType, commandBody)
            self.radio.sendRequestToPod(msg, self.handlePodResponse)

    def normalBolus(self, bolusAmount, cancelEvent, confidenceReminder = True):
        with self.commandLock:
            if self.pod is None or not self.pod.isInitialized():
                raise PdmError()
            if bolusAmount > self.pod.maximumBolus:
                raise PdmError()

            pulseCount = int(round(bolusAmount / 0.05))

            if pulseCount == 0:
                raise PdmError()

            pulseSpan = pulseCount * 16
            if pulseSpan > 0x3840:
                raise PdmError()

            self.updatePodStatus()

            if self.pod.status.bolusState == BolusState.Immediate:
                raise PdmError()
            if bolusAmount > self.pod.status.podReservoir:
                raise PdmError()

            checksum = pulseSpan + pulseCount*2 + 1

            commandBody = struct.pack(">I", self.nonce.getNext())
            commandBody += chr(0x02)
            commandBody += struct.pack(">H", checksum)
            commandBody += chr(0x01)
            commandBody += struct.pack(">H", pulseSpan)
            commandBody += struct.pack(">H", pulseCount)
            commandBody += struct.pack(">H", pulseCount)

            msg = self.createMessage(0x1a, commandBody)

            reminders = 0
            if confidenceReminder:
                reminders |= 0x40

            deliveryStart = 200000

            commandBody = chr(reminders)
            commandBody += struct.pack(">H", pulseCount * 10)
            commandBody += struct.pack(">I", deliveryStart)
            commandBody += "\00\00\00\00\00\00"
            msg.addCommand(0x17, commandBody)

            while True:
                self.radio.sendRequestToPod(msg, self.handlePodResponse)
                if self.nonceSyncWord is None:
                    break
                self.radio.messageSequence = (self.radio.messageSequence - 2) % 16
                self.nonce.sync(self.nonceSyncWord, self.radio.messageSequence)
                self.nonceSyncWord = None
                msg.resetNonce(self.nonce.getNext())

            if self.pod.status.bolusState != BolusState.Immediate:
                raise PdmError()

            if cancelEvent.wait(pulseCount * 2):
                self.cancelDelivery()
                return

            while True:
                if cancelEvent.wait(2):
                    self.cancelDelivery()
                self.updatePodStatus()
                if self.pod.status.bolusState != BolusState.Immediate:
                    break

    def setBasal(self):
        with self.commandLock:
            pass

    def cancelBolus(self, beep = False):
        with self.commandLock:
            self.updatePodStatus()
            if self.pod.status.basalState != BasalState.TempBasal:
                raise PdmError()

            commandBody = struct.pack(">I", self.nonce.getNext())
            commandBody += chr(0x01)
            c = 0x04
            if beep:
                c = c | 0x60

            msg = self.createMessage(0x1f, commandBody)
            while True:
                self.radio.sendRequestToPod(msg, self.handlePodResponse)
                if self.nonceSyncWord is None:
                    break
                self.radio.messageSequence = (self.radio.messageSequence - 2) % 16
                self.nonce.sync(self.nonceSyncWord, self.radio.messageSequence)
                self.nonceSyncWord = None
                msg.resetNonce(self.nonce.getNext())

            if self.pod.status.basalState == BasalState.TempBasal:
                raise PdmError()

    def cancelTempBasal(self, beep = False):
        with self.commandLock:
            self.updatePodStatus()
            if self.pod.status.basalState != BasalState.TempBasal:
                raise PdmError()

            commandBody = struct.pack(">I", self.nonce.getNext())
            commandBody += chr(0x01)
            c = 0x02
            if beep:
                c = c | 0x60

            msg = self.createMessage(0x1f, commandBody)
            while True:
                self.radio.sendRequestToPod(msg, self.handlePodResponse)
                if self.nonceSyncWord is None:
                    break
                self.radio.messageSequence = (self.radio.messageSequence - 2) % 16
                self.nonce.sync(self.nonceSyncWord, self.radio.messageSequence)
                self.nonceSyncWord = None
                msg.resetNonce(self.nonce.getNext())

            if self.pod.status.basalState == BasalState.TempBasal:
                raise PdmError()

    def setTempBasal(self, basalRate, hours, confidenceReminder = False):
        with self.commandLock:
            if self.pod is None or not self.pod.isInitialized():
                raise PdmError()

            halfHours = int(round(hours * 2))

            if halfHours > 24 or halfHours < 1:
                raise PdmError()

            if basalRate > self.pod.maximumTempBasal:
                raise PdmError()

            if basalRate > 30.0:
                raise PdmError()

            self.updatePodStatus()

            if self.pod.status.bolusState == BolusState.Immediate:
                raise PdmError()

            if self.pod.status.basalState == BasalState.TempBasal:
                self.cancelTempBasal()

            hourlyPulses = int(round(basalRate / 0.05))
            halfHourPulses = int(hourlyPulses / 2)
            alternate = (hourlyPulses % 2 == 1)

            checksum = halfHours + 0x38 + 0x40 + (halfHourPulses >> 8) + (halfHourPulses & 0xFF)

            iseBody = ""
            hoursLeft = halfHours
            if halfHours > 16:
                ise = 0xf000
                if alternate:
                    ise = ise | 0x0800
                    checksum += 8
                ise = ise | (halfHourPulses)
                iseBody += struct.pack(">H", ise)
                hoursLeft -= 16
                checksum += (halfHourPulses >> 8) * 16
                checksum += (halfHourPulses & 0xFF) * 16

            ise = (hoursLeft - 1) << 12
            if alternate:
                ise = ise | 0x0800
            ise = ise | (halfHourPulses)
            iseBody += struct.pack(">H", ise)
            checksum += (halfHourPulses >> 8) * hoursLeft
            checksum += (halfHourPulses & 0xFF) * hoursLeft
            if alternate:
                checksum += int(hoursLeft/2)

            commandBody = struct.pack(">I", self.nonce.getNext())
            commandBody += chr(0x01)
            commandBody += struct.pack(">H", checksum)
            commandBody += chr(halfHours)
            commandBody += struct.pack(">H", 0x3840)
            commandBody += struct.pack(">H", halfHourPulses)
            commandBody += iseBody

            msg = self.createMessage(0x1a, commandBody)

            reminders = 0
            if confidenceReminder:
                reminders |= 0x40

            commandBody = chr(reminders)
            commandBody += chr(0x00)

            pulseEntries = []
            subTotal = 0
            for i in range(0,halfHours):
                increase = halfHourPulses
                if alternate and i % 2 == 1:
                    increase += 1

                if subTotal + increase > 6553:
                    pulseEntries.append(subTotal)
                    subTotal = 0
                subTotal += increase
            pulseEntries.append(subTotal)

            pulseInterval = 3600 * 100000 / hourlyPulses

            commandBody += struct.pack(">H", pulseEntries[0] * 10)
            commandBody += struct.pack(">I", pulseInterval)
            for pe in pulseEntries:
                commandBody += struct.pack(">H", pe * 10)
                commandBody += struct.pack(">I", pulseInterval)
                
            msg.addCommand(0x16, commandBody)

            while True:
                self.radio.sendRequestToPod(msg, self.handlePodResponse)
                if self.nonceSyncWord is None:
                    break
                self.radio.messageSequence = (self.radio.messageSequence - 2) % 16
                self.nonce.sync(self.nonceSyncWord, self.radio.messageSequence)
                self.nonceSyncWord = None
                msg.resetNonce(self.nonce.getNext())

            if self.pod.status.basalState != BasalState.TempBasal:
                raise PdmError()

    def cancelDelivery(self):
        pass

    def handlePodResponse(self, messageSent, messageReceived):
        contents = messageReceived.getContents()
        for (ctype, content) in contents:
            if ctype == 0x1d: # status response
                self.pod.updateStatus(content)
                return None
            if ctype == 0x06: 
                if content[0] == chr(0x14): # bad nonce error
                    self.nonceSyncWord = struct.unpack(">H", content[1:])[0]
                    self.nonceSyncIndex = messageReceived.sequence
                    return None
                else:
                    errorCode = ord(content[0])
                    loggedEvent = ord(content[1])
                    podProgress = ord(content[2])

    def createMessage(self, commandType, commandBody):
        msg = Message(MessageType.PDM, self.pod.address)
        msg.addCommand(commandType, commandBody)
        return msg
        