from random import randint
import threading
import binascii
from podcomm import crc
from podcomm.rileylink import RileyLink, RileyLinkError, Response
from .packet import Packet
import logging
from .message import Message, MessageState
import time


class RadioError(Exception):
    def __init__(self, message="Unknown"):
        self.error_message = message


class ProtocolError(Exception):
    def __init__(self, message="Unknown"):
        self.error_message = message


class Radio:
    def __init__(self, msg_sequence = 0, pkt_sequence = 0):
        self.stopRadioEvent = threading.Event()
        self.messageSequence = msg_sequence
        self.packetSequence = pkt_sequence
        self.lastPacketReceived = None
        self.responseTimeout = 1000
        self.rileyLink = RileyLink()
        self.rileyLink.connect()
        self.rileyLink.init_radio()
        self.rileyLink.disconnect()

    def __logPacket(self, p):
        logging.debug("Packet received: %s" % p)

    def __logMessage(self, msg):
        logging.debug("Message received: %s" % msg)

    # def sendRequestToPodOld(self, message, responseHandler = None):
    #     try:
    #         self.rileyLink.connect()
    #         self.rileyLink.init_radio()
    #         while True:
    #             time.sleep(3)
    #             message.setSequence(self.messageSequence)
    #             logging.debug("SENDING MSG: %s" % message)
    #             packets = message.getPackets()
    #             received = None
    #
    #             for i in range(0, len(packets)):
    #                 packet = packets[i]
    #                 if i == len(packets)-1:
    #                     exp = "POD"
    #                 else:
    #                     exp = "ACK"
    #                 received = self.__sendPacketAndGetPacketResponse(packet, exp)
    #                 if received is None:
    #                     raise ProtocolError()
    #
    #             podResponse = Message.fromPacket(received)
    #             if podResponse is None:
    #                 raise ProtocolError()
    #
    #             while podResponse.state == MessageState.Incomplete:
    #                 ackPacket = Packet.Ack(message.address, False)
    #                 received = self.__sendPacketAndGetPacketResponse(ackPacket, "CON")
    #                 podResponse.addConPacket(received)
    #
    #             if podResponse.state == MessageState.Invalid:
    #                 raise ProtocolError()
    #
    #             logging.debug("RECEIVED MSG: %s" % podResponse)
    #             respondResult = None
    #             if responseHandler is not None:
    #                 respondResult = responseHandler(message, podResponse)
    #
    #             if respondResult is None:
    #                 ackPacket = Packet.Ack(message.address, True)
    #                 self.__sendPacketUntilQuiet(ackPacket)
    #                 self.messageSequence = (podResponse.sequence + 1) % 16
    #                 return podResponse
    #             else:
    #                 message = respondResult
    #     except:
    #         raise
    #     finally:
    #         self.rileyLink.disconnect()

    def sendRequestToPod(self, message, try_resync=True):
        try:
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


    def resyncPod(self, address):
        self.rileyLink.connect()
        self.rileyLink.init_radio()

        logging.info("Checking if the pod is still broadcasting")
        while True:
            logging.info("Listening to pod")
            try:
                received = self.rileyLink.get_packet(0.3)
            except RileyLinkError as rle:
                if rle.response_code == Response.RX_TIMEOUT:
                    break
                else:
                    raise rle

            if received is None:
                break

            p = self.__getPacket(received)
            if p is not None and p.address == address:
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
                received = self._sendPacketAndGetPacket(packet)
                if received is None:
                    raise ProtocolError("No response from Pod")
                if packet_index == packet_count:
                    if received.type != "POD":
                        raise ProtocolError("Invalid response from Pod")
                else:
                    if received.type != "ACK":
                        raise ProtocolError("Invalid response from Pod")

            pod_response = Message.fromPacket(received)
            if pod_response is None:
                raise ProtocolError()

            while pod_response.state == MessageState.Incomplete:
                ack_packet = Packet.Ack(message.address, False)
                received = self._sendPacketAndGetPacket(ack_packet)
                if received is None:
                    raise ProtocolError("No response from Pod")
                if received.type != "CON":
                    raise ProtocolError("Invalid response from Pod")
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
        except:
            raise
        finally:
            self.rileyLink.disconnect()


    def _sendPacketAndGetPacket(self, packetToSend):
        packetToSend.setSequence(self.packetSequence)
        expectedSequence = (self.packetSequence + 1) % 32
        send_retries = 2
        while send_retries > 0:
            try:
                send_retries -= 1
                logging.debug("SENDING PACKET EXP RESPONSE: %s (retries left: %d)" % (packetToSend, send_retries))
                data = packetToSend.data
                data += bytes([crc.crc8(data)])
                if packetToSend.type == "PDM":
                    received = self.rileyLink.send_and_receive_packet(data, 0, 0, 300, 30, 80)
                else:
                    received = self.rileyLink.send_and_receive_packet(data, 3, 20, 300, 30, 20)

                receive_retries = 10
                while receive_retries > 0:
                    if received is None:
                        received = self.rileyLink.get_packet(100)
                    try:
                        receive_retries -= 1
                        if received is None:
                            logging.debug("Nothing received")
                            continue
                    except RileyLinkError as rle:
                        if rle.response_code == Response.RX_TIMEOUT:
                            logging.debug("Receive timeout")
                            continue
                        else:
                            raise rle
                    p = self.__getPacket(received)
                    if p is None:
                        logging.debug("Received invalid packet. " % binascii.hexlify(received))
                        received = None
                        continue
                    if p.address != packetToSend.address:
                        logging.debug("Received packet address mismatch. %s" % p)
                        received = None
                        continue
                    elif p.sequence != expectedSequence:
                        logging.debug("Received packet sequence mismatch. %s" % p)
                        received = None
                        continue
                    else:
                        self.packetSequence = (self.packetSequence + 2) % 32
                        logging.debug("Received packet valid. %s" % p)
                        logging.debug("SEND RECV complete")
                        return p
            except RileyLinkError as rle:
                logging.error("Error while sending %s" % rle)
                continue
        raise ProtocolError("Send and receive failed")

    def _sendPacket(self, packetToSend):
        packetToSend.setSequence(self.packetSequence)
        try:
            data = packetToSend.data
            data += bytes([crc.crc8(data)])
            receive_retries = 10
            while receive_retries > 0:
                try:
                    logging.debug("SENDING FINAL PACKET: %s (retries left: %d)" % (packetToSend, receive_retries))
                    self.rileyLink.send_packet(data, 3, 20, 42)
                    receive_retries -= 1
                    received = self.rileyLink.get_packet(0.3)
                    if received is None:
                        break
                except RileyLinkError as rle:
                    if rle.response_code == Response.RX_TIMEOUT:
                        break
                    else:
                        raise rle
                p = self.__getPacket(received)
                if p is None or p.address != packetToSend.address:
                    break
                logging.warning("Still receiving POD packets")
            self.packetSequence = (self.packetSequence + 1) % 32
            logging.debug("SEND FINAL complete")
        except RileyLinkError as rle:
            logging.error("Error while sending %s" % rle)

    # def __sendPacketUntilQuiet(self, packetToSend, trackSequencing = True):
    #     if trackSequencing:
    #         packetToSend.setSequence(self.packetSequence)
    #     logging.debug("SENDING PACKET expecting quiet: %s" % packetToSend)
    #     data = packetToSend.data
    #     data += bytes([crc.crc8(data)])
    #
    #     while True:
    #         self.rileyLink.send_packet(data, 0, 0, 42)
    #         timed_out = False
    #         received = None
    #         try:
    #             received = self.rileyLink.get_packet(300)
    #         except RileyLinkError as rle:
    #             if rle.response_code != Response.RX_TIMEOUT:
    #                 raise rle
    #             else:
    #                 timed_out = True
    #
    #         if not timed_out and received is not None:
    #             p = self.__getPacket(received)
    #             if p is not None:
    #                 continue
    #
    #         if trackSequencing:
    #             self.packetSequence = (self.packetSequence + 1) % 32
    #         return
    #
    # def __sendPacketAndGetPacketResponse(self, packetToSend, expectedType, trackSequencing = True, retry_count = 3):
    #     expectedAddress = packetToSend.address
    #     retries = retry_count
    #     while retries > 0:
    #         if trackSequencing:
    #             packetToSend.setSequence(self.packetSequence)
    #         logging.debug("SENDING PACKET expecting response: %s" % packetToSend)
    #         data = packetToSend.data
    #         data += bytes([crc.crc8(data)])
    #         self.rileyLink.send_packet(data, 0, 0, 100)
    #         p = self.__getPacket(received)
    #         if p is not None and p.address == expectedAddress:
    #             logging.debug("RECEIVED PACKET: %s" % p)
    #             packet_accepted = False
    #             if expectedType is None:
    #                 if self.lastPacketReceived is None:
    #                     packet_accepted = True
    #                 else:
    #                     if self.lastPacketReceived.data != p.data:
    #                         packet_accepted = True
    #             else:
    #                 if p.type == expectedType:
    #                     packet_accepted = True
    #
    #             if packet_accepted:
    #                 logging.debug("received packet accepted. %s" % p)
    #                 if trackSequencing:
    #                     self.packetSequence = (p.sequence + 1) % 32
    #                 self.lastPacketReceived = p
    #                 return p
    #             else:
    #                 logging.debug("received packet does not match expected criteria. %s" % p)
    #                 if trackSequencing:
    #                     self.packetSequence = (p.sequence + 1) % 32
    #         retries = retries - 1
    #         logging.info("Retries left: %d" % retries)


    def __getPacket(self, data):
        if data is not None and len(data) > 2:
            calc = crc.crc8(data[2:-1])
            if data[-1] == calc:
                return Packet(0, data[2:-1])
        return None
