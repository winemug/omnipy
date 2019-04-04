from podcomm.protocol_common import PdmMessage, PdmRequest, PodMessage, PodResponse
from podcomm.protocol import *
from podcomm.nonce import Nonce
from podcomm.protocol_radio import PdmRadio, RadioPacket, RadioPacketType
from podcomm.crc import crc16, crc8
from tests.mock_radio import MockPacketRadio
from podcomm.pod import Pod


import time

pod = Pod()
pod.radio_address = 0x1f10fc49
radio = PdmRadio(0x1f10fc49, 0, 0)
pod.id_t = 381741
pod.id_lot = 44425

msg = request_status()
msg = radio.send_message_get_message(msg)
response_parse(msg, pod)
print(pod.__dict__)



