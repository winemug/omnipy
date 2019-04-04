from podcomm.protocol_common import PdmMessage, PdmRequest, PodMessage, PodResponse
from podcomm.protocol import *
from podcomm.nonce import Nonce
from podcomm.protocol_radio import PdmRadio, RadioPacket, RadioPacketType, TxPower
from podcomm.crc import crc16, crc8
from tests.mock_radio import MockPacketRadio
from podcomm.pod import Pod

import time

def skip_ack(packet : RadioPacket):
    if packet.type == RadioPacketType.ACK:
        return None
    else:
        return packet

path = "data/bbe.json"
log_path = "data/bbe.log"
pod = None
try:
    pod = Pod.Load(path)
except:
    pass

if pod is None:
    pod = Pod()
    pod.path = path
    pod.log_file_path = log_path
    pod.id_lot = 44147
    pod.id_t = 1100256
    pod.radio_address = 0x1f0e89f0
    pod.Save()

mock_radio = MockPacketRadio(send_callback=skip_ack, allow_connect=True, allow_listen=True)
radio = PdmRadio(pod.radio_address, packet_radio=mock_radio,
                 msg_sequence=pod.radio_message_sequence, pkt_sequence=pod.radio_packet_sequence)

request = request_status()
response = radio.send_message_get_message(request)
response_parse(response, pod)

radio.radio_ready.wait()
time.sleep(30)

#radio.packet_sequence = (radio.packet_sequence - 1) % 32
#radio.message_sequence = (radio.message_sequence - 1) % 16

request = request_status()
response = radio.send_message_get_message(request)
response_parse(response, pod)

radio.radio_ready.wait()
time.sleep(90)

radio.packet_sequence = 0
radio.message_sequence = 0

mock_radio.send_callback = None

request = request_status()
response = radio.send_message_get_message(request)
response_parse(response, pod)

request = request_status()
response = radio.send_message_get_message(request)
response_parse(response, pod)

radio.stop()

pod.radio_packet_sequence = radio.packet_sequence
pod.radio_message_sequence = radio.message_sequence
pod.Save()