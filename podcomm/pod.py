#!/usr/bin/python3

import simplejson as json
import struct
from datetime import datetime, timedelta
import os
from enum import IntEnum


class BolusState(IntEnum):
    NotRunning = 0
    Extended = 1
    Immediate = 2


class BasalState(IntEnum):
    NotRunning = 0
    TempBasal = 1
    Program = 2


class PodProgress(IntEnum):
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


class PodAlarm(IntEnum):
    AutoOff = 0
    Unknown = 1
    EndOfService = 2
    Expired = 3
    LowReservoir = 4
    SuspendInProgress = 5
    SuspendEnded = 6
    TimerLimit = 7

class Pod:
    def __init__(self):
        self.lot=0
        self.tid=0

        self.lastUpdated=(datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds()
        self.progress=PodProgress.InitialState
        self.basalState=BasalState.NotRunning
        self.bolusState=BolusState.NotRunning
        self.alarm=0
        self.reservoir=0
        self.activeMinutes=0
        self.faulted = False

        self.totalInsulin=0
        self.canceledInsulin=0

        self.basalSchedule=[]
        self.tempBasal=[]
        self.extendedBolus=[]

        self.address=0xffffffff
        self.packetSequence=0
        self.msgSequence=0
        self.lastNonce=None
        self.nonceSeed=0

        self.maximumBolus=15
        self.maximumTempBasal=15
        self.utcOffset=0
        self.path = "omni.json"

    def Save(self, save_as = None):
        if save_as is not None:
            self.path = save_as
        with open(self.path, "w") as stream:
            json.dump(self.__dict__, stream, indent=4, sort_keys=True)

    @staticmethod
    def Load(path):
        with open(path, "r") as stream:
            d = json.load(stream)
            p = Pod()
            p.path = path
            p.lot=d["lot"]
            p.tid=d["tid"]
        
            p.lastUpdated=d["lastUpdated"]
            p.progress=d["progress"]
            p.basalState=d["basalState"]
            p.bolusState=d["bolusState"]
            p.alarm=d["alarm"]
            p.reservoir=d["reservoir"]
            p.activeMinutes=d["activeMinutes"]
            p.faulted=d["faulted"]

            p.totalInsulin=d["totalInsulin"]
            p.canceledInsulin=d["canceledInsulin"]

            p.basalSchedule=d["basalSchedule"]
            p.tempBasal=d["tempBasal"]
            p.extendedBolus=d["extendedBolus"]

            p.address=d["address"]
            p.packetSequence=d["packetSequence"]
            p.msgSequence=d["msgSequence"]
            p.lastNonce=d["lastNonce"]
            p.nonceSeed=d["nonceSeed"]

            p.maximumBolus=d["maximumBolus"]
            p.maximumTempBasal=d["maximumTempBasal"]
            p.utcOffset=d["utcOffset"]

        return p

    def isInitialized(self):
        return not(self.lot is None or self.tid is None or self.address is None) \
            and (self.progress == PodProgress.Running or self.progress == PodProgress.RunningLow) \
            and not self.faulted

    def faultError(self, errMessageBody):
        self.faulted = True
        if errMessageBody[0] == 0x02:
            self.progress = errMessageBody[1]

    def setupPod(self, messageBody):
        pass

    def updateStatus(self, statusMessageBody):
        s = struct.unpack(">BII", statusMessageBody)
        delivery = s[0]
        insulinPulses = (s[1] & 0x0FFF8000) >> 15
        msgSequence = (s[1] & 0x00007800) >> 11
        canceledPulses = s[1] & 0x000007FF

        podAlarm = (s[2] & 0xFF000000) >> 25
        podActiveTime = (s[2] & 0x007FFC00) >> 10
        podReservoir = s[2] & 0x000003FF

        p = self

        if delivery & 0x80 > 0:
            p.bolusState = BolusState.Extended
        elif delivery & 0x40 > 0:
            p.bolusState = BolusState.Immediate
        else:
            p.bolusState = BolusState.NotRunning

        if delivery & 0x20 > 0:
            p.basalState = BasalState.TempBasal
        elif delivery & 0x10 > 0:
            p.basalState = BasalState.Program
        else:
            p.basalState = BasalState.NotRunning

        p.progress = delivery & 0xF

        p.alarm = podAlarm
        p.reservoir = podReservoir * 0.05
        p.msgSequence = msgSequence
        p.totalInsulin = insulinPulses * 0.05
        p.canceledInsulin = canceledPulses * 0.05
        p.activeMinutes = podActiveTime
        dn = datetime.utcnow()
        p.lastUpdated = (dn - datetime.utcfromtimestamp(0)).total_seconds()

        ds = dn.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

        logLine = "%d\t%s\t%f\t%f\t%d\t%d\t%d\t%d\t%d\t%s\t%s\t%d\t%d\n" % \
            (p.lastUpdated, ds, p.totalInsulin, p.canceledInsulin, p.activeMinutes, p.progress, \
            p.bolusState, p.basalState, p.reservoir, p.alarm, p.faulted, p.lot, p.tid)

        mode = "w"
        logFilePath = self.path + ".log"
        if os.path.exists(logFilePath):
            mode = "a"
        else:
            mode = "w"
        stream = open(logFilePath, mode)
        stream.write(logLine)
        stream.close()

        self.Save()

    def __str__(self):
        p = self
        state = "Lot %d Tid %d Address 0x%8X Faulted: %s\n" % (p.lot, p.tid, p.address, p.faulted)
        state += "Updated %s\nState: %s\nAlarm: %s\nBasal: %s\nBolus: %s\nReservoir: %dU\nInsulin delivered: %fU canceled: %fU\nTime active: %s" % (p.lastUpdated, p.progress, p.alarm, p.basalState, p.bolusState,
                p.reservoir, p.totalInsulin, p.canceledInsulin, timedelta(minutes=p.activeMinutes))
        return state
