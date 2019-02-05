import random
from decimal import *
from .nonce import Nonce
from .radio import Radio
from .pod import Pod, BasalState, BolusState, PodAlarm, PodProgress
from .message import Message, MessageState, MessageType
from datetime import date, datetime, time, timedelta
import struct
from threading import RLock
import time
import logging

def currentTimestamp():
    return datetime.utcnow() - datetime.utcfromtimestamp(0)

def getPulsesForHalfHours(halfHourUnits):
    halfHourlyDeliverySubtotals = []
    totalToDeliver = Decimal(0)
    for hhunit in halfHourUnits:
        totalToDeliver += hhunit
        halfHourlyDeliverySubtotals.append(totalToDeliver)

    pulses = []
    totalDelivered = Decimal(0)
    for subtotal in halfHourlyDeliverySubtotals:
        toDeliver = subtotal - totalDelivered
        pulseCount = int(toDeliver * Decimal(20))
        totalDelivered += Decimal(pulseCount) / Decimal(20)
        pulses.append(pulseCount)

    return pulses

def getInsulinScheduleTableFromPulses(pulses):
    iseTable = []
    ptr = 0
    while(ptr<len(pulses)):
        if ptr == len(pulses) - 1:
            iseTable.append(getIse(pulses[ptr], 0, False))
            break

        alternatingTable = pulses[ptr:]
        for k in range(1, len(alternatingTable), 2):
            alternatingTable[k] -= 1

        pulse = alternatingTable[0]
        others = alternatingTable[1:]
        repeats = getRepeatCount(pulse, others)
        if repeats > 15:
            repeats = 15
        if repeats > 0:
            iseTable.append(getIse(pulse, repeats, True))
        else:
            pulse = pulses[ptr]
            others = pulses[ptr+1:]
            repeats = getRepeatCount(pulse, others)
            if repeats > 15:
                repeats = 15
            iseTable.append(getIse(pulse, repeats, False))
        ptr += repeats + 1
    return iseTable
            
def getIse(pulses, repeat, alternate):
    ise = pulses & 0x03ff
    ise |= repeat << 12
    if alternate:
        ise |= 0x0800
    return ise

def getRepeatCount(pulse, otherPulses):
    repeatCount = 0
    for other in otherPulses:
        if pulse != other:
            break
        repeatCount += 1
    return repeatCount

def getStringBodyFromTable(table):
    st = bytes()
    for val in table:
        st += struct.pack(">H", val)
    return st

def getChecksum(body):
    checksum = 0
    for c in body:
        checksum += c
    return checksum

def getHalfHourPulseInterval(pulseCount):
    if pulseCount == 0:
        return 180000000
    else:
        return int(180000000 / pulseCount)

def getPulseIntervalEntries(halfHourUnits):
    list1 = []
    for hhu in halfHourUnits:
        pulses10 = hhu * Decimal("200")
        interval = 1800000000
        if hhu > 0:
            interval = int(Decimal("9000000") / hhu)

        if interval < 200000:
            raise PdmError()
        elif interval > 1800000000:
            raise PdmError()

        list1.append((int(pulses10), int(interval)))

    list2 = []
    lastPulseInterval = -1
    subTotalPulses = 0

    for pulses, interval in list1:
        if lastPulseInterval == -1:
            subTotalPulses = pulses
            lastPulseInterval = interval
        elif lastPulseInterval == interval:
            if subTotalPulses + pulses < 65536:
                subTotalPulses += pulses
            else:
                list2.append((subTotalPulses, lastPulseInterval))
                subTotalPulses = pulses
        else:
            list2.append((subTotalPulses, lastPulseInterval))
            subTotalPulses = pulses
            lastPulseInterval = interval
    else:
        if lastPulseInterval >= 0:
            list2.append((subTotalPulses, lastPulseInterval))

    return list2



class PdmError(Exception):
    pass

