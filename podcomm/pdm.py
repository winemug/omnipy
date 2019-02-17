from .pdmutils import *
from .nonce import Nonce
from .radio import Radio
from .message import Message, MessageType
from .exceptions import PdmError, OmnipyError
from .definitions import *

from decimal import *
import time
import struct
import logging


class Pdm:
    def __init__(self, pod):
        self.nonce = Nonce(pod.lot, pod.tid, seekNonce=pod.lastNonce, seed=pod.nonceSeed)
        self.pod = pod
        self.radio = Radio(pod.msgSequence, pod.packetSequence)

    def updatePodStatus(self, update_type=0):
        try:
            self._assert_pod_address_assigned()
            if update_type == 0 and \
                    self.pod.lastUpdated is not None and \
                    time.time() - self.pod.lastUpdated < 60:
                return
            with pdmlock():
                logging.debug("updating pod status")
                self._update_status(update_type)

        except PdmError:
            raise
        except OmnipyError as oe:
            raise PdmError("Command failed") from oe
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def acknowledge_alerts(self, alert_mask):
        try:
            self._assert_can_acknowledge_alerts()

            with pdmlock():
                logging.debug("acknowledging alerts with bitmask %d" % alert_mask)
                self._acknowledge_alerts(alert_mask)

        except PdmError:
            raise
        except OmnipyError as oe:
            raise PdmError("Command failed") from oe
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def is_busy(self):
        try:
            with pdmlock():
                return self._is_bolus_running()
        except PdmBusyError:
            return True
        except PdmError:
            raise
        except OmnipyError as oe:
            raise PdmError("Command failed") from oe
        except Exception as e:
            raise PdmError("Unexpected error") from e

    # def clear_alert(self, alert_bit):
    #     try:
    #         self._assert_can_acknowledge_alerts()
    #
    #         with pdmlock():
    #             logging.debug("clearing alert %d" % alert_bit)
    #             self._configure_alert(alert_bit, clear=True)
    #     except PdmError:
    #         raise
    #     except OmnipyError as oe:
    #         raise PdmError("Command failed") from oe
    #     except Exception as e:
    #         raise PdmError("Unexpected error") from e
    #     finally:
    #         self._savePod()

    def bolus(self, bolus_amount, beep=False):
        try:
            with pdmlock():
                self._assert_pod_address_assigned()
                self._assert_can_generate_nonce()
                self._assert_immediate_bolus_not_active()
                self._assert_not_faulted()
                self._assert_status_running()

                if bolus_amount > self.pod.maximumBolus:
                    raise PdmError("Bolus exceeds defined maximum bolus of %.2fU" % self.pod.maximumBolus)

                pulseCount = int(bolus_amount * Decimal(20))

                if pulseCount == 0:
                    raise PdmError("Cannot do a zero bolus")

                pulseSpan = pulseCount * 16
                if pulseSpan > 0x3840:
                    raise PdmError("Bolus would exceed the maximum time allowed for an immediate bolus")

                if self._is_bolus_running():
                    raise PdmError("A previous bolus is already running")

                if bolus_amount > self.pod.reservoir:
                    raise PdmError("Cannot bolus %.2f units, reservoir capacity is at: %.2f")

                commandBody = struct.pack(">I", 0)
                commandBody += b"\x02"

                bodyForChecksum = b"\x01"
                bodyForChecksum += struct.pack(">H", pulseSpan)
                bodyForChecksum += struct.pack(">H", pulseCount)
                bodyForChecksum += struct.pack(">H", pulseCount)
                checksum = getChecksum(bodyForChecksum)

                commandBody += struct.pack(">H", checksum)
                commandBody += bodyForChecksum

                msg = self._createMessage(0x1a, commandBody)


                reminders = 0
                if beep:
                    reminders |= 0x40

                deliveryStart = 200000

                commandBody = bytes([reminders])
                commandBody += struct.pack(">H", pulseCount * 10)
                commandBody += struct.pack(">I", deliveryStart)
                commandBody += b"\x00\x00\x00\x00\x00\x00"
                msg.addCommand(0x17, commandBody)

                self._sendMessage(msg, with_nonce=True)

                if self.pod.bolusState != BolusState.Immediate:
                    raise PdmError("Pod did not confirm bolus")

                self.pod.last_enacted_bolus_start = time.time()
                self.pod.last_enacted_bolus_amount = float(bolus_amount)
        except PdmError:
            raise
        except OmnipyError as oe:
            raise PdmError("Command failed") from oe
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()


    def cancelBolus(self, beep=False):
        try:
            with pdmlock():
                self._assert_pod_address_assigned()
                self._assert_can_generate_nonce()
                self._assert_not_faulted()
                self._assert_status_running()

                if self._is_bolus_running():
                    logging.debug("Canceling running bolus")
                    self._cancelActivity(cancelBolus=True, beep=beep)
                    if self.pod.bolusState == BolusState.Immediate:
                        raise PdmError("Failed to cancel bolus")
                    else:
                        self.pod.last_enacted_bolus_amount = float(-1)
                        self.pod.last_enacted_bolus_start = time.time()
                else:
                    raise PdmError("Bolus is not running")

        except PdmError:
            raise
        except OmnipyError as oe:
            raise PdmError("Command failed") from oe
        except Exception as e:
            raise PdmError("Unexpected error") from e
        finally:
            self._savePod()

    def cancelTempBasal(self, beep=False):
        try:
            with pdmlock():
                self._assert_pod_address_assigned()
                self._assert_can_generate_nonce()
                self._assert_immediate_bolus_not_active()
                self._assert_not_faulted()
                self._assert_status_running()

                if self._is_temp_basal_active():
                    logging.debug("Canceling temp basal")
                    self._cancelActivity(cancelTempBasal=True, beep=beep)
                    if self.pod.basalState == BasalState.TempBasal:
                        raise PdmError("Failed to cancel temp basal")
                    else:
                        self.pod.last_enacted_temp_basal_duration = float(-1)
                        self.pod.last_enacted_temp_basal_start = time.time()
                        self.pod.last_enacted_temp_basal_amount = float(-1)
                else:
                    raise PdmError("Temp basal is not active")

        except PdmError:
            raise
        except OmnipyError as oe:
            raise PdmError("Command failed") from oe
        except Exception as e:
            raise PdmError("Unexpected error") from e

        finally:
            self._savePod()

    def setTempBasal(self, basalRate, hours, confidenceReminder=False):
        try:
            with pdmlock():
                self._assert_pod_address_assigned()
                self._assert_can_generate_nonce()
                self._assert_immediate_bolus_not_active()
                self._assert_not_faulted()
                self._assert_status_running()

                halfHours = int(hours * Decimal(2))

                if halfHours > 24 or halfHours < 1:
                    raise PdmError("Requested duration is not valid")

                if self.pod is None or not self.pod.is_active():
                    raise PdmError("Pod not active")
                if basalRate > Decimal(self.pod.maximumTempBasal):
                    raise PdmError("Requested rate exceeds maximum temp basal setting")
                if basalRate > Decimal(30):
                    raise PdmError("Requested rate exceeds maximum temp basal capability")

                if self._is_temp_basal_active():
                    self.cancelTempBasal()

                halfHourUnits = [basalRate / Decimal(2)] * halfHours
                pulseList = getPulsesForHalfHours(halfHourUnits)
                iseList = getInsulinScheduleTableFromPulses(pulseList)

                iseBody = getStringBodyFromTable(iseList)
                pulseBody = getStringBodyFromTable(pulseList)

                commandBody = struct.pack(">I", 0)
                commandBody += b"\x01"

                bodyForChecksum = bytes([halfHours])
                bodyForChecksum += struct.pack(">H", 0x3840)
                bodyForChecksum += struct.pack(">H", pulseList[0])
                checksum = getChecksum(bodyForChecksum + pulseBody)

                commandBody += struct.pack(">H", checksum)
                commandBody += bodyForChecksum
                commandBody += iseBody

                msg = self._createMessage(0x1a, commandBody)

                reminders = 0
                if confidenceReminder:
                    reminders |= 0x40

                commandBody = bytes([reminders])
                commandBody += b"\x00"

                pulseEntries = getPulseIntervalEntries(halfHourUnits)

                firstPulseCount, firstInterval = pulseEntries[0]
                commandBody += struct.pack(">H", firstPulseCount)
                commandBody += struct.pack(">I", firstInterval)
                for pulseCount, interval in pulseEntries:
                    commandBody += struct.pack(">H", pulseCount)
                    commandBody += struct.pack(">I", interval)

                msg.addCommand(0x16, commandBody)

                self._sendMessage(msg, with_nonce=True)

                if self.pod.basalState != BasalState.TempBasal:
                    raise PdmError()
                else:
                    self.pod.last_enacted_temp_basal_duration = float(hours)
                    self.pod.last_enacted_temp_basal_start = time.time()
                    self.pod.last_enacted_temp_basal_amount = float(basalRate)

        except PdmError:
            raise
        except OmnipyError as oe:
            raise PdmError("Command failed") from oe
        except Exception as e:
            raise PdmError("Unexpected error") from e

        finally:
            self._savePod()

    def _cancelActivity(self, cancelBasal=False, cancelBolus=False, cancelTempBasal=False, beep=False):
        logging.debug("Running cancel activity for basal: %s - bolus: %s - tempBasal: %s" % (
        cancelBasal, cancelBolus, cancelTempBasal))
        commandBody = struct.pack(">I", 0)
        if beep:
            c = 0x60
        else:
            c = 0

        if cancelBolus:
            c = c | 0x04
        if cancelTempBasal:
            c = c | 0x02
        if cancelBasal:
            c = c | 0x01
        commandBody += bytes([c])

        msg = self._createMessage(0x1f, commandBody)
        self._sendMessage(msg, with_nonce=True)

    def _createMessage(self, commandType, commandBody):
        msg = Message(MessageType.PDM, self.pod.address, sequence=self.radio.messageSequence)
        msg.addCommand(commandType, commandBody)
        return msg

    def _savePod(self):
        try:
            logging.debug("Saving pod status")
            self.pod.msgSequence = self.radio.messageSequence
            self.pod.packetSequence = self.radio.packetSequence
            self.pod.lastNonce = self.nonce.lastNonce
            self.pod.nonceSeed = self.nonce.seed
            self.pod.Save()
            logging.debug("Saved pod status")
        except Exception as e:
            raise PdmError("Pod status was not saved") from e

    def _sendMessage(self, message, with_nonce=False, nonce_retry_count=0):
        if with_nonce:
            message.setNonce(self.nonce.getNext())
        response_message = self.radio.sendRequestToPod(message)
        contents = response_message.getContents()
        for (ctype, content) in contents:
            # if ctype == 0x01:  # pod info response
            #     self.pod.setupPod(content)
            if ctype == 0x1d:  # status response
                self.pod.handle_status_response(content)
            elif ctype == 0x02:  # pod faulted
                self.pod.handle_information_response(content)
            elif ctype == 0x06:
                if content[0] == 0x14:  # bad nonce error
                    if nonce_retry_count == 0:
                        logging.debug("Bad nonce error - renegotiating")
                    elif nonce_retry_count > 3:
                        raise PdmError("Nonce re-negotiation failed")
                    nonce_sync_word = struct.unpack(">H", content[1:])[0]
                    self.nonce.sync(nonce_sync_word, message.sequence)
                    self.radio.messageSequence = message.sequence
                    return self._sendMessage(message, with_nonce=True, nonce_retry_count=nonce_retry_count + 1)


    def _update_status(self, update_type=0):
        commandType = 0x0e
        commandBody = bytes([update_type])
        msg = self._createMessage(commandType, commandBody)
        self._sendMessage(msg)

    def _acknowledge_alerts(self, alert_mask):
        commandType = 0x11
        commandBody = bytes([0, 0, 0, 0, alert_mask])
        msg = self._createMessage(commandType, commandBody)
        self._sendMessage(msg, with_nonce=True)

    def _configure_alerts(self, alerts):
        commandType = 0x19
        commandBody = bytes([0, 0, 0, 0])

        for alert in alerts:
            commandBody += self._configure_alert(alert)

        msg = self._createMessage(commandType, commandBody)
        self._sendMessage(msg, with_nonce=True)

    def _configure_alert(self, alert_bit, activate, trigger_reservoir, trigger_auto_off,
                         duration_minutes, alert_after_minutes, alert_after_reservoir,
                         beep_repeat_type, beep_type):

        if alert_after_minutes is None:
            if alert_after_reservoir is None:
                raise PdmError("Either alert_after_minutes or alert_after_reservoir must be set")
            elif not trigger_reservoir:
                raise PdmError("Trigger reservoir must be True if alert_after_reservoir is to be set")
        else:
            if alert_after_reservoir is not None:
                raise PdmError("Only one of alert_after_minutes or alert_after_reservoir must be set")
            elif trigger_reservoir:
                raise PdmError("Trigger reservoir must be False if alert_after_minutes is to be set")

        if duration_minutes > 0x1FF:
            raise PdmError("Alert duration in minutes cannot be more than %d", 0x1ff)
        elif duration_minutes < 0:
            raise PdmError("Invalid alert duration value")

        if alert_after_minutes is not None and alert_after_minutes > 4800:
            raise PdmError("Alert cannot be set beyond 80 hours")
        if alert_after_minutes is not None and alert_after_minutes < 0:
            raise PdmError("Invalid value for alert_after_minutes")

        if alert_after_reservoir is not None and alert_after_reservoir > 50:
            raise PdmError("Alert cannot be set for more than 50 units")
        if alert_after_reservoir is not None and alert_after_minutes < 0:
            raise PdmError("Invalid value for alert_after_reservoir")

        b0 = alert_bit << 4
        if activate:
            b0 |= 0x08
        if trigger_reservoir:
            b0 |= 0x04
        if trigger_auto_off:
            b0 |= 0x02

        b0 |= (duration_minutes >> 8) & 0x0001
        b1 = duration_minutes & 0x00ff

        if alert_after_minutes is not None:
            b2 = alert_after_minutes >> 8
            b3 = alert_after_minutes & 0x00ff
        else:
            reservoir_limit = int(alert_after_reservoir * 10)
            b2 = reservoir_limit >> 8
            b3 = reservoir_limit & 0x00ff

        return bytes([b0, b1, b2, b3, beep_repeat_type, beep_type])

    def _is_bolus_running(self):
        if self.pod.lastUpdated is not None and self.pod.bolusState != BolusState.Immediate:
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

        self._update_status()
        return self.pod.bolusState == BolusState.Immediate

    def _is_temp_basal_active(self):
        if self.pod.lastUpdated is not None and self.pod.basalState != BasalState.TempBasal:
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

        self._update_status()
        return self.pod.basalState == BasalState.TempBasal

    def _assert_pod_address_assigned(self):
        if self.pod is None:
            raise PdmError("No pod assigned")

        if self.pod.address is None:
            raise PdmError("Radio address unknown")

    def _assert_can_acknowledge_alerts(self):
        self._assert_pod_address_assigned()
        if self.pod.progress < PodProgress.PairingSuccess:
            raise PdmError("Pod not paired completely yet.")

        if self.pod.progress == PodProgress.ErrorShuttingDown:
            raise PdmError("Pod is shutting down, cannot acknowledge alerts.")

        if self.pod.progress == PodProgress.AlertExpiredShuttingDown:
            raise PdmError("Acknowledgement period expired, pod is shutting down")

        if self.pod.progress > PodProgress.AlertExpiredShuttingDown:
            raise PdmError("Pod is not active")


    def _assert_can_generate_nonce(self):
        if self.pod.lot is None:
            raise PdmError("Lot number is not defined")

        if self.pod.tid is None:
            raise PdmError("Pod serial number is not defined")

    def _assert_status_running(self):
        if self.pod.progress < PodProgress.Running:
            raise PdmError("Pod is not yet running")

        if self.pod.progress > PodProgress.RunningLow:
            raise PdmError("Pod has stopped")

    def _assert_not_faulted(self):
        if self.pod.faulted:
            raise PdmError("Pod is faulted")

    def _assert_no_active_alerts(self):
        if self.pod.alert_states != 0:
            raise PdmError("Pod has active alerts")

    def _assert_immediate_bolus_not_active(self):
        if self._is_bolus_running():
            raise PdmError("Pod is busy delivering a bolus")


    #    def initializePod(self, path, addressToAssign=None):
    #     if addressToAssign is None:
    #         addressToAssign = random.randint(0x20000000, 0x2FFFFFFF)
    #     success = False

    #     self.pod = Pod()

    #     commandType = 0x07
    #     commandBody = struct.unpack(">I", addressToAssign)
    #     msg = self.createMessage(commandType, commandBody)
    #     self.radio.sendRequestToPod(msg, self.handlePodResponse)
    #     self.savePod()

    #     success = True

    #     self.savePod()
    #     return success

    # def setBasalSchedule(self, basalSchedule):
    #     with pdmlock():
    #
    #         self.updatePodStatus()
    #
    #         if self.pod.basalState == BasalState.TempBasal:
    #             raise PdmError()
    #
    #         if self.pod.basalState == BasalState.Program:
    #             self.cancelBasal()
    #
    #         if self.pod.basalState != BasalState.NotRunning:
    #             raise PdmError()
    #
    #         commandBody = struct.pack(">I", self.nonce.getNext())
    #         commandBody += b"\x00"
    #
    #         bodyForChecksum = ""
    #         utcOffset = timedelta(minutes=self.pod.utcOffset)
    #         podDate = datetime.utcnow() + utcOffset
    #
    #         hour = podDate.hour
    #         minute = podDate.minute
    #         second = podDate.second
    #
    #         currentHalfHour = hour * 2
    #         secondsUntilHalfHour = 0
    #         if minute < 30:
    #             secondsUntilHalfHour += (30 - minute - 1) * 60
    #         else:
    #             secondsUntilHalfHour += (60 - minute - 1) * 60
    #             currentHalfHour += 1
    #
    #         secondsUntilHalfHour += (60 - second)
    #
    #         pulseTable = getPulsesForHalfHours(basalSchedule)
    #         pulsesRemainingCurrentHour = int(secondsUntilHalfHour / 1800) * pulseTable[currentHalfHour]
    #         iseBody = getStringBodyFromTable(getInsulinScheduleTableFromPulses(pulseTable))
    #
    #         bodyForChecksum += bytes([currentHalfHour])
    #         bodyForChecksum += struct.pack(">H", secondsUntilHalfHour * 8)
    #         bodyForChecksum += struct.pack(">H", pulsesRemainingCurrentHour)
    #         getChecksum(bodyForChecksum + getStringBodyFromTable(pulseTable))
    #
    #         commandBody += bodyForChecksum + iseBody
    #
    #         msg = self._createMessage(0x1a, commandBody)
    #
    #         reminders = 0
    #         if confidenceReminder:
    #             reminders |= 0x40
    #
    #         commandBody = bytes([reminders])
    #
    #         # commandBody += b"\x00"
    #         # pulseEntries = []
    #         # subTotal = 0
    #         # for pulses in pulseList:
    #         #     if subTotal + pulses > 6553:
    #         #         pulseEntries.append(subTotal)
    #         #         subTotal = 0
    #         #     subTotal += pulses
    #         # pulseEntries.append(subTotal)
    #
    #         # if pulseList[0] == 0:
    #         #     pulseInterval = 3600* 100000
    #         # else:
    #         #     pulseInterval = 3600 * 100000 / pulseList[0]
    #
    #         # commandBody += struct.pack(">H", pulseEntries[0] * 10)
    #         # commandBody += struct.pack(">I", pulseInterval)
    #         # for pe in pulseEntries:
    #         #     commandBody += struct.pack(">H", pe * 10)
    #         #     commandBody += struct.pack(">I", pulseInterval)
    #
    #         # msg.addCommand(0x16, commandBody)
    #
    #         self.__sendMessageWithNonce(msg)
    #         self._savePod()
    #         if self.pod.basalState != BasalState.TempBasal:
    #             raise PdmError()
    #
    #         self._savePod()

    # def cancelBasal(self, beep=False):
    #     logging.debug("Canceling current basal schedule")
    #     self.updatePodStatus()
    #     if self.pod.basalState == BasalState.Program:
    #         self.__cancelActivity(cancelBasal=True, alarm=beep)
    #     if self.pod.basalState == BasalState.Program:
    #         raise PdmError()

    # def deactivatePod(self):
    #     # logging.debug("deactivating pod")
    #     # self.__savePod()