from .exceptions import ProtocolError
from .definitions import *
import simplejson as json
import struct
from datetime import datetime, timedelta
import binascii
import time


class Pod:
    def __init__(self):
        self.lot=0
        self.tid=0

        self.lastUpdated = None
        self.progress=PodProgress.InitialState
        self.basalState=BasalState.NotRunning
        self.bolusState=BolusState.NotRunning
        self.alert_states = 0
        self.reservoir=0
        self.minutes_since_activation=0
        self.faulted = False
        self.fault_event = None
        self.fault_event_rel_time = None
        self.fault_table_access = None
        self.fault_insulin_state_table_corruption = None
        self.fault_internal_variables = None
        self.fault_immediate_bolus_in_progress = None
        self.fault_progress_before = None
        self.radio_low_gain = None
        self.radio_rssi = None
        self.fault_progress_before_2 = None
        self.information_type2_last_word = None

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
        self.log_file_path = None

        self.last_enacted_temp_basal_start = None
        self.last_enacted_temp_basal_duration = None
        self.last_enacted_temp_basal_amount = None

        self.last_enacted_bolus_start = None
        self.last_enacted_bolus_amount = None

        self.version_pm = None
        self.version_pi = None
        self.version_unknown_byte = None
        self.version_unknown_7_bytes = None
        self.address_candidate = None

        self.setting_low_reservoir_alert = None
        self.setting_replace_pod_alert = None

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
            p.lot=d["lot"]
            p.tid=d["tid"]
        
            p.lastUpdated=d["lastUpdated"]
            p.progress=d["progress"]
            p.basalState=d["basalState"]
            p.bolusState=d["bolusState"]
            p.alert_states = d["alert_states"]
            p.reservoir=d["reservoir"]
            p.minutes_since_activation = d["minutes_since_activation"]
            p.faulted=d["faulted"]
            p.fault_event = d["fault_event"]
            p.fault_event_rel_time = d["fault_event_rel_time"]
            p.fault_table_access = d["fault_table_access"]
            p.fault_insulin_state_table_corruption = d["fault_insulin_state_table_corruption"]
            p.fault_internal_variables = d["fault_internal_variables"]
            p.fault_immediate_bolus_in_progress = d["fault_immediate_bolus_in_progress"]
            p.fault_progress_before = d["fault_progress_before"]
            p.radio_low_gain = d["radio_low_gain"]
            p.radio_rssi = d["radio_rssi"]
            p.fault_progress_before_2 = d["fault_progress_before_2"]
            p.information_type2_last_word = d["information_type2_last_word"]

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

            p.last_enacted_temp_basal_start = d["last_enacted_temp_basal_start"]
            p.last_enacted_temp_basal_duration = d["last_enacted_temp_basal_duration"]
            p.last_enacted_temp_basal_amount = d["last_enacted_temp_basal_amount"]

            p.last_enacted_bolus_start = d["last_enacted_bolus_start"]
            p.last_enacted_bolus_amount = d["last_enacted_bolus_amount"]

            p.version_pm = d["version_pm"]
            p.version_pi = d["version_pi"]
            p.version_unknown_byte = d["version_unknown_byte"]
            p.version_unknown_7_bytes = d["version_unknown_7_bytes"]
            p.address_candidate = d["address_candidate"]

            p.setting_low_reservoir_alert = d["setting_low_reservoir_alert"]
            p.setting_replace_pod_alert = d["setting_replace_pod_alert"]

        return p

    def is_active(self):
        return not(self.lot is None or self.tid is None or self.address is None) \
            and (self.progress == PodProgress.Running or self.progress == PodProgress.RunningLow) \
            and not self.faulted

    def handle_version_response(self, message_body):
        candidate_only = True
        if len(message_body) == 27:
            self.version_unknown_7_bytes = "%s" % str(message_body[0:7])
            candidate_only = False
            message_body = message_body[7:]

        mx = message_body[0]
        my = message_body[1]
        mz = message_body[2]
        self.version_pm = "%d.%d.%d" % (mx, my, mz)

        ix = message_body[3]
        iy = message_body[4]
        iz = message_body[5]
        self.version_pi = "%d.%d.%d" % (ix, iy, iz)

        self.version_unknown_byte = "%d" % message_body[6]
        self.progress = message_body[7] & 0x0F
        self.lot = struct.unpack(">I", message_body[8:12])[0]
        self.tid = struct.unpack(">I", message_body[12:16])[0]
        address = struct.unpack(">I", message_body[16:20])[0]
        if candidate_only:
            self.address_candidate = address
        else:
            self.address = address

    def handle_information_response(self, response, original_request=None):
        if response[0] == 0x01:
            pass
        elif response[0] == 0x02:
            self.faulted = True
            self.progress = response[1]
            self.__parse_delivery_state(response[2])
            self.canceledInsulin = struct.unpack(">H", response[3:5])[0] * 0.05
            self.msgSequence = response[5]
            self.totalInsulin = struct.unpack(">H", response[6:8])[0] * 0.05
            self.fault_event = response[8]
            self.fault_event_rel_time = struct.unpack(">H", response[9:11])[0]
            self.reservoir = struct.unpack(">H", response[11:13])[0] * 0.05
            self.minutes_since_activation = struct.unpack(">H", response[13:15])[0]
            self.alert_states = response[15]
            self.fault_table_access = response[16]
            self.fault_insulin_state_table_corruption = response[17] >> 7
            self.fault_internal_variables = (response[17] & 0x60) >> 6
            self.fault_immediate_bolus_in_progress = (response[17] & 0x10) >> 4
            self.fault_progress_before = (response[17] & 0x0F)
            self.radio_low_gain = (response[18] & 0xC0) >> 6
            self.radio_rssi = response[18] & 0x3F
            self.fault_progress_before_2 = (response[19] & 0x0F)
            self.information_type2_last_word = struct.unpack(">H", response[20:22])[0]
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

        self.faulted = ((s[2] >> 31) != 0)
        pod_alarm = (s[2] >> 23) & 0xFF
        pod_active_time = (s[2] & 0x007FFC00) >> 10
        pod_reservoir = s[2] & 0x000003FF

        self.__parse_delivery_state(state >> 4)

        self.progress = state & 0xF

        self.alert_states = pod_alarm
        self.reservoir = pod_reservoir * 0.05
        self.msgSequence = msg_sequence
        self.totalInsulin = insulin_pulses * 0.05
        self.canceledInsulin = canceled_pulses * 0.05
        self.minutes_since_activation = pod_active_time
        self.lastUpdated = time.time()
        self._save_with_log(original_request)

    def _save_with_log(self, original_request):
        ds = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        orq = "----"
        if original_request is not None:
            orq = original_request

        self.Save()

        self.log("%d\t%s\t%s\t%f\t%f\t%d\t%s\t%s\t%s\t%d\t%s\t%s\t%d\t%d\t0x%8X\n" % \
                 (self.lastUpdated, ds, orq, self.totalInsulin, self.canceledInsulin, self.minutes_since_activation,
                  PodProgress(self.progress).name,
                  BolusState(self.bolusState).name, BasalState(self.basalState).name, self.reservoir, self.alert_states,
                  self.faulted, self.lot, self.tid, self.address))

    def __parse_delivery_state(self, delivery_state):
        if delivery_state & 8 > 0:
            self.bolusState = BolusState.Extended
        elif delivery_state & 4 > 0:
            self.bolusState = BolusState.Immediate
        else:
            self.bolusState = BolusState.NotRunning

        if delivery_state & 2 > 0:
            self.basalState = BasalState.TempBasal
        elif delivery_state & 1 > 0:
            self.basalState = BasalState.Program
        else:
            self.basalState = BasalState.NotRunning

    def __str__(self):
        p = self
        state = "Lot %d Tid %d Address 0x%8X Faulted: %s\n" % (p.lot, p.tid, p.address, p.faulted)
        state += "Updated %s\nState: %s\nAlarm: %s\nBasal: %s\nBolus: %s\nReservoir: %dU\n" %\
                 (p.lastUpdated, p.progress, p.alert_states, p.basalState, p.bolusState, p.reservoir)
        state += "Insulin delivered: %fU canceled: %fU\nTime active: %s" %\
                 (p.totalInsulin, p.canceledInsulin, timedelta(minutes=p.minutes_since_activation))
        return state

    def log(self, log_message):
        try:
            with open(self.log_file_path, "a") as stream:
                stream.write(log_message)
        except Exception as e:
            getLogger().warning("Failed to write the following line to the pod log file %s:\n%s\nError: %s"
                            %(self.log_file_path, log_message, e))
