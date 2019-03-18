from decimal import *
from .exceptions import PdmError, PdmBusyError
import struct
from threading import RLock

g_lock = RLock()

class PdmLock():
    def __init__(self, timeout=2):
        self.fd = None
        self.timeout = timeout

    def __enter__(self):
        if not g_lock.acquire(blocking=True, timeout=self.timeout):
            raise PdmBusyError()

    def __exit__(self, exc_type, exc_val, exc_tb):
        g_lock.release()

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
    index = 0
    for hhu in halfHourUnits:
        pulses10 = hhu * Decimal("200")
        interval = 1800000000
        if hhu > 0:
            interval = int(Decimal("9000000") / hhu)

        if interval < 200000:
            raise PdmError()
        elif interval > 1800000000:
            raise PdmError()

        list1.append((int(pulses10), int(interval), index))
        index += 1

    list2 = []
    lastPulseInterval = None
    subTotalPulses = 0
    hh_indices = []

    for pulses, interval, index in list1:
        if lastPulseInterval is None:
            subTotalPulses = pulses
            lastPulseInterval = interval
            hh_indices.append(index)
        elif lastPulseInterval == interval:
            if subTotalPulses + pulses < 65536 and subTotalPulses > 0:
                subTotalPulses += pulses
                hh_indices.append(index)
            else:
                list2.append((subTotalPulses, lastPulseInterval, hh_indices))
                subTotalPulses = pulses
                hh_indices = [index]
        else:
            list2.append((subTotalPulses, lastPulseInterval, hh_indices))
            subTotalPulses = pulses
            lastPulseInterval = interval
            hh_indices = [index]
    else:
        if lastPulseInterval >= 0:
            list2.append((subTotalPulses, lastPulseInterval, hh_indices))

    return list2
