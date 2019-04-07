from .definitions import *
import simplejson as json
from datetime import datetime
import sqlite3

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
        self.var_alert_low_reservoir_set = False
        self.var_alert_replace_pod = None
        self.var_alert_replace_pod_set = False
        self.var_alert_before_prime_set = False
        self.var_alert_after_prime_set = False
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

        self.var_utc_offset = None
        self.var_activation_date = None
        self.var_insertion_date = None

        self.path = None
        self.log_file_path = None

        self.last_command = None
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
            self.path = "./unnamed_pod.json"
            self.log_file_path = "./unnamed_pod.log"

        self.log()

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

            p.id_lot = d.get("id_lot", None)
            p.id_t = d.get("id_t", None)
            p.id_version_pm = d.get("id_version_pm", None)
            p.id_version_pi = d.get("id_version_pi", None)
            p.id_version_unknown_byte = d.get("id_version_unknown_byte", None)
            p.id_version_unknown_7_bytes = d.get("id_version_unknown_7_bytes", None)

            p.radio_address = d.get("radio_address", None)
            p.radio_packet_sequence = d.get("radio_packet_sequence", None)
            p.radio_message_sequence = d.get("radio_message_sequence", None)
            p.radio_low_gain = d.get("radio_low_gain", None)
            p.radio_rssi = d.get("radio_rssi", None)

            p.state_last_updated = d.get("state_last_updated", None)
            p.state_progress = d.get("state_progress", None)
            p.state_basal = d.get("state_basal", None)
            p.state_bolus = d.get("state_bolus", None)
            p.state_alert = d.get("state_alert", None)
            p.state_active_minutes = d.get("state_active_minutes", None)
            p.state_faulted = d.get("state_faulted", None)

            p.fault_event = d.get("fault_event", None)
            p.fault_event_rel_time = d.get("fault_event_rel_time", None)
            p.fault_table_access = d.get("fault_table_access", None)
            p.fault_insulin_state_table_corruption = d.get("fault_insulin_state_table_corruption", None)
            p.fault_internal_variables = d.get("fault_internal_variables", None)
            p.fault_immediate_bolus_in_progress = d.get("fault_immediate_bolus_in_progress", None)
            p.fault_progress_before = d.get("fault_progress_before", None)
            p.fault_progress_before_2 = d.get("fault_progress_before_2", None)
            p.fault_information_type2_last_word = d.get("fault_information_type2_last_word", None)

            p.insulin_delivered = d.get("insulin_delivered", None)
            p.insulin_canceled = d.get("insulin_canceled", None)
            p.insulin_reservoir = d.get("insulin_reservoir", None)

            p.nonce_last = d.get("nonce_last", None)
            p.nonce_seed = d.get("nonce_seed", None)
            p.nonce_syncword = d.get("nonce_syncword", None)

            p.last_command = d.get("last_command", None)
            p.last_enacted_temp_basal_start = d.get("last_enacted_temp_basal_start", None)
            p.last_enacted_temp_basal_duration = d.get("last_enacted_temp_basal_duration", None)
            p.last_enacted_temp_basal_amount = d.get("last_enacted_temp_basal_amount", None)
            p.last_enacted_bolus_start = d.get("last_enacted_bolus_start", None)
            p.last_enacted_bolus_amount = d.get("last_enacted_bolus_amount", None)

            p.var_utc_offset = d.get("var_utc_offset", None)
            p.var_activation_date = d.get("var_activation_date", None)
            p.var_insertion_date = d.get("var_insertion_date", None)
            p.var_basal_schedule = d.get("var_basal_schedule", None)
            p.var_maximum_bolus = d.get("var_maximum_bolus", None)
            p.var_maximum_temp_basal_rate = d.get("var_maximum_temp_basal_rate", None)
            p.var_alert_low_reservoir = d.get("var_alert_low_reservoir", None)
            p.var_alert_low_reservoir_set = d.get("var_alert_low_reservoir_set", False)
            p.var_alert_replace_pod = d.get("var_alert_replace_pod", None)
            p.var_alert_replace_pod_set = d.get("var_alert_replace_pod_set", False)
            p.var_alert_before_prime_set = d.get("var_alert_before_prime_set", False)
            p.var_alert_after_prime_set = d.get("var_alert_after_prime_set", False)

            p.var_notify_bolus_start = d.get("var_notify_bolus_start", None)
            p.var_notify_bolus_cancel = d.get("var_notify_bolus_cancel", None)
            p.var_notify_temp_basal_set = d.get("var_notify_temp_basal_set", None)
            p.var_notify_temp_basal_cancel = d.get("var_notify_temp_basal_cancel", None)
            p.var_notify_basal_schedule_change = d.get("var_notify_basal_schedule_change", None)

        return p

    def is_active(self):
        return not(self.id_lot is None or self.id_t is None or self.radio_address is None) \
            and (self.state_progress == PodProgress.Running or self.state_progress == PodProgress.RunningLow) \
            and not self.state_faulted


    def __str__(self):
        return json.dumps(self.__dict__, indent=4, sort_keys=True)

    def log(self):
        pass

    def _get_conn(self):
        conn = sqlite3.connect(self.log_file_path)
        sql = """ CREATE TABLE IF NOT EXISTS pod_history (
                  timestamp real, 
                  pod_state integer, pod_minutes integer, pod_last_command text,
                  insulin_delivered real, insulin_canceled real, insulin_reservoir real
                  ) """

        c = conn.cursor()
        c.execute(sql)
        return conn

    def _sql(self, sql):
        conn = sqlite3.connect(self.log_file_path)
        c = conn.cursor()
        c.execute(sql)