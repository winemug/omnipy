import logging
import os
import struct
import time
from enum import IntEnum
from threading import Event

from bluepy.btle import Peripheral, Scanner, BTLEDisconnectError


class Command(IntEnum):
    GET_STATE = 1
    GET_VERSION = 2
    GET_PACKET = 3
    SEND_PACKET = 4
    SEND_AND_LISTEN = 5
    UPDATE_REGISTER = 6
    RESET = 7
    LED = 8
    READ_REGISTER = 9
    SET_MODE_REGISTERS = 10
    SET_SW_ENCODING = 11
    SET_PREAMBLE = 12
    RADIO_RESET_CONFIG = 13


class Response(IntEnum):
    PROTOCOL_SYNC = 0x00
    UNKNOWN_COMMAND = 0x22
    RX_TIMEOUT = 0xaa
    COMMAND_INTERRUPTED = 0xbb
    COMMAND_SUCCESS = 0xdd


class Register(IntEnum):
    SYNC1 = 0x00
    SYNC0 = 0x01
    PKTLEN = 0x02
    PKTCTRL1 = 0x03
    PKTCTRL0 = 0x04
    FSCTRL1 = 0x07
    FREQ2 = 0x09
    FREQ1 = 0x0a
    FREQ0 = 0x0b
    MDMCFG4 = 0x0c
    MDMCFG3 = 0x0d
    MDMCFG2 = 0x0e
    MDMCFG1 = 0x0f
    MDMCFG0 = 0x10
    DEVIATN = 0x11
    MCSM0 = 0x14
    FOCCFG = 0x15
    AGCCTRL2 = 0x17
    AGCCTRL1 = 0x18
    AGCCTRL0 = 0x19
    FREND1 = 0x1a
    FREND0 = 0x1b
    FSCAL3 = 0x1c
    FSCAL2 = 0x1d
    FSCAL1 = 0x1e
    FSCAL0 = 0x1f
    TEST1 = 0x24
    TEST0 = 0x25
    PATABLE0 = 0x2e


class Encoding(IntEnum):
    NONE = 0
    MANCHESTER = 1
    FOURBSIXB = 2


class RileyLinkError(Exception):
    def __init__(self, message, response_code=None):
        self.error_message = message
        self.response_code = response_code

    def __str__(self):
        return "RileyLinkError: %s" % self.error_message

