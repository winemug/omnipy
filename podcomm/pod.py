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
        self.radio_packet_sequence = 0
        self.radio_message_sequence = 0
        self.radio_low_gain = None
        self.radio_rssi = None

        self.nonce_last = None
        self.nonce_seed = 0
        self.nonce_syncword = None

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
            p.nonce_syncword = d["nonce_syncword"]

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

    def _save_with_log(self, original_request):
        ds = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        orq = "----"
        if original_request is not None:
            orq = original_request

        self.Save()
        self.log()

    def __str__(self):
        return json.dumps(self.__dict__, indent=4, sort_keys=True)

    def log(self, log_message):
        try:
            with open(self.log_file_path, "a") as stream:
                stream.write(json.dumps(self.__dict__, sort_keys=True))
        except Exception as e:
            getLogger().warning("Failed to write the following line to the pod log file %s:\n%s\nError: %s"
                            %(self.log_file_path, log_message, e))
