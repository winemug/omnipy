from .exceptions import ProtocolError, PacketRadioError
from podcomm import crc
from .packet_radio import TxPower
from .pr_rileylink import RileyLink
from .message import Message, MessageState
from .packet import Packet
from .definitions import *
from threading import Thread, Event

class Radio:
    def __init__(self, msg_sequence=0, pkt_sequence=0):
        self.messageSequence = msg_sequence
        self.packetSequence = pkt_sequence
        self.lastPacketReceived = None
        self.logger = getLogger()
        self.packetRadio = RileyLink()
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

    def send_request_get_response(self, message, tx_power=None, double_take=False):
        self.radio_ready.wait()
        self.radio_ready.clear()

        self.request_message = message
        self.double_take = double_take
        self.tx_power = tx_power

        self.request_arrived.set()

        self.response_received.wait()
        self.response_received.clear()
        if self.response_message is None:
            raise self.response_exception
        return self.response_message

    def disconnect(self):
        try:
            self.packetRadio.disconnect(ignore_errors=True)
        except Exception:
            self.logger.exception("Error while disconnecting")

    def _radio_loop(self):
        self.radio_ready.set()
        while True:
            if not self.request_arrived.wait(timeout=10.0):
                self.disconnect()
            self.request_arrived.wait()
            self.request_arrived.clear()

            message_address = self.request_message.address
            message_candidate_address = self.request_message.candidate_address

            try:
                self.response_message = self._send_request(self.request_message, tx_power=self.tx_power,
                                                           double_take=self.double_take)
            except Exception as e:
                self.response_message = None
                self.response_exception = e
            finally:
                self.response_received.set()

            self.radio_ready.set()

            try:
                self.logger.debug("Ending conversation")
                if message_address == 0xffffffff and message_candidate_address is not None:
                    ack_packet = Packet.Ack(message_address, message_candidate_address)
                else:
                    ack_packet = Packet.Ack(message_address, 0x00000000)
                self._send_packet(ack_packet)
                self.logger.debug("Conversation ended")
            except Exception as e:
                self.logger.exception("Error during ending conversation, ignored.")



    def _send_request(self, message, tx_power=None, double_take=False):

        if tx_power is not None:
            self.packetRadio.set_tx_power(tx_power)

        message.setSequence(self.messageSequence)
        self.logger.debug("SENDING MSG: %s" % message)
        packets = message.getPackets()
        received = None
        packet_index = 1
        packet_count = len(packets)
        for packet in packets:
            while True:
                if packet_index == packet_count:
                    expected_type = "POD"
                else:
                    expected_type = "ACK"
                received = self._exchange_packets(packet, expected_type)
                if received is None:
                    raise ProtocolError("Timeout reached waiting for a response.")

                if received.type != expected_type:
                    raise ProtocolError("Invalid response received. Expected type %s, received %s"
                                        % (expected_type, received.type))

                if double_take:
                    double_take=False
                else:
                    break

            packet_index += 1

        pod_response = Message.fromPacket(received)

        while pod_response.state == MessageState.Incomplete:
            if message.candidate_address is not None:
                ack_packet = Packet.Ack(message.address, message.candidate_address)
            else:
                ack_packet = Packet.Ack(message.address, message.address2)
            received = self._exchange_packets(ack_packet, "CON")
            if received is None:
                raise ProtocolError("Timeout reached waiting for a response.")
            if received.type != "CON":
                raise ProtocolError("Invalid response received. Expected type CON, received %s" % received.type)
            pod_response.addConPacket(received)

        if pod_response.state == MessageState.Invalid:
            raise ProtocolError("Received message is not valid")

        self.logger.debug("RECEIVED MSG: %s" % pod_response)
        self.messageSequence = (pod_response.sequence + 1) % 16
        return pod_response


    def _exchange_packets(self, packet_to_send, expected_type):
        send_retries = 30
        while send_retries > 0:
            try:
                packet_to_send.setSequence(self.packetSequence)
                expected_sequence = (self.packetSequence + 1) % 32
                expected_address = packet_to_send.address
                self.logger.debug("SENDING PACKET EXP RESPONSE: %s" % packet_to_send)
                data = packet_to_send.data
                data += bytes([crc.crc8(data)])

                if packet_to_send.type == "PDM":
                    send_retries -= 1
                    received = self.packetRadio.send_and_receive_packet(data, 0, 0, 100, 1, 130)
                else:
                    received = self.packetRadio.send_and_receive_packet(data, 0, 0, 100, 10, 20)

                if received is None:
                    self.logger.debug("Received nothing")
                    self.packetRadio.tx_up()
                    continue
                p, rssi = self._get_packet(received)
                if p is None:
                    self.logger.debug("Received bad packet")
                    self.packetRadio.tx_down()
                    continue
                if p.address != expected_address and p.address2 != packet_to_send.address2:
                    self.logger.debug("Received packet for a different radio_address")
                    self.packetRadio.tx_down()
                    continue

                if p.type != expected_type or p.sequence != expected_sequence:
                    if self.last_packet_received is not None:
                        if p.type == self.last_packet_received.type and \
                                p.sequence == self.last_packet_received.sequence:
                            self.logger.debug("Received previous response")
                            self.packetRadio.tx_up()
                            continue

                    self.logger.debug("Received unexpected packet")
                    self.packetSequence = (p.sequence + 1) % 32
                    continue

                self.packetSequence = (self.packetSequence + 2) % 32
                self.last_packet_received = p
                self.logger.debug("SEND AND RECEIVE complete")
                return p
            except PacketRadioError:
                self.logger.exception("Radio error during send and receive")
                self.packetRadio.disconnect()
        else:
            raise ProtocolError("Exceeded retry count while send and receive")

    def _send_packet(self, packetToSend):
        self.send_final_complete.clear()
        while True:
            try:
                packetToSend.setSequence(self.packetSequence)
                data = packetToSend.data
                data += bytes([crc.crc8(data)])

                self.logger.debug("SENDING FINAL PACKET: %s" % packetToSend)
                received = self.packetRadio.send_and_receive_packet(data, 3, 100, 100, 3, 20)
                if self.request_arrived.wait(timeout=0):
                    self.logger.debug("Prematurely exiting final phase to process next request")
                    self.packetSequence = (self.packetSequence + 2) % 32
                    return
                if received is None:
                    received = self.packetRadio.get_packet(1.0)
                    if received is None:
                        self.logger.debug("Silence has fallen")
                        break
                p, rssi = self._get_packet(received)
                if p is None:
                    self.logger.debug("Received bad packet")
                    self.packetRadio.tx_down()
                    continue
                if p.address != packetToSend.address and p.address2 != packetToSend.address2:
                    self.logger.debug("Received packet for a different radio_address")
                    self.packetRadio.tx_down()
                    continue
                if self.last_packet_received is not None:
                    if p.type == self.last_packet_received.type and \
                            p.sequence == self.last_packet_received.sequence:
                        self.logger.debug("Received previous response")
                        self.packetRadio.tx_up()
                        continue
                self.logger.debug("Received unexpected packet")
                self.packetSequence = (p.sequence + 1) % 32
                continue

            except PacketRadioError:
                self.logger.exception("Radio error during sending")
                self.packetRadio.disconnect()
        self.packetSequence = (self.packetSequence + 1) % 32
        self.logger.debug("SEND FINAL complete")
        self.send_final_complete.set()

    @staticmethod
    def _get_packet(data):
        p = None
        rssi = None
        if data is not None and len(data) > 2:
            rssi = data[0]
            calc = crc.crc8(data[2:-1])
            if data[-1] == calc:
                try:
                    p = Packet.from_data(data[2:-1])
                    getLogger().debug("RECEIVED PACKET: %s RSSI: %d" % (p, rssi))
                except ProtocolError as pe:
                    getLogger().warning("Crc match on an invalid packet, error: %s" % pe)
        return p, rssi
