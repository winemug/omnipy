import serial
import struct
import time
from .packet_radio import PacketRadio, TxPower
from .definitions import *
from enum import IntEnum
from threading import Event
from .exceptions import PacketRadioError
from .manchester import ManchesterCodec
import simplejson as json

XGATT_BATTERYSERVICE_UUID = "180f"
XGATT_BATTERY_CHAR_UUID = "2a19"
RILEYLINK_SERVICE_UUID = "0235733b-99c5-4197-b856-69219c2a3845"
RILEYLINK_DATA_CHAR_UUID = "c842e849-5028-42e2-867c-016adada9155"
RILEYLINK_RESPONSE_CHAR_UUID = "6e6c7910-b89e-43a5-a0fe-50c5e2b81f4a"

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

def get_fw_reg_id(reg: str) -> int:
    reg_dict = {
    "SYNC1": 0,
    "SYNC0": 1,
    "PKTLEN": 2,
    "PKTCTRL1": 3,
    "PKTCTRL0": 4,
    "ADDR": 5,
    "CHANNR": 6,
    "FSCTRL1": 7,
    "FSCTRL0": 8,
    "FREQ2": 9,
    "FREQ1": 10,
    "FREQ0": 11,
    "MDMCFG4": 12,
    "MDMCFG3": 13,
    "MDMCFG2": 14,
    "MDMCFG1": 15,
    "MDMCFG0": 16,
    "DEVIATN": 17,
    "MCSM2": 18,
    "MCSM1": 19,
    "MCSM0": 20,
    "FOCCFG": 21,
    "BSCFG": 22,
    "AGCCTRL2": 23,
    "AGCCTRL1": 24,
    "AGCCTRL0": 25,
    "FREND1": 26,
    "FREND0": 27,
    "FSCAL3": 28,
    "FSCAL2": 29,
    "FSCAL1": 30,
    "FSCAL0": 31,
    "TEST2": None,
    "TEST1": 36,
    "TEST0": 37,
    "PA_TABLE7": None,
    "PA_TABLE6": None,
    "PA_TABLE5": None,
    "PA_TABLE4": None,
    "PA_TABLE3": None,
    "PA_TABLE2": None,
    "PA_TABLE1": None,
    "PA_TABLE0": 46
    }
    return reg_dict[reg]

class Encoding(IntEnum):
    NONE = 0
    MANCHESTER = 1
    FOURBSIXB = 2

# 0xC0 +10
# 0xC8 +7
# 0x84 +5
# 0x60 0
# 0x62 -1
# 0x2C -5
# 0x34 -10
# 0x1D -15
# 0x0E -20
# 0x12 -30

g_rl_address = None
g_rl_version = None
g_rl_v_major = None
g_rl_v_minor = None