class RileyLink:
    def __init__(self, address = None):
        self.p = Peripheral()
        self.data_handle = None
        if address is None:
            if os.path.exists(".rladdr"):
                with open(".rladdr", "r") as stream:
                    address = stream.read()
        self.address = address
        self.service = None
        self.response_handle = None
        self.notify_event = Event()

    def findRileyLink(self):
        scanner = Scanner()
        found = None
        logging.debug("Scanning for RileyLink")
        for result in scanner.scan(6.0):
            if result.getValueText(7) == "0235733b-99c5-4197-b856-69219c2a3845":
                logging.debug("Found RileyLink")
                found = result.addr
                stream = open(".rladdr", "w")
                stream.write(result.addr)
                stream.close()
                break
        else:
            logging.error("RileyLink not found")
        return found
        
    def connect(self):
        if self.address is None:
            self.address = self.findRileyLink()

        self._connect_retry(3)

        self.service = self.p.getServiceByUUID("0235733b-99c5-4197-b856-69219c2a3845")
        data_char = self.service.getCharacteristics("c842e849-5028-42e2-867c-016adada9155")[0]
        self.data_handle = data_char.getHandle()

        char_response = self.service.getCharacteristics("6e6c7910-b89e-43a5-a0fe-50c5e2b81f4a")[0]
        self.response_handle = char_response.getHandle()

        response_notify_handle = self.response_handle + 1
        notify_setup = b"\x01\x00"
        self.p.writeCharacteristic(response_notify_handle, notify_setup)

        while self.p.waitForNotifications(0.05):
            self.p.readCharacteristic(self.data_handle)

    def _connect_retry(self, retries):
        while retries > 0:
            retries -= 1
            logging.info("Connecting to RileyLink, retries left: %d" % retries)
            try:
                self.p.connect(self.address)
                logging.info("Connected")
                break
            except BTLEDisconnectError:
                logging.warning("BTLE disconnect error received")
                time.sleep(2)

    def disconnect(self):
        logging.info("Disconnecting..")
        response_notify_handle = self.response_handle + 1
        notify_setup = b"\x00\x00"
        self.p.writeCharacteristic(response_notify_handle, notify_setup)
        self.p.disconnect()
        logging.info("Disconnected")

    def init_radio(self):
        response = self.__command(Command.READ_REGISTER, bytes([Register.SYNC1]))
        if len(response) > 0 and response[0] == 0xA5:
            return

        try:
            self.__command(Command.RADIO_RESET_CONFIG)
            self.__command(Command.SET_SW_ENCODING, bytes([Encoding.MANCHESTER]))
            frequency = int(433910000 / (24000000 / pow(2, 16)))
            self.__command(Command.SET_PREAMBLE, bytes([0x66, 0x65]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FREQ0, frequency & 0xff]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FREQ1, (frequency >> 8) & 0xff]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FREQ2, (frequency >> 16) & 0xff]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.PKTCTRL1, 0x20]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.PKTCTRL0, 0x00]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FSCTRL1, 0x06]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.MDMCFG4, 0xCA]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.MDMCFG3, 0xBC]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.MDMCFG2, 0x06]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.MDMCFG1, 0x70]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.MDMCFG0, 0x11]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.DEVIATN, 0x44]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.MCSM0, 0x18]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FOCCFG, 0x17]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FSCAL3, 0xE9]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FSCAL2, 0x2A]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FSCAL1, 0x00]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.FSCAL0, 0x1F]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.TEST1, 0x31]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.TEST0, 0x09]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.PATABLE0, 0x84]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.SYNC1, 0xA5]))
            self.__command(Command.UPDATE_REGISTER, bytes([Register.SYNC0, 0x5A]))

            response = self.__command(Command.GET_STATE)
            if response != b"OK":
                raise RileyLinkError("Rileylink state is not OK. Response returned: %s" % response)

        except RileyLinkError as rle:
            logging.error("Error while initializing rileylink radio: %s", rle)
            raise

    def get_packet(self, timeout=1.0):
        try:
            return self.__command(Command.GET_PACKET, struct.pack(">BL", 0, int(timeout * 1000)), timeout=float(timeout)+0.5, throw_on_timeout=False)
        except RileyLinkError as rle:
            logging.error("Error while receiving data: %s", rle)
            raise

    def send_and_receive_packet(self, packet, repeat_count, delay_ms, timeout_ms, retry_count, preamble_ext_ms):

        logging.debug("sending packet: %s" % packet.hex())
        try:
            return self.__command(Command.SEND_AND_LISTEN,
                                  struct.pack(">BBHBLBH",
                                              0,
                                              repeat_count,
                                              delay_ms,
                                              0,
                                              timeout_ms,
                                              retry_count,
                                              preamble_ext_ms)
                                              + packet,
                                  timeout=30)
        except RileyLinkError as rle:
            logging.error("Error while sending and receiving data: %s", rle)
            raise

    def send_packet(self, packet, repeat_count, delay_ms, preamble_extension_ms):
        try:
            result = self.__command(Command.SEND_PACKET, struct.pack(">BBHH", 0, repeat_count, delay_ms,
                                                                   preamble_extension_ms) + packet,
                                  timeout=30)
            return result
        except RileyLinkError as rle:
            logging.error("Error while sending data: %s", rle)
            raise

    def __command(self, command_type, command_data=None, timeout=2.0, throw_on_timeout=True):
        if command_data is None:
            data = bytes([1, command_type])
        else:
            data = bytes([len(command_data) + 1, command_type]) + command_data

        self.p.writeCharacteristic(self.data_handle, data, withResponse=True)

        if self.p.waitForNotifications(timeout):
            response = self.p.readCharacteristic(self.data_handle)
            if response is None or len(response) == 0:
                raise RileyLinkError("RileyLink returned no response")
            else:
                if response[0] == Response.COMMAND_SUCCESS:
                    return response[1:]
                elif response[0] == Response.COMMAND_INTERRUPTED:
                    logging.warning("A previous command was interrupted")
                    return response[1:]
                elif response[0] == Response.RX_TIMEOUT:
                    if throw_on_timeout:
                        raise RileyLinkError("Connection timed out while waiting for a response from the pod", response[0])
                else:
                    raise RileyLinkError("RileyLink returned error code: %02X. Additional response data: %s"
                                         % (response[0], response[1:]), response[0])
        else:
            if throw_on_timeout:
                raise RileyLinkError("Timed out while waiting for a response from RileyLink")
        return None

