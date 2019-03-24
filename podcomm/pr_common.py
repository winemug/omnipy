from .exceptions import ProtocolError, PacketRadioError
from podcomm import crc
from podcomm.protocol_common import *
from .packet_radio import TxPower
from .pr_rileylink import RileyLink
from .packet import Packet
from .definitions import *
from threading import Thread, Event
import binascii

def _ack_data(address1, address2, sequence):
    ack_data = bytes(struct.pack(">I", address1))
    ack_data += bytes(sequence | 0x40)
    ack_data += struct.pack(">I", address2)
    return ack_data


class PdmRadio:
    pod_message: PodMessage

    def __init__(self, radio_address, msg_sequence=0, pkt_sequence=0):
        self.radio_address = radio_address
        self.message_sequence = msg_sequence
        self.packet_sequence = pkt_sequence
        self.last_received_packet = None
        self.logger = getLogger()
        self.packet_radio = RileyLink()
        self.last_packet_received = None
        self.radio_ready = Event()
        self.request_arrived = Event()
        self.response_received = Event()
        self.send_final_complete = Event()
        self.request_message = None
        self.double_take = False
        self.tx_power = None
        self.response_message = None
        self.response_exception = None
        self.radio_thread = Thread(target=self._radio_loop)
        self.radio_thread.setDaemon(True)
        self.radio_thread.start()

    def send_message_get_message(self, message: PdmMessage,
                                 message_address, ack_address_override=None,
                                 tx_power=None, double_take=False):
        self.radio_ready.wait()
        self.radio_ready.clear()

        self.pdm_message = message
        self.pdm_message_address = message_address
        self.ack_address_override = ack_address_override
        self.pod_message = None
        self.double_take = double_take
        self.tx_power = tx_power

        self.request_arrived.set()

        self.response_received.wait()
        self.response_received.clear()
        if self.pod_message is None:
            raise self.response_exception
        return self.pod_message

    def disconnect(self):
        try:
            self.packet_radio.disconnect(ignore_errors=True)
        except Exception:
            self.logger.exception("Error while disconnecting")

    def _radio_loop(self):
        self.radio_ready.set()
        while True:
            if not self.request_arrived.wait(timeout=10.0):
                self.disconnect()
            self.request_arrived.wait()
            self.request_arrived.clear()

            try:
                self.pod_message = self._send_and_get(self.pdm_message, self.pdm_message_address,
                                                      self.ack_address_override,
                                                      tx_power=self.tx_power, double_take=self.double_take)
            except Exception as e:
                self.response_message = None
                self.response_exception = e
            finally:
                ack_address_override = self.ack_address_override
                self.response_received.set()

            self.radio_ready.set()

            try:
                self._send_packet(self._final_ack(ack_address_override, self.packet_sequence))
                self.logger.debug("Conversation ended")
            except Exception as e:
                self.logger.exception("Error during ending conversation, ignored.")

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

    def _send_and_get(self, pdm_message: PdmMessage, pdm_message_address, ack_address_override=None,
                      tx_power=None, double_take=False):

        if tx_power is not None:
            self.packet_radio.set_tx_power(tx_power)

        self.logger.debug("SENDING MSG: %s" % pdm_message)
        packets = pdm_message.get_packets(message_address=pdm_message_address, message_sequence=self.message_sequence,
                                          packet_address=self.radio_address, first_packet_sequence=self.packet_sequence)
        received = None
        packet_index = 1
        packet_count = len(packets)
        for packet in packets:
            self.packet_sequence = (self.packet_sequence + 1) % 32
            while True:
                if packet_index == packet_count:
                    expected_type_seq = 0xE0 | (self.packet_sequence % 32)
                else:
                    expected_type_seq = 0x40 | (self.packet_sequence % 32)
                received = self._exchange_packets(packet, None)
                if received is None:
                    raise ProtocolError("Timeout reached waiting for a response.")

                if double_take:
                    double_take=False
                else:
                    break

            packet_index += 1

        pod_response = PodMessage()
        while not pod_response.add_packet_data(received):
            ack_packet = self._interim_ack(ack_address_override)
            received = self._exchange_packets(ack_packet, None)
            if received is None:
                raise ProtocolError("Timeout reached waiting for a response.")
            if received.type != "CON":
                raise ProtocolError("Invalid response received. Expected type CON, received %s" % received.type)

        self.logger.debug("RECEIVED MSG: %s" % pod_response)
        self.message_sequence = (pod_response.sequence + 1) % 16
        return pod_response


    def _exchange_packets(self, packet_to_send, expected_type_seq):
        send_retries = 30
        while send_retries > 0:
            try:
                data = packet_to_send
                self.logger.debug("SENDING PACKET EXP RESPONSE: %s" % binascii.hexlify(data))

                send_retries -= 1
                received = self.packet_radio.send_and_receive_packet(data, 0, 0, 100, 1, 130)

                if received is None:
                    self.logger.debug("Received nothing")
                    self.packet_radio.tx_up()
                    continue
                p, rssi = self._get_packet(received)
                if p is None:
                    self.logger.debug("Received bad packet")
                    self.packet_radio.tx_down()
                    continue

                if expected_type_seq is not None and p[0] != expected_type_seq:
                    if self.last_packet_received is not None:
                        if p[0] == self.last_packet_received[0]:
                            self.logger.debug("Received previous response")
                            self.packet_radio.tx_up()
                            continue

                    raise PacketRadioError("Unexpected packet received")

                self.last_packet_received = p
                self.logger.debug("SEND AND RECEIVE complete")
                return p
            except PacketRadioError:
                self.logger.exception("Radio error during send and receive")
                self.packet_radio.disconnect()
        else:
            raise ProtocolError("Exceeded retry count while send and receive")

    def _send_packet(self, data_to_send):
        self.send_final_complete.clear()
        while True:
            try:
                data = data_to_send

                self.logger.debug("SENDING FINAL PACKET: %s" % data_to_send)
                received = self.packet_radio.send_and_receive_packet(data, 3, 100, 100, 3, 20)
                if self.request_arrived.wait(timeout=0):
                    self.logger.debug("Prematurely exiting final phase to process next request")
                    self.packetSequence = (self.packetSequence + 2) % 32
                    return
                if received is None:
                    received = self.packet_radio.get_packet(1.0)
                    if received is None:
                        self.logger.debug("Silence has fallen")
                        break
                p, rssi = self._get_packet(received)
                if p is None:
                    self.logger.debug("Received bad packet")
                    self.packet_radio.tx_down()
                    continue
                if self.last_packet_received is not None:
                    if p[0] == self.last_packet_received[0]:
                        self.logger.debug("Received previous response")
                        self.packet_radio.tx_up()
                        continue
                self.logger.debug("Received unexpected packet")
                continue

            except PacketRadioError:
                self.logger.exception("Radio error during sending")
                self.packet_radio.disconnect()
        self.packetSequence = (self.packetSequence + 1) % 32
        self.logger.debug("SEND FINAL complete")
        self.send_final_complete.set()

    def _get_packet(self, data):
        rssi = None
        if data is not None and len(data) > 6:
            rssi = data[0]
            calc = crc.crc8(data[2:-1])
            if data[-1] == calc:
                getLogger().debug("RECEIVED PACKET: %s RSSI: %d" % (binascii.hexlify(data[2:]), rssi))
                return data[6:-1], rssi
            return None, rssi
