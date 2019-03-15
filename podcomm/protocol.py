from podcomm.message import PdmMessage, Message, MessageType
from podcomm.protocol_common import *
from podcomm.definitions import *
from enum import IntEnum
import struct
from datetime import datetime, timedelta


class StatusRequestType(IntEnum):
    Standard = 0


def _cm(cmd_type, cmd_body):
    m = Message(MessageType.PDM, 0, 0)
    m.addCommand(cmd_type, cmd_body)
    return m

def request_assign_address(address):
    cmd_body = struct.pack(">I", address)
    return _cm(PdmRequest.AssignAddress, cmd_body)


def request_setup_pod(lot, tid, address, utc_offset_minutes):
    cmd_body = struct.pack(">I", address)
    cmd_body += bytes([0x14, 0x04])

    pod_date = datetime.utcnow() + timedelta(minutes=utc_offset_minutes)

    year = pod_date.year
    month = pod_date.month
    day = pod_date.day
    hour = pod_date.hour
    minute = pod_date.minute

    cmd_body += bytes([month, day, year - 2000, hour, minute])

    cmd_body += struct.pack(">I", lot)
    cmd_body += struct.pack(">I", tid)
    return _cm(PdmRequest.SetupPod, cmd_body)


def request_set_low_reservoir_alert(iu_reservoir_level):
    cmd_body = bytes([0, 0, 0, 0])
    cmd_body += alert_configuration_message_body(PodAlertBit.LowReservoir,
                                                 activate=True,
                                                 trigger_auto_off=False,
                                                 duration_minutes=60,
                                                 alert_after_reservoir=iu_reservoir_level,
                                                 beep_type=BeepType.BipBip,
                                                 beep_repeat_type=BeepPattern.OnceEveryHour)
    return _cm(PdmRequest.ConfigureAlerts, cmd_body)


def request_clear_low_reservoir_alert():
    pass


def request_set_pod_expiry_alert(minutes_after_activation):
    cmd_body = bytes([0, 0, 0, 0])
    cmd_body += alert_configuration_message_body(PodAlertBit.LowReservoir,
                                                 activate=True,
                                                 trigger_auto_off=False,
                                                 duration_minutes=60,
                                                 alert_after_reservoir=iu_reservoir_level,
                                                 beep_type=BeepType.BipBip,
                                                 beep_repeat_type=BeepPattern.OnceEveryHour)
    return _cm(PdmRequest.ConfigureAlerts, cmd_body)


def request_clear_pod_expiry_alert():
    pass


def request_set_generic_alert(minutes_after_set, repeat_interval):
    cmd_body = bytes([0, 0, 0, 0])
    cmd_body += alert_configuration_message_body(PodAlertBit.TimerLimit,
                                                 activate=True,
                                                 trigger_auto_off=False,
                                                 duration_minutes=55,
                                                 alert_after_minutes=5,
                                                 beep_repeat_type=BeepPattern.OnceEveryMinuteForThreeMinutesAndRepeatEveryFifteenMinutes,
                                                 beep_type=BeepType.BipBipBipTwice)
    return _cm(PdmRequest.ConfigureAlerts, cmd_body)


def request_clear_generic_alert():
    pass


def request_set_basal_schedule(basal_schedule):
    pass


def request_prime_cannula():
    pass


def request_insert_cannula():
    pass


def request_status(status_request_type=0):
    cmd_body = bytes([status_request_type])
    return _cm(PdmRequest.Status, cmd_body)


def request_acknowledge_alerts(alert_mask):
    cmd_type = 0x11
    cmd_body = bytes([0, 0, 0, 0, alert_mask])
    return _cm(PdmRequest.AcknowledgeAlerts, cmd_body)


def request_purge_insulin(iu_to_purge):
    pass


def request_bolus(iu_bolus):
    pass


def request_cancel_bolus():
    pass


def request_temp_basal(basal_rate_iuhr, duration_hours):
    pass


def request_cancel_temp_basal():
    pass


def request_stop_basal_insulin():
    pass


def request_resume_basal_insulin():
    pass


def request_deactivate():
    pass
