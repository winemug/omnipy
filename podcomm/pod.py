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
        self.path = None

    def Save(self, save_as = None):
        if save_as is not None:
            self.path = save_as
        if self.path is None:
            raise ValueError("No filename given")
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

    def setupPod(self, messageBody):
        pass

    def handle_information_response(self, response):
        self.faulted = True
        if response[0] == 0x02:
            self.progress = response[1]

    def handle_status_response(self, response):
        s = struct.unpack(">BII", response)
        delivery = s[0]
        insulin_pulses = (s[1] & 0x0FFF8000) >> 15
        msg_sequence = (s[1] & 0x00007800) >> 11
        canceled_pulses = s[1] & 0x000007FF

        pod_alarm = (s[2] & 0xFF000000) >> 25
        pod_active_time = (s[2] & 0x007FFC00) >> 10
        pod_reservoir = s[2] & 0x000003FF

        if delivery & 0x80 > 0:
            self.bolusState = BolusState.Extended
        elif delivery & 0x40 > 0:
            self.bolusState = BolusState.Immediate
        else:
            self.bolusState = BolusState.NotRunning

        if delivery & 0x20 > 0:
            self.basalState = BasalState.TempBasal
        elif delivery & 0x10 > 0:
            self.basalState = BasalState.Program
        else:
            self.basalState = BasalState.NotRunning

        self.progress = delivery & 0xF

        self.alarm = pod_alarm
        self.reservoir = pod_reservoir * 0.05
        self.msgSequence = msg_sequence
        self.totalInsulin = insulin_pulses * 0.05
        self.canceledInsulin = canceled_pulses * 0.05
        self.activeMinutes = pod_active_time
        now = datetime.utcnow()
        self.lastUpdated = (now - datetime.utcfromtimestamp(0)).total_seconds()

        ds = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

        log_line = "%d\t%s\t%f\t%f\t%d\t%d\t%d\t%d\t%d\t%s\t%s\t%d\t%d\n" % \
            (self.lastUpdated, ds, self.totalInsulin, self.canceledInsulin, self.activeMinutes, self.progress,
             self.bolusState, self.basalState, self.reservoir, self.alarm, self.faulted, self.lot, self.tid)

        log_file_path = self.path + ".log"
        with open(log_file_path, "a") as stream:
            stream.write(log_line)

        self.Save()

    def __str__(self):
        p = self
        state = "Lot %d Tid %d Address 0x%8X Faulted: %s\n" % (p.lot, p.tid, p.address, p.faulted)
        state += "Updated %s\nState: %s\nAlarm: %s\nBasal: %s\nBolus: %s\nReservoir: %dU\n" %\
                 (p.lastUpdated, p.progress, p.alarm, p.basalState, p.bolusState, p.reservoir)
        state += "Insulin delivered: %fU canceled: %fU\nTime active: %s" %\
                 (p.totalInsulin, p.canceledInsulin, timedelta(minutes=p.activeMinutes))
        return state