class Pdm:
    def __init__(self, pod, dryRun = False):
        self.commandLock = RLock()
        self.nonce = Nonce(pod.lot, pod.tid, seekNonce = pod.lastNonce, seed = pod.nonceSeed)
        self.pod = pod
        self.radio = Radio(pod.msgSequence, pod.packetSequence)
        if not dryRun:
            self.radio.start()
        self.nonceSyncWord = None
        self.dryRun = dryRun

    def __createMessage(self, commandType, commandBody):
        msg = Message(MessageType.PDM, self.pod.address)
        msg.addCommand(commandType, commandBody)
        return msg

    def __savePod(self):
        logging.debug("Saving pod status")
        if not self.dryRun:
            self.pod.msgSequence = self.radio.messageSequence
            self.pod.packetSequence = self.radio.packetSequence
            self.pod.lastNonce = self.nonce.lastNonce
            self.pod.nonceSeed = self.nonce.seed
            self.pod.Save()

    def __sendMessage(self, message, responseHandler):
        logging.debug("Sending message: %s" % message)
        if not self.dryRun:
            self.radio.sendRequestToPod(message, self.__handlePodResponse)

    def cleanUp(self):
        logging.debug("Running cleanup")
        self.__savePod()
        if not self.dryRun:
            if self.radio is not None:
                self.radio.stop()

    def initializePod(self, path, addressToAssign = None):
        # with self.commandLock:

        #     if addressToAssign is None:
        #         addressToAssign = random.randint(0x20000000, 0x2FFFFFFF)
        #     success = False

        #     self.pod = Pod()

        #     commandType = 0x07
        #     commandBody = struct.unpack(">I", addressToAssign)
        #     msg = self.createMessage(commandType, commandBody)
        #     self.radio.sendRequestToPod(msg, self.handlePodResponse)
        #     self.savePod()

        #     success = True

        #     self.savePod()
        #     return success
        pass

    def deactivatePod(self):
        logging.debug("deactivating pod")
        self.__savePod()
        pass

    def updatePodStatus(self):
        logging.debug("updating pod status")
        with self.commandLock:
            dnts = (datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds()
            diffsecs = dnts - self.pod.lastUpdated
            if diffsecs < 7 and diffsecs > 0:
                time.sleep(7 - diffsecs)

            commandType = 0x0e
            commandBody = b"\x00"
            msg = self.__createMessage(commandType, commandBody)
            self.__sendMessage(msg, self.__handlePodResponse)
            self.__savePod()


    def bolus(self, bolusAmount, waitUntilFinished = True, confidenceReminder = False):
        logging.debug("enacting bolus: %f units" % bolusAmount)
        with self.commandLock:
            if self.pod is None or not self.pod.isInitialized():
                raise PdmError()
            if bolusAmount > self.pod.maximumBolus:
                raise PdmError()

            pulseCount = int(bolusAmount * Decimal(20))

            if pulseCount == 0:
                raise PdmError()

            pulseSpan = pulseCount * 16
            if pulseSpan > 0x3840:
                raise PdmError()

            self.updatePodStatus()

            if self.pod.bolusState == BolusState.Immediate:
                raise PdmError()
            if bolusAmount > self.pod.reservoir:
                raise PdmError()

            commandBody = struct.pack(">I", self.nonce.getNext())
            commandBody += b"\x02"

            bodyForChecksum = b"\x01"
            bodyForChecksum += struct.pack(">H", pulseSpan)
            bodyForChecksum += struct.pack(">H", pulseCount)
            bodyForChecksum += struct.pack(">H", pulseCount)
            checksum = getChecksum(bodyForChecksum)

            commandBody += struct.pack(">H", checksum)
            commandBody += bodyForChecksum

            msg = self.__createMessage(0x1a, commandBody)

            reminders = 0
            if confidenceReminder:
                reminders |= 0x40

            deliveryStart = 200000

            commandBody = bytes([reminders])
            commandBody += struct.pack(">H", pulseCount * 10)
            commandBody += struct.pack(">I", deliveryStart)
            commandBody += b"\x00\x00\x00\x00\x00\x00"
            msg.addCommand(0x17, commandBody)

            self.__sendMessageWithNonce(msg)

            if not self.dryRun:
                if self.pod.bolusState != BolusState.Immediate:
                    raise PdmError()

                if waitUntilFinished:
                    time.sleep(pulseCount * 2)

                    while True:
                        self.updatePodStatus()
                        if self.pod.bolusState != BolusState.Immediate:
                            break
                        time.sleep(10)
                self.__savePod()

    def setBasalSchedule(self, basalSchedule):
        raise PdmError() # not implemented
        with self.commandLock:

            self.updatePodStatus()

            if self.pod.basalState == BasalState.TempBasal:
                raise PdmError()

            if self.pod.basalState == BasalState.Program:
                self.cancelBasal()
            
            if self.pod.basalState != BasalState.NotRunning:
                raise PdmError()

            commandBody = struct.pack(">I", self.nonce.getNext())
            commandBody += b"\x00"

            bodyForChecksum = ""
            utcOffset = timedelta(minutes = self.pod.utcOffset)
            podDate = datetime.utcnow() + utcOffset

            hour = podDate.hour
            minute = podDate.minute
            second = podDate.second

            currentHalfHour = hour * 2
            secondsUntilHalfHour = 0
            if minute < 30:
                secondsUntilHalfHour += (30 - minute - 1) * 60
            else:
                secondsUntilHalfHour += (60 - minute - 1) * 60
                currentHalfHour += 1

            secondsUntilHalfHour += (60 - second)

            pulseTable = getPulsesForHalfHours(basalSchedule)
            pulsesRemainingCurrentHour = int(secondsUntilHalfHour / 1800) * pulseTable[currentHalfHour]
            iseBody = getStringBodyFromTable(getInsulinScheduleTableFromPulses(pulseTable))

            bodyForChecksum += bytes([currentHalfHour])
            bodyForChecksum += struct.pack(">H", secondsUntilHalfHour * 8)
            bodyForChecksum += struct.pack(">H", pulsesRemainingCurrentHour)
            getChecksum(bodyForChecksum + getStringBodyFromTable(pulseTable))

            commandBody += bodyForChecksum + iseBody

            msg = self.__createMessage(0x1a, commandBody)

            reminders = 0
            if confidenceReminder:
                reminders |= 0x40

            commandBody = bytes([reminders])


            # commandBody += b"\x00"
            # pulseEntries = []
            # subTotal = 0
            # for pulses in pulseList:
            #     if subTotal + pulses > 6553:
            #         pulseEntries.append(subTotal)
            #         subTotal = 0
            #     subTotal += pulses
            # pulseEntries.append(subTotal)

            # if pulseList[0] == 0:
            #     pulseInterval = 3600* 100000
            # else:
            #     pulseInterval = 3600 * 100000 / pulseList[0]

            # commandBody += struct.pack(">H", pulseEntries[0] * 10)
            # commandBody += struct.pack(">I", pulseInterval)
            # for pe in pulseEntries:
            #     commandBody += struct.pack(">H", pe * 10)
            #     commandBody += struct.pack(">I", pulseInterval)
                
            # msg.addCommand(0x16, commandBody)

            self.__sendMessageWithNonce(msg)
            self.__savePod()
            if self.pod.basalState != BasalState.TempBasal:
                raise PdmError()

            self.__savePod()

    def cancelBasal(self, beep = False):
        logging.debug("Canceling current basal schedule")
        self.updatePodStatus()
        if self.pod.basalState == BasalState.Program:
            self.__cancelActivity(cancelBasal = True, alarm = beep)
        if self.pod.basalState == BasalState.Program:
            raise PdmError()

    def cancelBolus(self, beep = False):
        logging.debug("Canceling running bolus")
        self.updatePodStatus()
        if self.pod.bolusState == BolusState.Immediate:
            self.__cancelActivity(cancelBolus = True, alarm = beep)
        if self.pod.bolusState == BolusState.Immediate:
            raise PdmError()

    def cancelTempBasal(self, beep = False):
        logging.debug("Canceling temp basal")
        self.updatePodStatus()
        if self.pod.basalState == BasalState.TempBasal:
            self.__cancelActivity(cancelTempBasal = True, alarm = beep)
        if self.pod.basalState == BasalState.TempBasal:
            raise PdmError()

    def __cancelActivity(self, cancelBasal = False, cancelBolus= False, cancelTempBasal = False, alarm = True):
        logging.debug("Running cancel activity for basal: %s - bolus: %s - tempBasal: %s" %(cancelBasal, cancelBolus, cancelTempBasal))
        with self.commandLock:
            commandBody = struct.pack(">I", self.nonce.getNext())
            if alarm:
                c = 0x60
            else:
                c = 0

            c = 0x60
            if cancelBolus:
                c = c | 0x04
            if cancelTempBasal:
                c = c | 0x02
            if cancelBasal:
                c = c | 0x01
            commandBody += bytes([c])

            msg = self.__createMessage(0x1f, commandBody)
            self.__sendMessageWithNonce(msg)
            self.__savePod()

    def setTempBasal(self, basalRate, hours, confidenceReminder = False):
        with self.commandLock:

            halfHours = int(hours * Decimal(2))

            if halfHours > 24 or halfHours < 1:
                raise PdmError()

            if not self.dryRun:
                if self.pod is None or not self.pod.isInitialized():
                    raise PdmError()
                if basalRate > Decimal(self.pod.maximumTempBasal):
                    raise PdmError()
                if basalRate > Decimal(30):
                    raise PdmError()
                self.updatePodStatus()
                if self.pod.bolusState == BolusState.Immediate:
                    raise PdmError()
                if self.pod.basalState == BasalState.TempBasal:
                    self.cancelTempBasal()

            halfHourUnits = [basalRate / Decimal(2)] * halfHours
            pulseList = getPulsesForHalfHours(halfHourUnits)
            iseList = getInsulinScheduleTableFromPulses(pulseList)

            iseBody = getStringBodyFromTable(iseList)
            pulseBody = getStringBodyFromTable(pulseList)

            commandBody = struct.pack(">I", self.nonce.getNext())
            commandBody += b"\x01"

            bodyForChecksum = bytes([halfHours])
            bodyForChecksum += struct.pack(">H", 0x3840)
            bodyForChecksum += struct.pack(">H", pulseList[0])
            checksum = getChecksum(bodyForChecksum + pulseBody)

            commandBody += struct.pack(">H", checksum)
            commandBody += bodyForChecksum
            commandBody += iseBody

            msg = self.__createMessage(0x1a, commandBody)

            reminders = 0
            if confidenceReminder:
                reminders |= 0x40

            commandBody = bytes([reminders])
            commandBody += b"\x00"

            pulseEntries = getPulseIntervalEntries(halfHourUnits)

            firstPulseCount, firstInterval = pulseEntries[0]
            commandBody += struct.pack(">H", firstPulseCount)
            commandBody += struct.pack(">I", firstInterval)
            for pulseCount, interval in pulseEntries:
                commandBody += struct.pack(">H", pulseCount)
                commandBody += struct.pack(">I", interval)
                
            msg.addCommand(0x16, commandBody)

            if self.dryRun:
                print(msg)
            else:
                self.__sendMessageWithNonce(msg)
                self.__savePod()
                if self.pod.basalState != BasalState.TempBasal:
                    raise PdmError()

    def __sendMessageWithNonce(self, msg):
        while True:
            self.nonceSyncWord = None
            self.__sendMessage(msg, self.__handlePodResponse)
            if self.nonceSyncWord is None:
                break
            self.radio.messageSequence = (self.radio.messageSequence - 2) % 16
            self.nonce.sync(self.nonceSyncWord, self.radio.messageSequence)
            msg.resetNonce(self.nonce.getNext())

    def __handlePodResponse(self, messageSent, messageReceived):
        contents = messageReceived.getContents()
        for (ctype, content) in contents:
            if ctype == 0x01: # pod info response
                self.pod.setupPod(content)
                self.__savePod()
                return None
            if ctype == 0x1d: # status response
                self.pod.updateStatus(content)
                self.__savePod()
                return None
            if ctype == 0x02: # pod faulted
                self.pod.faultError(content)
                self.__savePod()
                return None
            if ctype == 0x06: 
                if content[0] == 0x14: # bad nonce error
                    self.nonceSyncWord = struct.unpack(">H", content[1:])[0]
                    self.nonceSyncIndex = messageReceived.sequence
                    return None
                else:
                    errorCode = ord(content[0])
                    loggedEvent = ord(content[1])
                    podProgress = ord(content[2])
                    return None

