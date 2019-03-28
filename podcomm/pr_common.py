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
    return RadioPacket(address1, RadioPacketType.ACK, sequence,
                     struct.pack(">I", address2));


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
        self.pod_message = None
        self.response_exception = None
        self.radio_thread = Thread(target=self._radio_loop)
        self.radio_thread.setDaemon(True)
        self.radio_thread.start()

    def send_message_get_message(self, message: PdmMessage,
                                 message_address=None,
                                 ack_address_override=None,
                                 tx_power=None, double_take=False):
        self.radio_ready.wait()
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
                self.response_exception = None
            except Exception as e:
                self.pod_message = None
                self.response_exception = e
            finally:
                self.response_received.set()

            self.radio_ready.set()
            if self.response_exception is None:
                try:
                    self._send_packet(self._final_ack(self.ack_address_override, self.packet_sequence))
                    self.logger.debug("Conversation ended")
                except Exception as e:
                    self.logger.exception("Error during ending conversation, ignored.")
            else:
                self.radio_ready.set()

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

        packets = pdm_message.get_radio_packets(message_address=pdm_message_address,
                                                message_sequence=self.message_sequence,
                                                packet_address=self.radio_address,
                                                first_packet_sequence=self.packet_sequence)
        self.logger.info("SENDING MSG: %s" % pdm_message)
        received = None

        if tx_power is not None:
            self.packet_radio.set_tx_power(tx_power)

        if len(packets) > 1:
            if double_take:
                received = self._exchange_packets(packets[0].with_sequence(self.packet_sequence), RadioPacketType.ACK)
                self.packet_sequence = (received.sequence + 1) % 32

            received = self._exchange_packets(packets[0].with_sequence(self.packet_sequence), RadioPacketType.ACK)
            self.packet_sequence = (received.sequence + 1) % 32

            if len(packets) > 2:
                for packet in packets[1:-1]:
                    received = self._exchange_packets(packet, RadioPacketType.ACK)
                    self.packet_sequence = (received.sequence + 1) % 32

        received = self._exchange_packets(packets[-1].with_sequence(self.packet_sequence), RadioPacketType.POD)
        self.packet_sequence = (received.sequence + 1) % 32

        pod_response = PodMessage()
        while not pod_response.add_radio_packet(received):
            ack_packet = self._interim_ack(ack_address_override, (received.sequence + 1) % 32)
            received = self._exchange_packets(ack_packet, RadioPacketType.CON)

        self.logger.info("RECEIVED MSG: %s" % pod_response)
        self.message_sequence = (pod_response.sequence + 1) % 16
        return pod_response


    def _exchange_packets(self, packet_to_send, expected_type):
        send_retries = 10
        while send_retries > 0:
            try:
                self.logger.debug("SENDING: %s" % packet_to_send)

                send_retries -= 1
                received = self.packet_radio.send_and_receive_packet(packet_to_send.get_data(), 0, 0, 100, 1, 130)

                if received is None:
                    self.logger.debug("Received nothing")
                    self.packet_radio.tx_up()
                    continue
                p, rssi = self._get_packet(received)
                if p is None:
                    self.logger.debug("RECEIVED BAD DATA: %s" % received.hex())
                    self.packet_radio.tx_down()
                    continue

                if expected_type is not None and p.type != expected_type:
                    if self.last_packet_received is not None:
                        if p.address == self.last_packet_received.address and \
                                p.sequence == self.last_packet_received.sequence:
                            self.logger.debug("Received previous response")
                            self.packet_radio.tx_up()
                            continue

                    self.logger.debug("RECEIVED unexpected packet: %s" % p)
                    self.packet_sequence = (p.sequence + 1) % 32
                    packet_to_send.with_sequence(self.packet_sequence)
                    continue

                self.logger.debug("RECEIVED: %s" % p)
                self.last_packet_received = p
                self.logger.debug("SEND AND RECEIVE complete")
                return p
            except PacketRadioError:
                self.logger.exception("Radio error during send and receive, retrying")
                self.disconnect()
        else:
            self.disconnect()
            raise ProtocolError("Exceeded retry count while send and receive")

    def _send_packet(self, packet_to_send):
        self.send_final_complete.clear()
        while True:
            try:
                self.logger.debug("SENDING: %s" % packet_to_send)

                received = self.packet_radio.send_and_receive_packet(packet_to_send.get_data(), 3, 100, 100, 3, 20)
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
                    self.logger.debug("RECEIVED BAD DATA: %s" % received.hex())
                    self.packet_radio.tx_down()
                    continue
                if self.last_packet_received is not None:
                    if p[0] == self.last_packet_received[0]:
                        self.logger.debug("Received previous response")
                        self.packet_radio.tx_up()
                        continue

                self.logger.debug("RECEIVED unexpected packet: %s" % p)
                continue

            except PacketRadioError:
                self.logger.exception("Radio error during sending")
                self.packet_radio.disconnect()
        self.packet_sequence = (self.packet_sequence + 1) % 32
        self.logger.debug("SEND FINAL complete")
        self.send_final_complete.set()

    def _get_packet(self, data):
        rssi = None
        if data is not None and len(data) > 2:
            rssi = data[0]
            try:
                return RadioPacket.parse(data[2:]), rssi
            except:
                getLogger().exception("RECEIVED DATA: %s RSSI: %d" % (binascii.hexlify(data[2:]), rssi))
        return None, rssi
