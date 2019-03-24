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


class PodMessage:
    def __init__(self):
        self.address = None
        self.sequence = None
        self.expect_critical_followup = False
        self.body_length = 0
        self.body = None

    def add_packet_data(self, data):
        t = data[0] >> 5
        if t == 7:
            self.address = struct.unpack(">I", data[1:5])[0]
            self.sequence = (data[6] >> 2) & 0x0f
            self.expect_critical_followup = (data[6] & 0x80) > 0
            self.body_length = ((data[6] & 0x03) << 8) | data[11]
            self.body = data[8:]
        elif t == 4:
            self.body += data[1:]
        else:
            raise ProtocolError("Packet type invalid")

        return self.body_length == len(self.body) + 2

class PdmMessage:
    def __init__(self, cmd_type, cmd_body):
        self.parts = []
        self.add_part(cmd_type, cmd_body)

    def get_packets(self, message_address,
                    message_sequence,
                    packet_address,
                    first_packet_sequence,
                    expect_critical_follow_up=False):

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
        packets = []
        while(index < total_body_len):
            packet_data = struct.pack(">I", packet_address)
            seq_byte = sequence

            if first_packet:
                first_packet = False
                seq_byte |= 0xa0
            else:
                seq_byte |= 0x80

            packet_data += bytes([seq_byte])
            to_write = min(31, total_body_len - index)
            packet_data += message_body[index:index+to_write]
            packet_data += bytes([crc8(packet_data)])
            packets.append(packet_data)
            index += to_write
            sequence = (sequence + 2) % 32

        return packets

    def add_part(self, cmd_type, cmd_body):
        part_tuple = cmd_type, cmd_body, None
        self.parts.append(part_tuple)

    def set_nonce(self, nonce):
        cmd_type, cmd_body, _ = self.parts[0]
        self.parts[0] = cmd_type, cmd_body, nonce


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
