from podcomm.exceptions import PdmError, ProtocolError
from enum import IntEnum
from podcomm.crc import crc8, crc16
import struct

class PdmRequest(IntEnum):
    SetupPod = 0x03
    AssignAddress = 0x07
    Status = 0x0e
    AcknowledgeAlerts = 0x11
    BasalSchedule = 0x13
    TempBasalSchedule = 0x16
    BolusSchedule = 0x17
    ConfigureAlerts = 0x19
    InsulinSchedule = 0x1a
    DeactivatePod = 0x1c
    CancelDelivery = 0x1f


class PodResponse(IntEnum):
    VersionInfo = 0x01
    DetailInfo = 0x02
    BadNonce = 0x06
    Status = 0x1d

class RadioPacketType(IntEnum):
    UN0 = 0b00000000,
    UN1 = 0b00100000,
    ACK = 0b01000000,
    UN3 = 0b01100000,
    CON = 0b10000000,
    PDM = 0b10100000,
    UN6 = 0b11000000,
    POD = 0b11100000

class RadioPacket:
    def __init__(self, address, type, sequence, body):
        self.address = address
        self.type = type
        self.sequence = sequence % 32
        self.body = body

    @staticmethod
    def parse(data):
        if len(data) < 5:
            raise ProtocolError("Packet length too small")

        crc = data[-1]
        crc_computed = crc8(data[:-1])
        if crc != crc_computed:
            raise ProtocolError("Packet crc error")

        address = struct.unpack(">I", data[0:4])[0]

        type = RadioPacketType(data[4] & 0b11100000)
        sequence = data[4] & 0b00011111

        body = data[5:-1]
        return RadioPacket(address, type, sequence, body)

    def with_sequence(self, sequence):
        self.sequence = sequence
        return self

    def get_data(self):
        data = struct.pack(">I", self.address)
        data += bytes([self.type | self.sequence ])
        data += self.body
        data +=  bytes([crc8(data)])
        return data

    def __str__(self):
            return "Packet Addr: 0x%08x Type: %s Seq: 0x%02x Body: %s" % (self.address, self.type, self.sequence, self.body.hex())



class PodMessage:
    def __init__(self):
        self.address = None
        self.sequence = None
        self.expect_critical_followup = False
        self.body_length = 0
        self.body = None
        self.body_prefix = None
        self.parts = []

    def add_radio_packet(self, radio_packet):
        if radio_packet.type == RadioPacketType.POD:
            self.address = struct.unpack(">I", radio_packet.body[0:4])[0]
            self.sequence = (radio_packet.body[4] >> 2) & 0x0f
            self.expect_critical_followup = (radio_packet.body[4] & 0x80) > 0
            self.body_length = ((radio_packet.body[4] & 0x03) << 8) | radio_packet.body[5]
            self.body_prefix = radio_packet.body[:6]
            self.body = radio_packet.body[6:]
        elif radio_packet.type == RadioPacketType.CON:
            self.body += radio_packet.body
        else:
            raise ProtocolError("Packet type invalid")

        if self.body_length == len(self.body) - 2:
            crc = struct.unpack(">H", self.body[-2:])[0]
            crc_calculated = crc16(self.body_prefix + self.body[:-2])
            if crc == crc_calculated:
                self.body = self.body[:-2]

                bi = 0
                while bi < len(self.body):
                    response_type = self.body[bi]
                    if response_type == 0x1d:
                        response_len = len(self.body) - bi - 1
                        bi += 1
                    else:
                        response_len = self.body[bi+1]
                        bi += 2

                    if bi+response_len > len(self.body):
                        raise ProtocolError("Error in message format")

                    response_body = self.body[bi:bi+response_len]
                    self.parts.append((response_type, response_body))
                    bi += response_len
                return True
            else:
                raise ProtocolError("Message crc error")
        else:
            return False

    def __str__(self):
        s = "Pod Address: 0x%8X Sequence: %s Critical Follow-up: %s\n" % ( self.address,
                                                                    self.sequence,
                                                                    self.expect_critical_followup)

        for r_type, r_body in self.parts:
            s += "Response: %02x Body: %s\n" % (r_type, r_body.hex())
        return s