class TIDongle(PacketRadio):
    def __init__(self):
        self.logger = getLogger()
        self.packet_logger = get_packet_logger()
        self.initialized = False
        self.manchester = ManchesterCodec()
        self.ser : serial.Serial = None

    def connect(self, force_initialize=False):
        if self.ser is None:
            self.ser = serial.Serial('/dev/ttyS0', baudrate=35600, bytesize=8, parity='N', stopbits=1,
                                xonxoff=0,
                                rtscts=0)
        if force_initialize:
            self.ser.flush()

    def disconnect(self, ignore_errors=True):
        self.ser.close()
        self.ser = None

    def get_info(self):
        return ""

    def init_radio(self, force_init=False):
        try:
            if force_init:
                self.initialized = False
                self.logger.debug("force initialize, resetting RL")
                #TODO: reset pin
                time.sleep(3)
                self.logger.debug("reconnecting")
            self._command(Command.RADIO_RESET_CONFIG)
            self._command(Command.SET_SW_ENCODING, bytes([Encoding.NONE]))
            self._command(Command.SET_PREAMBLE, bytes([0x66, 0x65]))

            with open("/home/pi/omnipy/cc1110.json", "r") as ocj:
                js = json.load(ocj)

            common_regs = js['common']
            for reg in common_regs:
                self._command(Command.UPDATE_REGISTER, bytes([get_fw_reg_id(reg), int(common_regs[reg], base=16)]))

            tx = js['tx']
            tx_mode = [0x01]
            for reg in tx:
                tx_mode.append(get_fw_reg_id(reg))
                tx_mode.append(int(tx[reg], base=16))
            tx_mode = bytes(tx_mode)
            self._command(Command.SET_MODE_REGISTERS, tx_mode)

            rx = js['rx']
            rx_mode = [0x02]
            for reg in rx:
                rx_mode.append(get_fw_reg_id(reg))
                rx_mode.append(int(rx[reg], base=16))
            rx_mode = bytes(rx_mode)
            self._command(Command.SET_MODE_REGISTERS, rx_mode)

            response = self._command(Command.GET_STATE)
            if response != b"OK":
                raise PacketRadioError("Rileylink state is not OK. Response returned: %s" % response)

            self.initialized = True

        except Exception as e:
            raise PacketRadioError("Error while initializing rileylink radio: %s", e)

    def tx_up(self):
        pass

    def tx_down(self):
        pass

    def set_tx_power(self, tx_power):
        pass

    def get_packet(self, timeout=5.0):
        try:
            self.connect()
            result = self._command(Command.GET_PACKET, struct.pack(">BL", 0, int(timeout * 1000)),
                                 timeout=float(timeout)+0.5)
            if result is not None:
                return result[0:2] + self.manchester.decode(result[2:])
            else:
                return None
        except Exception as e:
            raise PacketRadioError("Error while getting radio packet") from e

    def send_and_receive_packet(self, packet, repeat_count, delay_ms, timeout_ms, retry_count, preamble_ext_ms):
        try:
            self.connect()
            data = self.manchester.encode(packet)
            result = self._command(Command.SEND_AND_LISTEN,
                                  struct.pack(">BBHBLBH",
                                              0,
                                              repeat_count,
                                              delay_ms,
                                              0,
                                              timeout_ms,
                                              retry_count,
                                              preamble_ext_ms)
                                              + data,
                                  timeout=30)
            if result is not None:
                return result[0:2] + self.manchester.decode(result[2:])
            else:
                return None
        except Exception as e:
            raise PacketRadioError("Error while sending and receiving data") from e

    def send_packet(self, packet, repeat_count, delay_ms, preamble_extension_ms):
        try:
            self.connect()
            data = self.manchester.encode(packet)
            result = self._command(Command.SEND_PACKET, struct.pack(">BBHH", 0, repeat_count, delay_ms,
                                                                   preamble_extension_ms) + data,
                                  timeout=30)
            return result
        except Exception as e:
            raise PacketRadioError("Error while sending data") from e

    def _set_amp(self, index=None):
        pass

    def _command(self, command_type, command_data=None, timeout=10.0):
        try:
            self.connect()
            if command_data is None:
                data = bytes([1, command_type])
            else:
                data = bytes([len(command_data) + 1, command_type]) + command_data

            self.ser.write(data)
            self.ser.flush()

            response = None
            response_len = None
            self.ser.timeout = timeout
            x = self.ser.read(1)
            if len(x) > 0:
                response_len = x[0]
                if response_len > 0:
                    response = self.ser.read(response_len)

            if response_len is None:
                raise PacketRadioError("Timed out while waiting for a response from RileyLink")


            if response is None or len(response) == 0:
                raise PacketRadioError("RileyLink returned no response")
            else:
                if response[0] == Response.COMMAND_SUCCESS:
                    return response[1:]
                elif response[0] == Response.COMMAND_INTERRUPTED:
                    self.logger.warning("A previous command was interrupted")
                    return response[1:]
                elif response[0] == Response.RX_TIMEOUT:
                    return None
                else:
                    raise PacketRadioError("RileyLink returned error code: %02X. Additional response data: %s"
                                         % (response[0], response[1:]), response[0])
        except PacketRadioError:
            raise
        except Exception as e:
            raise PacketRadioError("Error executing command") from e
