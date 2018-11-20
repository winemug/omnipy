from enum import Enum
from message import Message
import struct
from datetime import datetime, timedelta

class BolusState(Enum):
    NotRunning = 0
    Extended = 1
    Immediate = 2

class BasalState(Enum):
    NotRunning = 0
    TempBasal = 1
    Program = 2

class PodProgress(Enum):
    InitialState = 0
    TankPowerActivated = 1
    TankFillCompleted = 2
    PairingSuccess = 3
    Purging = 4
    ReadyForInjection = 5
    InjectionDone = 6
    Priming = 7
    Running = 8
    RunningLow = 9
    ErrorShuttingDown = 13
    AlertExpiredShuttingDown = 14
    Inactive = 15

class PodAlarm(Enum):
    Event14 = 0
    PodExpired = 1
    InsulinSuspendPeriodEnded = 2
    InsulinSuspended = 3
    LessThan50ULeft = 4
    PodExpiresInAnHour = 5
    PodDeactivated = 6

class PodStatus:
    def __init__(self):
        self.bolusState = BolusState.NotRunning
        self.basalState = BasalState.NotRunning
        self.podState = PodProgress.InitialState
        self.podReservoir = 0
        self.msgSequence = 0
        self.podAlarms = []
        self.totalInsulin = 0
        self.canceledInsulin = 0
        self.podActiveMinutes = 0
        self.lastUpdated = None

    def __str__(self):
        return "Updated %s\nState: %s\nAlarms: %s\nBasal: %s\nBolus: %s\nReservoir: %dU\nInsulin delivered: %fU canceled: %fU\nTime active: %s" % (self.lastUpdated, self.podState, self.podAlarms, self.basalState, self.bolusState,
                self.podReservoir, self.totalInsulin, self.canceledInsulin, timedelta(minutes=self.podActiveMinutes))

class Pod:
    def __init__(self, lot, tid, address = None):
        self.lot = lot
        self.tid = tid
        self.address = address
        self.status = PodStatus()
        self.maximumBolus = 15.0

        
    def isInitialized(self):
        return not(self.lot is None or self.tid is None or self.address is None)

    def updateStatus(self, statusMessageBody):
        s = struct.unpack(">BII", statusMessageBody)
        delivery = s[0]
        insulinPulses = (s[1] & 0x0FFF8000) >> 15
        msgSequence = (s[1] & 0x00007800) >> 11
        canceledPulses = s[1] & 0x000007FF

        podAlarm = (s[2] & 0xFF000000) >> 25
        podActiveTime = (s[2] & 0x007FFC00) >> 10
        podReservoir = s[2] & 0x000003FF

        if delivery & 0x80 > 0:
            self.status.bolusState = BolusState.Extended
        elif delivery & 0x40 > 0:
            self.status.bolusState = BolusState.Immediate
        else:
            self.status.bolusState = BolusState.NotRunning

        if delivery & 0x20 > 0:
            self.status.basalState = BasalState.TempBasal
        elif delivery & 0x10 > 0:
            self.status.basalState = BasalState.Program
        else:
            self.status.basalState = BasalState.NotRunning

        self.status.podState = PodProgress(delivery & 0xF)

        alarms = []
        if podAlarm & 0x40 > 0:
            alarms.append(PodAlarm.Event14)
        if podAlarm & 0x20 > 0:
            alarms.append(PodAlarm.PodExpired)
        if podAlarm & 0x10 > 0:
            alarms.append(PodAlarm.InsulinSuspendPeriodEnded)
        if podAlarm & 0x08 > 0:
            alarms.append(PodAlarm.InsulinSuspended)
        if podAlarm & 0x04 > 0:
            alarms.append(PodAlarm.LessThan50ULeft)
        if podAlarm & 0x02 > 0:
            alarms.append(PodAlarm.PodExpiresInAnHour)
        if podAlarm & 0x01 > 0:
            alarms.append(PodAlarm.PodDeactivated)

        self.status.podAlarms = alarms        
        self.status.podReservoir = podReservoir * 0.05
        self.status.msgSequence = msgSequence
        self.status.totalInsulin = insulinPulses * 0.05
        self.status.canceledInsulin = canceledPulses * 0.05
        self.status.podActiveMinutes = podActiveTime
        self.status.lastUpdated = datetime.utcnow()

    def __str__(self):
        return "Lot %d Tid %d Address 0x%8X Status: %s" % (self.lot, self.tid, self.address, self.status)