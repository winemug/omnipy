from .exceptions import ProtocolError
from .definitions import *
import simplejson as json
import struct
from datetime import datetime, timedelta
import binascii
import time


class Pod:
    def __init__(self):
        self.id_lot = None
        self.id_t = None
        self.id_version_pm = None
        self.id_version_pi = None
        self.id_version_unknown_byte = None
        self.id_version_unknown_7_bytes = None

        self.radio_address = None
        self.radio_address_candidate = None
        self.radio_packet_sequence = 0
        self.radio_message_sequence = 0
        self.radio_low_gain = None
        self.radio_rssi = None

        self.nonce_last = None
        self.nonce_seed = 0

        self.state_last_updated = None
        self.state_progress = PodProgress.InitialState
        self.state_basal = BasalState.NotRunning
        self.state_bolus = BolusState.NotRunning
        self.state_alert = 0
        self.state_active_minutes=0
        self.state_faulted = False

        self.var_maximum_bolus = None
        self.var_maximum_temp_basal_rate = None
        self.var_alert_low_reservoir = None
        self.var_alert_replace_pod = None
        self.var_basal_schedule = None
        self.var_notify_bolus_start = None
        self.var_notify_bolus_cancel = None
        self.var_notify_temp_basal_set = None
        self.var_notify_temp_basal_cancel = None
        self.var_notify_basal_schedule_change = None

        self.fault_event = None
        self.fault_event_rel_time = None
        self.fault_table_access = None
        self.fault_insulin_state_table_corruption = None
        self.fault_internal_variables = None
        self.fault_immediate_bolus_in_progress = None
        self.fault_progress_before = None
        self.fault_progress_before_2 = None
        self.fault_information_type2_last_word = None

        self.insulin_reservoir = 0
        self.insulin_delivered = 0
        self.insulin_canceled = 0

        self.var_utc_offset=None
        self.path = None
        self.log_file_path = None

        self.last_enacted_temp_basal_start = None
        self.last_enacted_temp_basal_duration = None
        self.last_enacted_temp_basal_amount = None

        self.last_enacted_bolus_start = None
        self.last_enacted_bolus_amount = None

    def Save(self, save_as = None):
        if save_as is not None:
            self.path = save_as
            self.log_file_path = save_as + POD_LOG_SUFFIX
        if self.path is None:
            raise ValueError("No filename given")
        with open(self.path, "w") as stream:
            json.dump(self.__dict__, stream, indent=4, sort_keys=True)

    @staticmethod
    def Load(path, log_file_path=None):
        if log_file_path is None:
            log_file_path = path + POD_LOG_SUFFIX

        with open(path, "r") as stream:
            d = json.load(stream)
            p = Pod()
            p.path = path
            p.log_file_path = log_file_path

            p.id_lot = d["id_lot"]
            p.id_t = d["id_t"]
            p.id_version_pm = d["id_version_pm"]
            p.id_version_pi = d["id_version_pi"]
            p.id_version_unknown_byte = d["id_version_unknown_byte"]
            p.id_version_unknown_7_bytes = d["id_version_unknown_7_bytes"]

            p.radio_address = d["radio_address"]
            p.radio_address_candidate = d["radio_address_candidate"]
            p.radio_packet_sequence = d["radio_packet_sequence"]
            p.radio_message_sequence = d["radio_message_sequence"]
            p.radio_low_gain = d["radio_low_gain"]
            p.radio_rssi = d["radio_rssi"]

            p.state_last_updated = d["state_last_updated"]
            p.state_progress = d["state_progress"]
            p.state_basal = d["state_basal"]
            p.state_bolus = d["state_bolus"]
            p.state_alert = d["state_alert"]
            p.state_active_minutes = d["state_active_minutes"]
            p.state_faulted = d["state_faulted"]

            p.fault_event = d["fault_event"]
            p.fault_event_rel_time = d["fault_event_rel_time"]
            p.fault_table_access = d["fault_table_access"]
            p.fault_insulin_state_table_corruption = d["fault_insulin_state_table_corruption"]
            p.fault_internal_variables = d["fault_internal_variables"]
            p.fault_immediate_bolus_in_progress = d["fault_immediate_bolus_in_progress"]
            p.fault_progress_before = d["fault_progress_before"]
            p.fault_progress_before_2 = d["fault_progress_before_2"]
            p.fault_information_type2_last_word = d["fault_information_type2_last_word"]

            p.insulin_delivered = d["insulin_delivered"]
            p.insulin_canceled = d["insulin_canceled"]
            p.insulin_reservoir = d["insulin_reservoir"]

            p.nonce_last = d["nonce_last"]
            p.nonce_seed = d["nonce_seed"]

            p.last_enacted_temp_basal_start = d["last_enacted_temp_basal_start"]
            p.last_enacted_temp_basal_duration = d["last_enacted_temp_basal_duration"]
            p.last_enacted_temp_basal_amount = d["last_enacted_temp_basal_amount"]
            p.last_enacted_bolus_start = d["last_enacted_bolus_start"]
            p.last_enacted_bolus_amount = d["last_enacted_bolus_amount"]

            p.var_utc_offset = d["var_utc_offset"]
            p.var_basal_schedule = d["var_basal_schedule"]
            p.var_maximum_bolus = d["var_maximum_bolus"]
            p.var_maximum_temp_basal_rate = d["var_maximum_temp_basal_rate"]
            p.var_alert_low_reservoir = d["var_alert_low_reservoir"]
            p.var_alert_replace_pod = d["var_alert_replace_pod"]
            p.var_notify_bolus_start = d["var_notify_bolus_start"]
            p.var_notify_bolus_cancel = d["var_notify_bolus_cancel"]
            p.var_notify_temp_basal_set = d["var_notify_temp_basal_set"]
            p.var_notify_temp_basal_cancel = d["var_notify_temp_basal_cancel"]
            p.var_notify_basal_schedule_change = d["var_notify_basal_schedule_change"]

        return p

    def is_active(self):
        return not(self.id_lot is None or self.id_t is None or self.radio_address is None) \
            and (self.state_progress == PodProgress.Running or self.state_progress == PodProgress.RunningLow) \
            and not self.state_faulted

    def handle_version_response(self, message_body):
        candidate_only = True
        if len(message_body) == 27:
            self.id_version_unknown_7_bytes = "%s" % str(message_body[0:7])
            candidate_only = False
            message_body = message_body[7:]

        mx = message_body[0]
        my = message_body[1]
        mz = message_body[2]
        self.id_version_pm = "%d.%d.%d" % (mx, my, mz)

        ix = message_body[3]
        iy = message_body[4]
        iz = message_body[5]
        self.id_version_pi = "%d.%d.%d" % (ix, iy, iz)

        self.id_version_unknown_byte = "%d" % message_body[6]
        self.state_progress = message_body[7] & 0x0F
        self.id_lot = struct.unpack(">I", message_body[8:12])[0]
        self.id_t = struct.unpack(">I", message_body[12:16])[0]
        address = struct.unpack(">I", message_body[16:20])[0]
        if candidate_only:
            self.radio_address_candidate = address
        else:
            self.radio_address = address

    def handle_information_response(self, response, original_request=None):
        if response[0] == 0x01:
            pass
        elif response[0] == 0x02:
            self.state_faulted = True
            self.state_progress = response[1]
            self.__parse_delivery_state(response[2])
            self.insulin_canceled = struct.unpack(">H", response[3:5])[0] * 0.05
            self.radio_message_sequence = response[5]
            self.insulin_delivered = struct.unpack(">H", response[6:8])[0] * 0.05
            self.fault_event = response[8]
            self.fault_event_rel_time = struct.unpack(">H", response[9:11])[0]
            self.insulin_reservoir = struct.unpack(">H", response[11:13])[0] * 0.05
            self.state_active_minutes = struct.unpack(">H", response[13:15])[0]
            self.state_alert = response[15]
            self.fault_table_access = response[16]
            self.fault_insulin_state_table_corruption = response[17] >> 7
            self.fault_internal_variables = (response[17] & 0x60) >> 6
            self.fault_immediate_bolus_in_progress = (response[17] & 0x10) >> 4
            self.fault_progress_before = (response[17] & 0x0F)
            self.radio_low_gain = (response[18] & 0xC0) >> 6
            self.radio_rssi = response[18] & 0x3F
            self.fault_progress_before_2 = (response[19] & 0x0F)
            self.fault_information_type2_last_word = struct.unpack(">H", response[20:22])[0]
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
                                % (response[0], binascii.hexlify(response)))

        self._save_with_log(original_request)

    def handle_status_response(self, response, original_request=None):
        s = struct.unpack(">BII", response)
        state = s[0]
        insulin_pulses = (s[1] & 0x0FFF8000) >> 15
        msg_sequence = (s[1] & 0x00007800) >> 11
        canceled_pulses = s[1] & 0x000007FF

        self.state_faulted = ((s[2] >> 31) != 0)
        pod_alarm = (s[2] >> 23) & 0xFF
        pod_active_time = (s[2] & 0x007FFC00) >> 10
        pod_reservoir = s[2] & 0x000003FF

        self.__parse_delivery_state(state >> 4)

        self.state_progress = state & 0xF

        self.state_alert = pod_alarm
        self.insulin_reservoir = pod_reservoir * 0.05
        self.radio_message_sequence = msg_sequence
        self.insulin_delivered = insulin_pulses * 0.05
        self.insulin_canceled = canceled_pulses * 0.05
        self.state_active_minutes = pod_active_time
        self.state_last_updated = time.time()
        self._save_with_log(original_request)

    def _save_with_log(self, original_request):
        ds = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        orq = "----"
        if original_request is not None:
            orq = original_request

        self.Save()

        self.log("%d\t%s\t%s\t%f\t%f\t%d\t%s\t%s\t%s\t%d\t%s\t%s\t%d\t%d\t0x%8X\n" % \
                 (self.state_last_updated, ds, orq, self.insulin_delivered, self.insulin_canceled, self.state_active_minutes,
                  PodProgress(self.state_progress).name,
                  BolusState(self.state_bolus).name, BasalState(self.state_basal).name, self.insulin_reservoir, self.state_alert,
                  self.state_faulted, self.id_lot, self.id_t, self.radio_address))

    def __parse_delivery_state(self, delivery_state):
        if delivery_state & 8 > 0:
            self.state_bolus = BolusState.Extended
        elif delivery_state & 4 > 0:
            self.state_bolus = BolusState.Immediate
        else:
            self.state_bolus = BolusState.NotRunning

        if delivery_state & 2 > 0:
            self.state_basal = BasalState.TempBasal
        elif delivery_state & 1 > 0:
            self.state_basal = BasalState.Program
        else:
            self.state_basal = BasalState.NotRunning

    def __str__(self):
        p = self
        state = "Lot %d Tid %d Address 0x%8X Faulted: %s\n" % (p.id_lot, p.id_t, p.radio_address, p.state_faulted)
        state += "Updated %s\nState: %s\nAlarm: %s\nBasal: %s\nBolus: %s\nReservoir: %dU\n" %\
                 (p.state_last_updated, p.state_progress, p.state_alert, p.state_basal, p.state_bolus, p.insulin_reservoir)
        state += "Insulin delivered: %fU canceled: %fU\nTime active: %s" %\
                 (p.insulin_delivered, p.insulin_canceled, timedelta(minutes=p.state_active_minutes))
        return state

    def log(self, log_message):
        try:
            with open(self.log_file_path, "a") as stream:
                stream.write(log_message)
        except Exception as e:
            getLogger().warning("Failed to write the following line to the pod log file %s:\n%s\nError: %s"
                            %(self.log_file_path, log_message, e))
