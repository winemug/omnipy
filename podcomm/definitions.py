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


class PodAlert(IntEnum):
    AutoOff = 0x01
    Unknown = 0x02
    EndOfService = 0x04
    Expired = 0x08
    LowReservoir = 0x10
    SuspendInProgress = 0x20
    SuspendEnded = 0x40
    TimerLimit = 0x80


class PodAlertBit(IntEnum):
    AutoOff = 0x00
    Unknown = 0x01
    EndOfService = 0x02
    Expired = 0x03
    LowReservoir = 0x04
    SuspendInProgress = 0x05
    SuspendEnded = 0x06
    TimerLimit = 0x07
