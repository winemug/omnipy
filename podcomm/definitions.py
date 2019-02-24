from enum import IntEnum
import logging

RILEYLINK_MAC_FILE = "data/rladdr"
PDM_LOCK_FILE = "data/.pdmlock"
TOKENS_FILE = "data/tokens"
KEY_FILE = "data/key"
RESPONSE_FILE = "data/response"
POD_FILE = "data/pod"
POD_FILE_SUFFIX = ".json"
POD_LOG_SUFFIX = ".log"
OMNIPY_LOGGER = "OMNIPY"
OMNIPY_LOGFILE = "data/omnipy.log"

API_VERSION_MAJOR = 1
API_VERSION_MINOR = 0

REST_URL_GET_VERSION = "/omnipy/version"

REST_URL_TOKEN = "/omnipy/token"
REST_URL_CHECK_PASSWORD = "/omnipy/pwcheck"

REST_URL_NEW_POD = "/omnipy/newpod"
REST_URL_SET_POD_PARAMETERS = "/omnipy/parameters"
REST_URL_GET_PDM_ADDRESS = "/omnipy/pdmspy"
REST_URL_SET_LIMITS = "/omnipy/limits"

REST_URL_RL_INFO = "/rl/info"

REST_URL_STATUS = "/pdm/status"
REST_URL_PDM_BUSY = "/pdm/isbusy"
REST_URL_ACK_ALERTS = "/pdm/ack"
REST_URL_DEACTIVATE_POD = "/pdm/deactivate"
REST_URL_BOLUS = "/pdm/bolus"
REST_URL_CANCEL_BOLUS = "/pdm/cancelbolus"
REST_URL_SET_TEMP_BASAL = "/pdm/settempbasal"
REST_URL_CANCEL_TEMP_BASAL = "/pdm/canceltempbasal"


def getLogger():
    return logging.getLogger(OMNIPY_LOGGER)


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
