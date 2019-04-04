from .exceptions import PacketRadioError, OmnipyTimeoutError
from podcomm.packet_radio import TxPower
from podcomm.protocol_common import *
from .pr_rileylink import RileyLink
from .definitions import *
from threading import Thread, Event
import binascii
import time
import subprocess

def _ack_data(address1, address2, sequence):
    return RadioPacket(address1, RadioPacketType.ACK, sequence,
                     struct.pack(">I", address2))

class PdmRadio:
    pod_message: PodMessage

    def __init__(self, radio_address, msg_sequence=0, pkt_sequence=0, packet_radio=None):
        self.radio_address = radio_address
        self.message_sequence = msg_sequence
        self.packet_sequence = pkt_sequence
        self.last_received_packet = None
        self.logger = getLogger()
        self.packet_logger = get_packet_logger()

        if packet_radio is None:
            self.packet_radio = RileyLink()
        else:
            self.packet_radio = packet_radio

        self.last_packet_received = None
        self.last_packet_timestamp = None
        self.radio_ready = Event()
        self.radio_busy = False
        self.request_arrived = Event()
        self.response_received = Event()
        self.request_shutdown = Event()
        self.request_message = None
        self.double_take = False
        self.tx_power = None
        self.expect_critical_follow_up = False
        self.pod_message = None
        self.response_exception = None
        self.radio_thread = None
        self.start()

    def start(self):
        self.radio_thread = Thread(target=self._radio_loop)
        self.radio_thread.setDaemon(True)
        self.radio_thread.start()

    def stop(self):
        self.radio_ready.wait()
        self.radio_ready.clear()
        self.request_shutdown.set()
        self.request_arrived.set()
        self.radio_thread.join()
        self.request_shutdown.clear()

    def send_message_get_message(self, message: PdmMessage,
                                 message_address=None,
                                 ack_address_override=None,
                                 tx_power=None, double_take=False,
                                 expect_critical_follow_up=False):
        if not self.radio_ready.wait(30):
            if self.radio_busy:
                raise PacketRadioError("Radio is busy")
            else:
                raise PacketRadioError("Radio is not ready")

        self.radio_ready.clear()

        self.pdm_message = message
        if message_address is None:
            self.pdm_message_address = self.radio_address
        else:
            self.pdm_message_address = message_address
        self.ack_address_override = ack_address_override
        self.pod_message = None
        self.double_take = double_take
        self.tx_power = tx_power
        self.expect_critical_follow_up = expect_critical_follow_up

        self.request_arrived.set()

        self.response_received.wait()
        self.response_received.clear()
        if self.pod_message is None:
            raise self.response_exception
        return self.pod_message

    def get_packet(self, timeout=30000):
        received = self.packet_radio.get_packet(timeout=timeout)
        p, rssi = self._get_packet(received)
        return p

    def disconnect(self):
        try:
            self.packet_radio.disconnect(ignore_errors=True)
        except Exception:
            self.logger.exception("Error while disconnecting")

    def _radio_loop(self):
        while not self._radio_init():
            self.logger.warning("Failed to initialize radio, retrying")
            time.sleep(5)

        self.radio_ready.set()
        while True:
            if not self.request_arrived.wait(timeout=5.0):
                self.disconnect()
            self.request_arrived.wait()
            self.request_arrived.clear()

            if self.request_shutdown.wait(0):
                self.disconnect()
                break

            self.radio_busy = True
            try:
                self.pod_message = self._send_and_get(self.pdm_message, self.pdm_message_address,
                                                      self.ack_address_override,
                                                      tx_power=self.tx_power, double_take=self.double_take,
                                                      expect_critical_follow_up=self.expect_critical_follow_up)
                self.response_exception = None
            except Exception as e:
                self.pod_message = None
                self.response_exception = e

            if self.response_exception is None:
                ack_packet = self._final_ack(self.ack_address_override, self.packet_sequence)
                self.packet_sequence = (self.packet_sequence + 1) % 32
                self.response_received.set()

                try:
                    self._send_packet(ack_packet)
                except Exception as e:
                    self.logger.exception("Error during ending conversation, ignored.")
            else:
                self.response_received.set()

            self.radio_ready.set()
            self.radio_busy = False

    def _interim_ack(self, ack_address_override, sequence):
        if ack_address_override is None:
            return _ack_data(self.radio_address, self.radio_address, sequence)
        else:
            return _ack_data(self.radio_address, ack_address_override, sequence)

    def _final_ack(self, ack_address_override, sequence):
        if ack_address_override is None:
            return _ack_data(self.radio_address, 0, sequence)
        else:
            return _ack_data(self.radio_address, ack_address_override, sequence)

    def _radio_init(self, retries=1):
        retry = 0
        while retry < retries:
            try:
                self.disconnect()
                self.packet_radio.connect(force_initialize=True)
                return True
            except:
                self.logger.exception("Error during radio initialization")
                time.sleep(2)
                retry += 1
        return False

    def _kill_btle_subprocess(self):
        try:
            p = subprocess.Popen(["ps", "-A"], stdout=subprocess.PIPE)
            out, err = p.communicate()
            for line in out.splitlines():
                if "bluepy-helper" in line:
                    pid = int(line.split(None, 1)[0])
                    os.kill(pid, 9)
                    break
        except:
            self.logger.warning("Failed to kill bluepy-helper")

    def _reset_sequences(self):
        self.packet_sequence = 0
        self.message_sequence = 0

    def _send_and_get(self, pdm_message: PdmMessage, pdm_message_address, ack_address_override=None,
                      tx_power=None, double_take=False, expect_critical_follow_up=False):

        packets = pdm_message.get_radio_packets(message_address=pdm_message_address,
                                                message_sequence=self.message_sequence,
                                                packet_address=self.radio_address,
                                                first_packet_sequence=self.packet_sequence,
                                                double_take=double_take,
                                                expect_critical_follow_up=expect_critical_follow_up)

        try:
            if tx_power is not None:
                self.packet_radio.set_tx_power(tx_power)
            self._awaken()
        except PacketRadioError:
            if not self._radio_init(3):
                raise

        received = None
        packet_count = len(packets)

        for part in range(0, packet_count):
            packet = packets[part]
            repeat_count = -1
            timeout = 10
            while True:
                repeat_count += 1
                if repeat_count == 0:
                    self.logger.debug("Sending PDM message part %d/%d" % (part + 1, packet_count))
                else:
                    self.logger.debug("Sending PDM message part %d/%d (Repeat: %d)" %
                                      (part + 1, packet_count, repeat_count))

                if part == packet_count - 1:
                    expected_type = RadioPacketType.POD
                else:
                    expected_type = RadioPacketType.ACK

                try:
                    received = self._exchange_packets(packet.with_sequence(self.packet_sequence),
                                                      expected_type=expected_type,
                                                      timeout=timeout)
                    break
                except OmnipyTimeoutError:
                    self.logger.debug("Trying to recover from timeout error")
                    if part == 0:
                        if repeat_count == 0:
                            timeout = 15
                            continue
                        elif repeat_count == 1:
                            self._reset_sequences()
                            timeout = 10
                            time.sleep(2)
                            continue
                        elif repeat_count == 2:
                            self._reset_sequences()
                            self._radio_init()
                            timeout = 15
                            continue
                        else:
                            self.logger.debug("Failed recovery")
                            if packet_count == 1:
                                self.logger.debug("Calming pod down in case of reception problem on our end")
                                ack_packet = self._final_ack(self.ack_address_override, 1)
                                try:
                                    self.packet_radio.set_tx_power(TxPower.Highest)
                                    self._send_packet(ack_packet)
                                except Exception as e:
                                    self.logger.exception("Ignored.")
                            self._reset_sequences()
                            raise
                    elif part < packet_count - 1:
                        if repeat_count < 2:
                            timeout = 20
                            continue
                        else:
                            raise
                    else:
                        if repeat_count < 10:
                            timeout = 20
                            continue
                        else:
                            raise
                except PacketRadioError:
                    self.logger.debug("Trying to recover from radio error")
                    if part == 0:
                        if repeat_count < 2:
                            self._radio_init()
                            continue
                        elif repeat_count < 4:
                            self.disconnect()
                            self._kill_btle_subprocess()
                            timeout = 10
                            time.sleep(2)
                            continue
                        else:
                            self.logger.debug("Failed recovery")
                            self._reset_sequences()
                            raise
                    elif part < packet_count - 1:
                        if repeat_count < 6:
                            self.disconnect()
                            self._kill_btle_subprocess()
                            timeout = 10
                            time.sleep(2)
                            continue
                        else:
                            self.logger.debug("Failed recovery")
                            self._reset_sequences()
                            raise
                    else:
                        if repeat_count < 10:
                            self.disconnect()
                            self._kill_btle_subprocess()
                            timeout = 10
                            time.sleep(2)
                            continue
                        else:
                            self.logger.debug("Failed recovery")
                            self._reset_sequences()
                            raise
                except ProtocolError:
                    if part == 0 and repeat_count == 0:
                        self.logger.debug("Trying to recover from protocol error")
                        continue
                    else:
                        raise

            part += 1
            self.packet_sequence = (received.sequence + 1) % 32


        self.packet_logger.info("SENT MSG %s" % pdm_message)
        if received.type == RadioPacketType.POD:
            part_count = 1
            self.logger.debug("Received POD message part %d." % part_count)
        pod_response = PodMessage()
        while not pod_response.add_radio_packet(received):
            ack_packet = self._interim_ack(ack_address_override, (received.sequence + 1) % 32)
            received = self._exchange_packets(ack_packet, RadioPacketType.CON)
            part_count += 1
            self.logger.debug("Received POD message part %d." % part_count)

        self.packet_logger.info("RCVD MSG %s" % pod_response)
        self.logger.debug("Send and receive completed.")
        self.message_sequence = (pod_response.sequence + 1) % 16
        return pod_response


    def _exchange_packets(self, packet_to_send, expected_type, timeout=10):
        start_time = None
        while start_time is None or time.time() - start_time < timeout:
            received = self.packet_radio.send_and_receive_packet(packet_to_send.get_data(), 0, 0, 100, 1, 130)
            if start_time is None:
                start_time = time.time()

            self.packet_logger.info("SEND PKT %s" % packet_to_send)

            if received is None:
                self.packet_logger.debug("RECV PKT None")
                self.packet_radio.tx_up()
                continue
            p, rssi = self._get_packet(received)
            if p is None:
                self.packet_logger.debug("RECV PKT BAD DATA: %s" % received.hex())
                self.packet_radio.tx_down()
                continue

            self.packet_logger.info("RECV PKT %s" % p)
            if p.address != self.radio_address:
                self.packet_logger.debug("RECV PKT ADDR MISMATCH")
                self.packet_radio.tx_down()
                continue

            self.last_packet_timestamp = time.time()

            if self.last_packet_received is not None and \
                        p.sequence == self.last_packet_received.sequence and \
                        p.type == self.last_packet_received.type:
                self.packet_logger.debug("RECV PKT previous")
                self.packet_radio.tx_up()
                continue

            self.last_packet_received = p
            self.packet_sequence = (p.sequence + 1) % 32

            if expected_type is not None and p.type != expected_type:
                self.packet_logger.debug("RECV PKT unexpected type %s" % p)
                raise ProtocolError("Unexpected packet type received")

            if p.sequence != (packet_to_send.sequence + 1) % 32:
                self.packet_sequence = (p.sequence + 1) % 32
                self.packet_logger.debug("RECV PKT unexpected sequence %s" % p)
                self.last_packet_received = p
                raise ProtocolError("Incorrect packet sequence received")

            return p
        raise OmnipyTimeoutError("Exceeded timeout while send and receive")

    def _send_packet(self, packet_to_send, timeout=25):
        start_time = None
        while start_time is None or time.time() - start_time < timeout:
            try:
                self.packet_logger.info("SEND PKT %s" % packet_to_send)

                received = self.packet_radio.send_and_receive_packet(packet_to_send.get_data(), 5, 55, 300, 2, 40)
                if start_time is None:
                    start_time = time.time()

                # if self.request_arrived.wait(timeout=0):
                #     self.logger.debug("Prematurely exiting final phase to process next request")
                #     return
                if received is None:
                    received = self.packet_radio.get_packet(1.0)
                    if received is None:
                        self.packet_logger.debug("Silence")
                        break
                p, rssi = self._get_packet(received)
                if p is None:
                    self.packet_logger.debug("RECV PKT bad %s" % received.hex())
                    self.packet_radio.tx_down()
                    continue

                if p.address != self.radio_address:
                    self.packet_logger.debug("RECV PKT ADDR MISMATCH")
                    self.packet_radio.tx_down()
                    continue

                self.last_packet_timestamp = time.time()
                if self.last_packet_received is not None:
                    if p.type == self.last_packet_received.type and p.sequence == self.last_packet_received.sequence:
                        self.packet_logger.debug("RECV PKT previous")
                        self.packet_radio.tx_up()
                        continue

                self.packet_logger.info("RECV PKT %s" % p)
                self.packet_logger.debug("RECEIVED unexpected packet: %s" % p)
                self.last_packet_received = p
                self.packet_sequence = (p.sequence + 1) % 32
                packet_to_send.with_sequence(self.packet_sequence)
                continue


            except PacketRadioError:
                self.logger.exception("Radio error during send and receive, retrying")
                if not self._radio_init(3):
                    raise
                start_time = time.time()
        else:
            self.logger.warning("Exceeded timeout while waiting for silence to fall")

    def _get_packet(self, data):
        rssi = None
        if data is not None and len(data) > 2:
            rssi = data[0]
            try:
                return RadioPacket.parse(data[2:]), rssi
            except:
                getLogger().exception("RECEIVED DATA: %s RSSI: %d" % (binascii.hexlify(data[2:]), rssi))
        return None, rssi

    def _awaken(self):
        self.packet_radio.send_packet(bytes(), 0, 0, 250)
