from podcomm.pod import Pod
from podcomm.protocol_common import *
from podcomm.definitions import *
from enum import IntEnum
import struct
from datetime import datetime, timedelta


class StatusRequestType(IntEnum):
    Standard = 0


def request_assign_address(address):
    cmd_body = struct.pack(">I", address)
    return PdmMessage(PdmRequest.AssignAddress, cmd_body)


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
    return PdmMessage(PdmRequest.SetupPod, cmd_body)


def request_set_low_reservoir_alert(iu_reservoir_level):
    cmd_body = alert_configuration_message_body(PodAlertBit.LowReservoir,
                                                 activate=True,
                                                 trigger_auto_off=False,
                                                 duration_minutes=60,
                                                 alert_after_reservoir=iu_reservoir_level,
                                                 beep_type=BeepType.BipBip,
                                                 beep_repeat_type=BeepPattern.OnceEveryHour)
    return PdmMessage(PdmRequest.ConfigureAlerts, cmd_body)


def request_clear_low_reservoir_alert():
    pass


def request_set_pod_expiry_alert(minutes_after_activation):
    cmd_body = alert_configuration_message_body(PodAlertBit.LowReservoir,
                                                 activate=True,
                                                 trigger_auto_off=False,
                                                 duration_minutes=60,
                                                 alert_after_minutes=minutes_after_activation,
                                                 beep_type=BeepType.BipBip,
                                                 beep_repeat_type=BeepPattern.OnceEveryHour)
    return PdmMessage(PdmRequest.ConfigureAlerts, cmd_body)


def request_clear_pod_expiry_alert():
    pass


def request_set_generic_alert(minutes_after_set, repeat_interval):
    cmd_body = alert_configuration_message_body(PodAlertBit.TimerLimit,
                                                 activate=True,
                                                 trigger_auto_off=False,
                                                 duration_minutes=55,
                                                 alert_after_minutes=5,
                                                 beep_repeat_type=BeepPattern.OnceEveryMinuteForThreeMinutesAndRepeatEveryFifteenMinutes,
                                                 beep_type=BeepType.BipBipBipTwice)
    return PdmMessage(PdmRequest.ConfigureAlerts, cmd_body)


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
    return PdmMessage(PdmRequest.Status, cmd_body)


def request_acknowledge_alerts(alert_mask):
    cmd_body = bytes([alert_mask])
    return PdmMessage(PdmRequest.AcknowledgeAlerts, cmd_body)


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


def response_parse(response: PodMessage, pod: Pod):
    parts = response.get_parts()
    for response_type, response_body in parts:
        if response_type == 0x01:
            parse_version_response(response_body, pod)
        elif response_type == 0x02:
            parse_information_response(response_body, pod)
        elif response_type == 0x1d:
            parse_status_response(response_body, pod)


def parse_information_response(response, pod):
        if response[0] == 0x01:
            pass
        elif response[0] == 0x02:
            pod.state_faulted = True
            pod.state_progress = response[1]
            pod.__parse_delivery_state(response[2])
            pod.insulin_canceled = struct.unpack(">H", response[3:5])[0] * 0.05
            pod.radio_message_sequence = response[5]
            pod.insulin_delivered = struct.unpack(">H", response[6:8])[0] * 0.05
            pod.fault_event = response[8]
            pod.fault_event_rel_time = struct.unpack(">H", response[9:11])[0]
            pod.insulin_reservoir = struct.unpack(">H", response[11:13])[0] * 0.05
            pod.state_active_minutes = struct.unpack(">H", response[13:15])[0]
            pod.state_alert = response[15]
            pod.fault_table_access = response[16]
            pod.fault_insulin_state_table_corruption = response[17] >> 7
            pod.fault_internal_variables = (response[17] & 0x60) >> 6
            pod.fault_immediate_bolus_in_progress = (response[17] & 0x10) >> 4
            pod.fault_progress_before = (response[17] & 0x0F)
            pod.radio_low_gain = (response[18] & 0xC0) >> 6
            pod.radio_rssi = response[18] & 0x3F
            pod.fault_progress_before_2 = (response[19] & 0x0F)
            pod.fault_information_type2_last_word = struct.unpack(">H", response[20:22])[0]
        elif response[0] == 0x03:
            pass
        elif response[0] == 0x05:
            pass
        elif response[0] == 0x06:
            pass
        elif response[0] == 0x46:
            pass
        elif response[0] == 0x50:
            pass
        elif response[0] == 0x51:
            pass
        else:
            raise ProtocolError("Failed to parse the information response of type 0x%2X with content: %s"
                                % (response[0], response.hex()))

def parse_status_response(response, pod):
    s = struct.unpack(">BII", response)

    parse_delivery_state(pod, s[0] >> 4)
    pod.state_progress = PodProgress([0] & 0xF)

    pod.radio_message_sequence = (s[1] & 0x00007800) >> 11

    pod.insulin_delivered = ((s[1] & 0x0FFF8000) >> 15) * 0.05
    pod.insulin_canceled = (s[1] & 0x000007FF) * 0.05

    pod.state_faulted = ((s[2] >> 31) != 0)
    pod.state_alert = (s[2] >> 23) & 0xFF
    pod.state_active_minutes = (s[2] & 0x007FFC00) >> 10
    pod.insulin_reservoir = (s[2] & 0x000003FF) * 0.05

def parse_delivery_state(pod, delivery_state):
    if delivery_state & 8 > 0:
        pod.state_bolus = BolusState.Extended
    elif delivery_state & 4 > 0:
        pod.state_bolus = BolusState.Immediate
    else:
        pod.state_bolus = BolusState.NotRunning

    if delivery_state & 2 > 0:
        pod.state_basal = BasalState.TempBasal
    elif delivery_state & 1 > 0:
        pod.state_basal = BasalState.Program
    else:
        pod.state_basal = BasalState.NotRunning

def parse_version_response(response, pod):
    if len(response) == 27:
        pod.id_version_unknown_7_bytes = response[0:7].hex()
        response = response[7:]

    mx = response[0]
    my = response[1]
    mz = response[2]
    pod.id_version_pm = "%d.%d.%d" % (mx, my, mz)

    ix = response[3]
    iy = response[4]
    iz = response[5]
    pod.id_version_pi = "%d.%d.%d" % (ix, iy, iz)

    pod.id_version_unknown_byte = "%d" % response[6]
    pod.state_progress = response[7] & 0x0F
    pod.id_lot = struct.unpack(">I", response[8:12])[0]
    pod.id_t = struct.unpack(">I", response[12:16])[0]
    pod.radio_address = struct.unpack(">I", response[16:20])[0]