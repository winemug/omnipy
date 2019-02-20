from enum import IntEnum

RILEYLINK_MAC_FILE = ".rladdr"
PDM_LOCK_FILE = ".pdmlock"
TOKENS_FILE = ".tokens"
KEY_FILE = ".key"
RESPONSE_FILE = ".response"
POD_FILE = "pod"
POD_FILE_SUFFIX = ".json"
POD_LOG_SUFFIX = ".log"
OMNIPY_LOGGER = "OMNIPY"
OMNIPY_LOGFILE = "omnipy.log"

API_VERSION_MAJOR = 1
API_VERSION_MINOR = 0


def getLogger():
    logging.getLogger(REST_LOGGER)


def configureLogging():
    logger = getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh = logging.FileHandler(OMNIPY_LOGFILE)
    ch = logging.StreamHandler()
    fh.setLevel(logging.DEBUG)
    ch.setLevel(logging.WARNING)
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)


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
