from decimal import *
from .exceptions import PdmError, PdmBusyError
from .definitions import *
import struct
import fcntl

class PdmLock():
    def __init__(self):
        self.fd = None

    def __enter__(self):
        try:
            self.fd = open(PDM_LOCK_FILE, "w")
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as ioe:
            self.fd = None
            raise PdmBusyError from ioe

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        except IOError as ioe:
            raise

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
    while ptr < len(pulses):
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
            others = pulses[ptr + 1:]
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
            if subTotalPulses + pulses < 65536 and subTotalPulses > 0:
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
