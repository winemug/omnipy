from .protocol import *
from .protocol_radio import PdmRadio
from .nonce import *
from .exceptions import PdmError, OmnipyError, PdmBusyError
from .definitions import *
from .packet_radio import TxPower
from decimal import *
from datetime import datetime, timedelta
from threading import RLock
import time


g_lock = RLock()


class PdmLock():
    def __init__(self, timeout=2):
        self.fd = None
        self.timeout = timeout

    def __enter__(self):
        if not g_lock.acquire(blocking=True, timeout=self.timeout):
            raise PdmBusyError()

    def __exit__(self, exc_type, exc_val, exc_tb):
        g_lock.release()


class Pdm:
    def __init__(self, pod):
        if pod is None:
            raise PdmError("Cannot instantiate pdm without pod")

        self.pod = pod
        self.nonce = None
        self.radio = None
        self.logger = getLogger()

    def get_nonce(self):
        if self.nonce is None:
            if self.pod.id_lot is None or self.pod.id_t is None:
                raise PdmError("Cannot generate nonce without pod lot and id")
            if self.pod.nonce_last is None or self.pod.nonce_seed is None:
                self.nonce = Nonce(self.pod.id_lot, self.pod.id_t)
            else:
                self.nonce = Nonce(self.pod.id_lot, self.pod.id_t, self.pod.nonce_last, self.pod.nonce_seed)
        return self.nonce

    def get_radio(self):
        if self.radio is None:
            if self.pod.radio_message_sequence is None or self.pod.radio_packet_sequence is None:
                self.pod.radio_message_sequence = 0
                self.pod.radio_packet_sequence = 0

            self.radio = PdmRadio(self.pod.radio_address,
                                  msg_sequence=self.pod.radio_message_sequence,
                                  pkt_sequence=self.pod.radio_packet_sequence)

        return self.radio

    def send_request(self, request, with_nonce=False, double_take=False):

        if with_nonce:
            nonce_obj = self.get_nonce()
            nonce_val = nonce_obj.getNext()
            request.set_nonce(nonce_val)
            self.pod.nonce_last = nonce_val
            self.pod.nonce_seed = nonce_obj.seed

        response = self.get_radio().send_message_get_message(request, double_take=double_take)
        response_parse(response, self.pod)

        if with_nonce and self.pod.nonce_syncword is not None:
            self.logger.info("Nonce resync requested")
            nonce_obj = self.get_nonce()
            nonce_obj.sync(self.pod.nonce_syncword, request.sequence)

            nonce_val = nonce_obj.getNext()
            request.set_nonce(nonce_val)
            self.pod.nonce_last = nonce_val
            self.pod.nonce_seed = nonce_obj.seed
            self.get_radio().message_sequence = request.sequence
            response = self.get_radio().send_message_get_message(request, double_take=double_take)
            response_parse(response, self.pod)
            if self.pod.nonce_syncword is not None:
                self.get_nonce().reset()
                raise PdmError("Nonce sync failed")

    def update_status_internal(self, update_type=0):
        self._assert_pod_address_assigned()
        self.send_request(request_status(update_type))

    def update_status(self, update_type=0):
        try:
            with PdmLock():
                self.logger.info("Updating pod status, request type %d" % update_type)
                self.update_status_internal(update_type)
        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def acknowledge_alerts(self, alert_mask):
        try:
            with PdmLock():
                self._assert_pod_address_assigned()
                self.update_status_internal()
                self._assert_can_acknowledge_alerts()

                if self.pod.state_alert | alert_mask != self.pod.state_alert:
                    raise PdmError("Bitmask invalid for current alert state")

                self.logger.info("Acknowledging alerts with bitmask %d" % alert_mask)
                request = request_acknowledge_alerts(alert_mask)
                self.send_request(request, with_nonce=True)
                if self.pod.state_alert & alert_mask != 0:
                    raise PdmError("Failed to acknowledge one or more alerts")
        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def is_busy(self):
        try:
            with PdmLock(0):
                self.update_status_internal()
                return self.pod.state_bolus == BolusState.Immediate
        except PdmBusyError:
            return True
        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e

    def bolus(self, bolus_amount):
        try:
            with PdmLock():
                self._assert_pod_address_assigned()
                self.update_status_internal()
                self._assert_can_generate_nonce()
                self._assert_immediate_bolus_not_active()
                self._assert_not_faulted()
                self._assert_status_running()

                if self.pod.var_maximum_bolus is not None and bolus_amount > self.pod.var_maximum_bolus:
                    raise PdmError("Bolus exceeds defined maximum bolus of %.2fU" % self.pod.var_maximum_bolus)

                if bolus_amount < DECIMAL_0_05:
                    raise PdmError("Cannot do a bolus less than 0.05U")

                if self._is_bolus_running():
                    raise PdmError("A previous bolus is already running")

                if bolus_amount > self.pod.insulin_reservoir:
                    raise PdmError("Cannot bolus %.2f units, insulin_reservoir capacity is at: %.2f")

                self.logger.debug("Bolusing %0.2f" % float(bolus_amount))
                request = request_bolus(bolus_amount)
                self.send_request(request, with_nonce=True)

                if self.pod.state_bolus != BolusState.Immediate:
                    raise PdmError("Pod did not confirm bolus")

                self.pod.last_enacted_bolus_start = time.time()
                self.pod.last_enacted_bolus_amount = float(bolus_amount)

        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()


    def cancel_bolus(self):
        try:
            with PdmLock():
                self._assert_pod_address_assigned()
                self._assert_can_generate_nonce()
                self._assert_not_faulted()
                self._assert_status_running()

                if self._is_bolus_running():
                    self.logger.debug("Canceling running bolus")
                    request = request_cancel_bolus()
                    self.send_request(request, with_nonce=True)
                    if self.pod.state_bolus == BolusState.Immediate:
                        raise PdmError("Failed to cancel bolus")
                    else:
                        self.pod.last_enacted_bolus_amount = float(-1)
                        self.pod.last_enacted_bolus_start = time.time()
                else:
                    raise PdmError("Bolus is not running")

        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def cancel_temp_basal(self):
        try:
            with PdmLock():
                self._assert_pod_address_assigned()
                self.update_status_internal()
                self._assert_can_generate_nonce()
                self._assert_immediate_bolus_not_active()
                self._assert_not_faulted()
                self._assert_status_running()

                if self._is_temp_basal_active():
                    self.logger.debug("Canceling temp basal")
                    request = request_cancel_temp_basal()
                    self.send_request(request, with_nonce=True)
                    if self.pod.state_basal == BasalState.TempBasal:
                        raise PdmError("Failed to cancel temp basal")
                    else:
                        self.pod.last_enacted_temp_basal_duration = float(-1)
                        self.pod.last_enacted_temp_basal_start = time.time()
                        self.pod.last_enacted_temp_basal_amount = float(-1)
                else:
                    self.logger.warning("Cancel temp basal received, while temp basal was not active. Ignoring.")

        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def set_temp_basal(self, basalRate, hours, confidenceReminder=False):
        try:
            with PdmLock():
                self._assert_pod_address_assigned()
                self.update_status_internal()
                self._assert_can_generate_nonce()
                self._assert_immediate_bolus_not_active()
                self._assert_not_faulted()
                self._assert_status_running()

                if hours > 12 or hours < 0.5:
                    raise PdmError("Requested duration is not valid")

                if self.pod.var_maximum_temp_basal_rate is not None and \
                        basalRate > Decimal(self.pod.var_maximum_temp_basal_rate):
                    raise PdmError("Requested rate exceeds maximum temp basal setting")
                if basalRate > Decimal(30):
                    raise PdmError("Requested rate exceeds maximum temp basal capability")

                if self._is_temp_basal_active():
                    self.logger.debug("Canceling active temp basal before setting a new temp basal")
                    request = request_cancel_temp_basal()
                    self.send_request(request, with_nonce=True)
                    if self.pod.state_basal == BasalState.TempBasal:
                        raise PdmError("Failed to cancel running temp basal")
                self.logger.debug("Setting temp basal %02.2fU/h for %02.1fh"% (float(basalRate), float(hours)))
                request = request_temp_basal(basalRate, hours)
                self.send_request(request, with_nonce=True)

                if self.pod.state_basal != BasalState.TempBasal:
                    raise PdmError("Failed to set temp basal")
                else:
                    self.pod.last_enacted_temp_basal_duration = float(hours)
                    self.pod.last_enacted_temp_basal_start = time.time()
                    self.pod.last_enacted_temp_basal_amount = float(basalRate)

        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def set_basal_schedule(self, schedule, hours=None, minutes=None, seconds=None):
        try:
            with PdmLock():
                self._assert_pod_address_assigned()
                self.update_status_internal()
                self._assert_can_generate_nonce()
                self._assert_immediate_bolus_not_active()
                self._assert_not_faulted()
                self._assert_status_running()

                if self._is_temp_basal_active():
                    raise PdmError("Cannot change basal schedule while a temp. basal is active")

                self._assert_basal_schedule_is_valid(schedule)

                # request = request_stop_basal_insulin()
                # self.send_request(request, with_nonce=True)

                request = request_set_basal_schedule(schedule, hour=hours, minute=minutes, second=seconds)
                self.send_request(request, with_nonce=True, double_take=True)

                if self.pod.state_basal != BasalState.Program:
                    raise PdmError("Failed to set basal schedule")
                else:
                    self.pod.var_basal_schedule = schedule

        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def deactivate_pod(self):
        try:
            with PdmLock():
                self.update_status_internal()
                self._assert_can_deactivate()

                self.logger.debug("Deactivating pod")
                request = request_deactivate()
                self.send_request(request, with_nonce=True)
        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def activate_pod(self, candidate_address):
        try:
            with PdmLock():
                self._assert_pod_activate_can_start()

                radio = self.get_radio()

                radio.radio_address = 0xffffffff

                request = request_assign_address(candidate_address)
                response = self.get_radio().send_message_get_message(request, message_address=0xffffffff,
                                                                     ack_address_override=candidate_address,
                                                                     tx_power=TxPower.Lowest)
                response_parse(response, self.pod)

                self._assert_pod_can_activate()

                utc_offset = timedelta(minutes=self.pod.var_utc_offset)
                pod_date = datetime.utcnow() + utc_offset

                year = pod_date.year
                month = pod_date.month
                day = pod_date.day
                hour = pod_date.hour
                minute = pod_date.minute

                request = request_setup_pod(self.pod.id_lot, self.pod.id_t, candidate_address,
                                            year, month, day, hour, minute)
                response = self.get_radio().send_message_get_message(request, message_address=0xffffffff,
                                                                     ack_address_override=candidate_address,
                                                                     tx_power=TxPower.Lowest)
                response_parse(response, self.pod)

                self._assert_pod_paired()

                self.pod.nonce_seed = 0
                self.pod.nonce_last = None

                self.pod.radio_address = candidate_address

                if self.pod.var_alert_low_reservoir is not None:
                    request = request_set_low_reservoir_alert(self.pod.var_alert_low_reservoir)
                    self.send_request(request, with_nonce=True)

                request = request_set_generic_alert(5, 55)
                self.send_request(request, with_nonce=True)

                request = request_delivery_flags(0, 0)
                self.send_request(request, with_nonce=True)

                request = request_prime_cannula()
                self.send_request(request, with_nonce=True)

                time.sleep(55)

                while self.pod.state_progress == PodProgress.Purging:
                    time.sleep(5)
                    self.update_status_internal()

                if self.pod.var_alert_replace_pod is not None:
                    request = request_set_pod_expiry_alert(self.pod.var_alert_replace_pod - self.pod.state_active_minutes)
                    self.send_request(request, with_nonce=True)
                else:
                    self.update_status_internal()

                if self.pod.state_progress != PodProgress.ReadyForInjection:
                    raise PdmError("Pod did not reach ready for injection stage")

        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def inject_and_start(self, basal_schedule):
        try:
            with PdmLock():
                if self.pod.state_progress != PodProgress.ReadyForInjection:
                    raise PdmError("Pod is not at the injection stage")

                self._assert_basal_schedule_is_valid(basal_schedule)

                utc_offset = timedelta(minutes=self.pod.var_utc_offset)
                pod_date = datetime.utcnow() + utc_offset

                hour = pod_date.hour
                minute = pod_date.minute
                second = pod_date.second

                request = request_set_basal_schedule(basal_schedule, hour, minute, second)
                self.send_request(request)

                if self.pod.state_progress != PodProgress.BasalScheduleSet:
                    raise PdmError("Pod did not acknowledge basal schedule")



                request = request_insert_cannula()
                self.send_request(request)

                if self.pod.state_progress != PodProgress.Inserting:
                    raise PdmError("Pod did not acknowledge cannula insertion start")

                time.sleep(10)

                while self.pod.state_progress == PodProgress.Inserting:
                    time.sleep(5)
                    self.update_status_internal()

                if self.pod.state_progress != PodProgress.Running:
                    raise PdmError("Pod did not get to running state")

        except OmnipyError:
            raise
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def _savePod(self):
        try:
            self.logger.debug("Saving pod status")
            radio = self.get_radio()
            if radio is not None:
                self.pod.radio_message_sequence = radio.message_sequence
                self.pod.radio_packet_sequence = radio.packet_sequence

            nonce = self.get_nonce()
            if nonce is not None:
                self.pod.nonce_last = nonce.lastNonce
                self.pod.nonce_seed = nonce.seed

            self.pod.Save()
            self.logger.debug("Saved pod status")
        except Exception as e:
            raise PdmError("Pod status was not saved") from e

    def _is_bolus_running(self):
        if self.pod.state_last_updated is not None and self.pod.state_bolus != BolusState.Immediate:
            return False

        if self.pod.last_enacted_bolus_amount is not None \
                and self.pod.last_enacted_bolus_start is not None:

            if self.pod.last_enacted_bolus_amount < 0:
                return False

            now = time.time()
            bolus_end_earliest = (self.pod.last_enacted_bolus_amount * 35) + self.pod.last_enacted_bolus_start
            bolus_end_latest = (self.pod.last_enacted_bolus_amount * 45) + 10 + self.pod.last_enacted_bolus_start
            if now > bolus_end_latest:
                return False
            elif now < bolus_end_earliest:
                return True

        self.update_status_internal()
        return self.pod.state_bolus == BolusState.Immediate

    def _is_basal_schedule_active(self):
        if self.pod.state_last_updated is not None and self.pod.state_basal == BasalState.NotRunning:
            return False

        self.update_status_internal()
        return self.pod.state_basal == BasalState.Program

    def _is_temp_basal_active(self):
        if self.pod.state_last_updated is not None and self.pod.state_basal != BasalState.TempBasal:
            return False

        if self.pod.last_enacted_temp_basal_start is not None \
                and self.pod.last_enacted_temp_basal_duration is not None:
            if self.pod.last_enacted_temp_basal_amount < 0:
                return False
            now = time.time()
            temp_basal_end_earliest = self.pod.last_enacted_temp_basal_start + \
                                      (self.pod.last_enacted_temp_basal_duration * 3600) - 60
            temp_basal_end_latest = self.pod.last_enacted_temp_basal_start + \
                                      (self.pod.last_enacted_temp_basal_duration * 3660) + 60
            if now > temp_basal_end_latest:
                return False
            elif now < temp_basal_end_earliest:
                return True

        self.update_status_internal()
        return self.pod.state_basal == BasalState.TempBasal

    def _assert_pod_activate_can_start(self):
        self._assert_pod_address_not_assigned()

    def _assert_basal_schedule_is_valid(self, schedule):
        if schedule is None:
            raise PdmError("No basal schedule defined")

        if len(schedule) != 48:
            raise PdmError("A full schedule of 48 half hours is needed")

        min_rate = Decimal("0.05")
        max_rate = Decimal("30")

        for entry in schedule:
            if entry < min_rate:
                raise PdmError("A basal rate schedule entry cannot be less than 0.05U/h")
            if entry > max_rate:
                raise PdmError("A basal rate schedule entry cannot be more than 30U/h")

    def _assert_pod_address_not_assigned(self):
        if self.pod is None:
            raise PdmError("No pod instance created")

        if self.pod.radio_address is not None and self.pod.radio_address != 0xffffffff:
            raise PdmError("Radio radio_address already set")

    def _assert_pod_address_assigned(self):
        if self.pod.radio_address is None:
            raise PdmError("Radio address not set")

    def _assert_pod_can_activate(self):
        if self.pod is None:
            raise PdmError("No pod instance created")

        if self.pod.id_lot is None:
            raise PdmError("Lot number unknown")

        if self.pod.id_t is None:
            raise PdmError("Serial number unknown")

        if self.pod.state_progress != PodProgress.TankFillCompleted:
            raise PdmError("Pod is not at the expected state of Tank Fill Completed")

    def _assert_pod_paired(self):
        if self.pod.radio_address is None:
            raise PdmError("Radio radio_address not accepted")

        if self.pod.state_progress != PodProgress.PairingSuccess:
            raise PdmError("Progress does not indicate pairing success")

    def _assert_can_deactivate(self):
        self._assert_pod_address_assigned()
        self._assert_can_generate_nonce()
        if self.pod.state_progress < PodProgress.PairingSuccess:
            raise PdmError("Pod is not paired")
        if self.pod.state_progress > PodProgress.AlertExpiredShuttingDown:
            raise PdmError("Pod already deactivated")

    def _assert_can_acknowledge_alerts(self):
        self._assert_pod_address_assigned()
        if self.pod.state_progress < PodProgress.PairingSuccess:
            raise PdmError("Pod not paired completely yet.")

        if self.pod.state_progress == PodProgress.ErrorShuttingDown:
            raise PdmError("Pod is shutting down, cannot acknowledge alerts.")

        if self.pod.state_progress == PodProgress.AlertExpiredShuttingDown:
            raise PdmError("Acknowledgement period expired, pod is shutting down")

        if self.pod.state_progress > PodProgress.AlertExpiredShuttingDown:
            raise PdmError("Pod is not active")

    def _assert_can_generate_nonce(self):
        if self.pod.id_lot is None:
            raise PdmError("Lot number is not defined")

        if self.pod.id_t is None:
            raise PdmError("Pod serial number is not defined")

    def _assert_status_running(self):
        if self.pod.state_progress < PodProgress.Running:
            raise PdmError("Pod is not yet running")

        if self.pod.state_progress > PodProgress.RunningLow:
            raise PdmError("Pod has stopped")

    def _assert_not_faulted(self):
        if self.pod.state_faulted:
            raise PdmError("Pod is state_faulted")

    def _assert_no_active_alerts(self):
        if self.pod.state_alert != 0:
            raise PdmError("Pod has active alerts")

    def _assert_immediate_bolus_not_active(self):
        if self._is_bolus_running():
            raise PdmError("Pod is busy delivering a bolus")