class PdmMessage:
    def __init__(self, cmd_type, cmd_body):
        self.parts = []
        self.add_part(cmd_type, cmd_body)
        self.message_str_prefix = "\n"

    def get_radio_packets(self, message_address,
                    message_sequence,
                    packet_address,
                    first_packet_sequence,
                    expect_critical_follow_up=False):

        self.message_str_prefix = "Pdm Address: 0x%08X Sequence: %s Critical Follow-up: %s\n" % (
                                    message_address, message_sequence, expect_critical_follow_up)
        message_body_len = 0
        for _, cmd_body, nonce in self.parts:
            message_body_len += len(cmd_body) + 2
            if nonce is not None:
                message_body_len += 4

        if expect_critical_follow_up:
            b0 = 0x80
        else:
            b0 = 0x00

        b0 |= (message_sequence << 2)
        b0 |= (message_body_len >> 8) & 0x03
        b1 = message_body_len & 0xff

        message_body = struct.pack(">I", message_address)
        message_body +=  bytes([b0, b1])
        for cmd_type, cmd_body, nonce in self.parts:
            if nonce is None:
                message_body += bytes([cmd_type, len(cmd_body)])
            else:
                message_body += bytes([cmd_type, len(cmd_body) + 4])
                message_body += struct.pack(">I", nonce)
            message_body += cmd_body

        crc_calculated = crc16(message_body)
        x = struct.pack(">H", crc_calculated)
        message_body += x

        index = 0
        first_packet = True
        sequence = first_packet_sequence
        total_body_len = len(message_body)
        radio_packets = []
        while(index < total_body_len):
            to_write = min(31, total_body_len - index)
            packet_body = message_body[index:index+to_write]

            radio_packets.append(RadioPacket(packet_address,
                                             RadioPacketType.PDM if first_packet else RadioPacketType.CON,
                                             sequence,
                                             packet_body))
            first_packet = False
            index += to_write
            sequence = (sequence + 2) % 32

        return radio_packets

    def add_part(self, cmd_type, cmd_body):
        part_tuple = cmd_type, cmd_body, None
        self.parts.append(part_tuple)

    def set_nonce(self, nonce):
        cmd_type, cmd_body, _ = self.parts[0]
        self.parts[0] = cmd_type, cmd_body, nonce

    def __str__(self):
        s = self.message_str_prefix
        for cmd_type, cmd_body, nonce in self.parts:
            if nonce is None:
                s += "Command: %02x Body: %s\n" % (cmd_type, cmd_body.hex())
            else:
                s += "Command: %02x Body: %s Nonce: %s\n" % (cmd_type, cmd_body.hex(), nonce.hex())
        return s


def alert_configuration_message_body(alert_bit, activate, trigger_auto_off, duration_minutes, beep_repeat_type, beep_type,
                     alert_after_minutes=None, alert_after_reservoir=None, trigger_reservoir=False):
    if alert_after_minutes is None:
        if alert_after_reservoir is None:
            raise PdmError("Either alert_after_minutes or alert_after_reservoir must be set")
        elif not trigger_reservoir:
            raise PdmError("Trigger insulin_reservoir must be True if alert_after_reservoir is to be set")
    else:
        if alert_after_reservoir is not None:
            raise PdmError("Only one of alert_after_minutes or alert_after_reservoir must be set")
        elif trigger_reservoir:
            raise PdmError("Trigger insulin_reservoir must be False if alert_after_minutes is to be set")

    if duration_minutes > 0x1FF:
        raise PdmError("Alert duration in minutes cannot be more than %d" % 0x1ff)
    elif duration_minutes < 0:
        raise PdmError("Invalid alert duration value")

    if alert_after_minutes is not None and alert_after_minutes > 4800:
        raise PdmError("Alert cannot be set beyond 80 hours")
    if alert_after_minutes is not None and alert_after_minutes < 0:
        raise PdmError("Invalid value for alert_after_minutes")

    if alert_after_reservoir is not None and alert_after_reservoir > 50:
        raise PdmError("Alert cannot be set for more than 50 units")
    if alert_after_reservoir is not None and alert_after_reservoir < 0:
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

    if alert_after_reservoir is not None:
        reservoir_limit = int(alert_after_reservoir * 10)
        b2 = reservoir_limit >> 8
        b3 = reservoir_limit & 0x00ff
    elif alert_after_minutes is not None:
        b2 = alert_after_minutes >> 8
        b3 = alert_after_minutes & 0x00ff
    else:
        raise PdmError("Incorrect alert configuration requested")

    return bytes([b0, b1, b2, b3, beep_repeat_type, beep_type])
