import threading
from .exceptions import ProtocolError, RileyLinkError, TransmissionOutOfSyncError
from podcomm import crc
from podcomm.rileylink import RileyLink
from .message import Message, MessageState
from .packet import Packet
from .definitions import *


class Radio:
    def __init__(self, msg_sequence = 0, pkt_sequence = 0):
        self.stopRadioEvent = threading.Event()
        self.messageSequence = msg_sequence
        self.packetSequence = pkt_sequence
        self.lastPacketReceived = None
        self.logger = getLogger()
        self.rileyLink = RileyLink()

    def send_request_get_response(self, message, stay_connected=True):
        try:
            return self._send_request_get_response(message, stay_connected)
        except TransmissionOutOfSyncError:
            raise
        except Exception:
            self.rileyLink.disconnect(ignore_errors=True)
            raise

    def disconnect(self):
        try:
            self.rileyLink.disconnect(ignore_errors=True)
        except Exception as e:
            self.logger.warning("Error while disconnecting %s" % str(e))

    def _send_request_get_response(self, message, stay_connected=True):
        try:
            return self._send_request(message)
        except TransmissionOutOfSyncError:
            self.logger.warning("Transmission out of sync, radio needs resyncing")
            raise
        finally:
            if not stay_connected:
                self.rileyLink.disconnect()

    def _send_request(self, message):
        message.setSequence(self.messageSequence)
        self.logger.debug("SENDING MSG: %s" % message)
        packets = message.getPackets()
        received = None
        packet_index = 1
        packet_count = len(packets)
        for packet in packets:
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
            packet_index += 1

        pod_response = Message.fromPacket(received)

        while pod_response.state == MessageState.Incomplete:
            ack_packet = Packet.Ack(message.address, False)
            received = self._exchange_packets(ack_packet, "CON")
            if received is None:
                raise ProtocolError("Timeout reached waiting for a response.")
            if received.type != "CON":
                raise ProtocolError("Invalid response received. Expected type CON, received %s" % received.type)
            pod_response.addConPacket(received)

        if pod_response.state == MessageState.Invalid:
            raise ProtocolError("Received message is not valid")

        self.logger.debug("RECEIVED MSG: %s" % pod_response)

        self.logger.debug("Sending end of conversation")
        ack_packet = Packet.Ack(message.address, True)
        self._send_packet(ack_packet)
        self.logger.debug("Conversation ended")

        self.messageSequence = (pod_response.sequence + 1) % 16
        return pod_response

    def _exchange_packets(self, packet_to_send, expected_type):
        packet_to_send.setSequence(self.packetSequence)
        expected_sequence = (self.packetSequence + 1) % 32
        expected_address = packet_to_send.address
        send_retries = 3
        while send_retries > 0:
            try:
                send_retries -= 1
                self.logger.debug("SENDING PACKET EXP RESPONSE: %s (retries left: %d)" % (packet_to_send, send_retries))
                data = packet_to_send.data
                data += bytes([crc.crc8(data)])

                if packet_to_send.type == "PDM":
                    received = self.rileyLink.send_and_receive_packet(data, 0, 300, 300, 10, 80)
                else:
                    received = self.rileyLink.send_and_receive_packet(data, 0, 20, 300, 10, 20)

                if received is None:
                    continue
                p = self._get_packet(received)
                if p is None or p.address != expected_address:
                    continue

                if p.type != expected_type or p.sequence != expected_sequence:
                    self.packetSequence = (p.sequence + 1) % 32
                    self.messageSequence = 0
                    raise TransmissionOutOfSyncError()
                self.packetSequence = (self.packetSequence + 2) % 32
                self.logger.debug("SEND AND RECEIVE complete")
                return p
            except RileyLinkError as rle:
                raise ProtocolError("Radio error during send and receive") from rle
        else:
            raise ProtocolError("Exceeded retry count while send and receive")

    def _send_packet(self, packetToSend):
        packetToSend.setSequence(self.packetSequence)
        try:
            data = packetToSend.data
            data += bytes([crc.crc8(data)])
            receive_retries = 20
            while receive_retries > 0:
                receive_retries -= 1
                self.logger.debug("SENDING FINAL PACKET: %s (retries left: %d)" % (packetToSend, receive_retries))
                received = self.rileyLink.send_and_receive_packet(data, 0, 20, 1000, 2, 40)
                if received is None:
                    break
                p = self._get_packet(received)
                if p is None:
                    break
                if p.address != packetToSend.address:
                    continue
                self.logger.warning("Still receiving POD packets")
                if p.sequence == packetToSend.sequence:
                    self.packetSequence = (self.packetSequence + 1) % 32
                    self.messageSequence = 0
                    raise TransmissionOutOfSyncError()
            else:
                raise ProtocolError("Exceeded retry count while sending")
            self.packetSequence = (self.packetSequence + 1) % 32
            self.logger.debug("SEND FINAL complete")
        except RileyLinkError as rle:
            raise ProtocolError("Radio error during sending") from rle

    @staticmethod
    def _get_packet(data):
        p = None
        if data is not None and len(data) > 2:
            calc = crc.crc8(data[2:-1])
            if data[-1] == calc:
                try:
                    p = Packet.from_data(data[2:-1])
                    getLogger().debug("RECEIVED PACKET: %s" % p)
                except ProtocolError as pe:
                    getLogger().warning("Crc match on an invalid packet, error: %s" % pe)
        return p
