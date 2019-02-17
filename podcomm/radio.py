import binascii
import logging
import threading
import time

from .exceptions import ProtocolError, RileyLinkError
from podcomm import crc
from podcomm.rileylink import RileyLink, Response
from .message import Message, MessageState
from .packet import Packet



class Radio:
    def __init__(self, msg_sequence = 0, pkt_sequence = 0):
        self.stopRadioEvent = threading.Event()
        self.messageSequence = msg_sequence
        self.packetSequence = pkt_sequence
        self.lastPacketReceived = None
        self.responseTimeout = 1000
        self.rileyLink = RileyLink()
        self.connected = False

    def __logPacket(self, p):
        logging.debug("Packet received: %s" % p)

    def __logMessage(self, msg):
        logging.debug("Message received: %s" % msg)

    def sendRequestToPod(self, message, try_resync=True, stay_connected=True):
        try:
            self.connect()
            return self._sendRequest(message)
        except ProtocolError as pe:
            if try_resync:
                logging.error("Protocol error: %s" % pe)
                logging.info("Trying to resync sequences with pod")
                self.resyncPod(message.address)
                logging.info("Retrying request one more time")
                return self._sendRequest(message)
            else:
                raise
        finally:
            if not stay_connected:
                self.disconnect()

    def connect(self):
        try:
            self.rileyLink.connect()
            self.connected = True
        except RileyLinkError as rle:
            logging.error("Error while connecting to RileyLink: %s" % rle)
            raise rle

    def disconnect(self):
        try:
            self.rileyLink.disconnect()
        except RileyLinkError as rle:
            logging.warning("Error while disconnecting from RileyLink: %s" % rle)


    def resyncPod(self, address):
        self.connect()

        logging.info("Checking if the pod is still broadcasting")
        while True:
            logging.info("Listening to pod")
            received = self.rileyLink.get_packet(0.3)
            if received is None:
                break
            p = self.__getPacket(received)
            if p is None or p.address != address:
                continue
            logging.info("Received broadcast from pod, responding to it")
            ack = Packet.Ack(address, True)
            ack.setSequence((p.sequence + 1) % 32)
            data = ack.data
            data += bytes([crc.crc8(data)])
            self.rileyLink.send_packet(data, 10, 100, 45)

        logging.info("Radio silence confirmed")
        time.sleep(2)
        logging.info("Sending request for sync")
        ack = Packet.Ack(address, True)
        ack.setSequence(0)
        data = ack.data
        data += bytes([crc.crc8(data)])
        self.rileyLink.send_packet(data, 5, 100, 250)
        logging.info("All done, fingers crossed.")
        self.rileyLink.disconnect()
        self.packetSequence = 1
        self.messageSequence = 0
        time.sleep(2)

    def _sendRequest(self, message):
        try:
            self.rileyLink.connect()
            self.rileyLink.init_radio()
            message.setSequence(self.messageSequence)
            logging.debug("SENDING MSG: %s" % message)
            packets = message.getPackets()
            received = None
            packet_index = 1
            packet_count = len(packets)
            for packet in packets:
                if packet_index == packet_count:
                    expected_type = "POD"
                else:
                    expected_type = "ACK"
                received = self._sendPacketAndGetPacket(packet, expected_type)
                if received is None:
                    raise ProtocolError("Timeout reached waiting for a response.")

                if received.type != expected_type:
                    raise ProtocolError("Invalid response received. Expected type %s, received %s"
                                        % (expected_type, received.type))
                packet_index += 1

            pod_response = Message.fromPacket(received)

            while pod_response.state == MessageState.Incomplete:
                ack_packet = Packet.Ack(message.address, False)
                received = self._sendPacketAndGetPacket(ack_packet, "CON")
                if received is None:
                    raise ProtocolError("Timeout reached waiting for a response.")
                if received.type != "CON":
                    raise ProtocolError("Invalid response received. Expected type CON, received %s" % received.type)
                pod_response.addConPacket(received)

            if pod_response.state == MessageState.Invalid:
                raise ProtocolError("Received message is not valid")

            logging.debug("RECEIVED MSG: %s" % pod_response)

            logging.debug("Sending end of conversation")
            ack_packet = Packet.Ack(message.address, True)
            self._sendPacket(ack_packet)
            logging.debug("Conversation ended")

            self.messageSequence = (pod_response.sequence + 1) % 16
            return pod_response
        finally:
            self.rileyLink.disconnect()

    def _eval_received_unexpected_packet(self, data, expected_address, expected_sequence, expected_type):
        pass
    def _eval_received_data_as_packet(self, data, expected_address, expected_sequence, expected_type):
        if data is None:
            logging.debug("Receive timed out.")
            return None
        p = self.__getPacket(data)
        if p is None:
            logging.debug("Received invalid packet. " % binascii.hexlify(data))
            return None
        if p.address != expected_address:
            logging.debug("Received packet address mismatch. %s" % p)
            return None
        elif p.sequence != expected_sequence:
            logging.debug("Received packet sequence mismatch. %s" % p)
            return None
        elif p.type != expected_type:
            logging.debug("Received unexpected packet type %s" % ())
            return None
        return p

    def _sendPacketAndGetPacket(self, packet_to_send, expected_type):
        packet_to_send.setSequence(self.packetSequence)
        expected_sequence = (self.packetSequence + 1) % 32
        expected_address = packet_to_send.address
        send_retries = 3
        while send_retries > 0:
            try:
                send_retries -= 1
                logging.debug("SENDING PACKET EXP RESPONSE: %s (retries left: %d)" % (packet_to_send, send_retries))
                data = packet_to_send.data
                data += bytes([crc.crc8(data)])

                if packet_to_send.type == "PDM":
                    received = self.rileyLink.send_and_receive_packet(data, 0, 0, 300, 10, 80)
                else:
                    received = self.rileyLink.send_and_receive_packet(data, 3, 20, 300, 10, 20)

                packet_response = self._eval_received_data_as_packet(received,
                                                                     expected_address, expected_sequence, expected_type)
                if packet_response is not None:
                    return packet_response

                receive_retries = 15
                while received is None and receive_retries > 0:
                    receive_retries -= 1
                    received = self.rileyLink.get_packet(0.1)
                    packet_response = self._eval_received_data_as_packet(received,
                                                                         expected_address, expected_sequence,
                                                                         expected_type)
                    if packet_response is not None:
                        return packet_response
            except RileyLinkError as rle:
                raise ProtocolError("Radio error during send and receive") from rle
        raise ProtocolError("Send and receive handshake failed")

    def _sendPacket(self, packetToSend):
        packetToSend.setSequence(self.packetSequence)
        try:
            data = packetToSend.data
            data += bytes([crc.crc8(data)])
            receive_retries = 10
            while receive_retries > 0:
                logging.debug("SENDING FINAL PACKET: %s (retries left: %d)" % (packetToSend, receive_retries))
                self.rileyLink.send_packet(data, 3, 20, 42)
                receive_retries -= 1
                received = self.rileyLink.get_packet(0.3)
                if received is None:
                    break

                p = self.__getPacket(received)
                if p is None or p.address != packetToSend.address:
                    break
                logging.warning("Still receiving POD packets")
            self.packetSequence = (self.packetSequence + 1) % 32
            logging.debug("SEND FINAL complete")
        except RileyLinkError as rle:
            logging.error("Error while sending %s" % rle)

    def __getPacket(self, data):
        p = None
        if data is not None and len(data) > 2:
            calc = crc.crc8(data[2:-1])
            if data[-1] == calc:
                try:
                    p = Packet.from_data(data[2:-1])
                except ProtocolError as pe:
                    logging.warning("Crc match on an invalid packet, error: %s" % pe)
        return p
