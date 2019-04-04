from podcomm.protocol_common import PdmMessage, PdmRequest, PodMessage, PodResponse
from podcomm.protocol import *
from podcomm.nonce import Nonce
from podcomm.protocol_radio import PdmRadio, RadioPacket, RadioPacketType, TxPower
from podcomm.crc import crc16, crc8
from tests.mock_radio import MockPacketRadio
from podcomm.pod import Pod

import time

pod = Pod()
mock_radio = MockPacketRadio()

req_address = 0x1f000010
radio = PdmRadio(0xffffffff, packet_radio=mock_radio)

rsp = PodMessage()
body = bytearray.fromhex("020700")
body += bytearray.fromhex("020700")
body += bytearray.fromhex("0202")
body += bytearray.fromhex("00001555") #lot
body += bytearray.fromhex("00012223") #tid
body += bytearray.fromhex("ff")
body += bytearray.fromhex("1f000010")

rsp.add_part(PodResponse.VersionInfo, body)
mock_radio.add_response(rsp, 0xffffffff, 0xffffffff, False)

msg = request_assign_address(req_address)
rsp = radio.send_message_get_message(msg, ack_address_override=req_address, tx_power=TxPower.Lowest)
response_parse(rsp, pod)


rsp = PodMessage()
body = bytearray.fromhex("01020304050607")
body += bytearray.fromhex("020700")
body += bytearray.fromhex("020700")
body += bytearray.fromhex("0202")
body += bytearray.fromhex("00001555") #lot
body += bytearray.fromhex("00012223") #tid
rsp.add_part(PodResponse.VersionInfo, body)
mock_radio.add_response(rsp, 0xffffffff, 0xffffffff, False)


msg = request_setup_pod(pod.id_lot, pod.id_t, pod.radio_address, 2019, 5, 30, 16, 0)
rsp = radio.send_message_get_message(msg, ack_address_override=pod.radio_address)
response_parse(rsp, pod)

radio = PdmRadio(req_address, packet_radio=mock_radio)
nonce = Nonce(pod.id_lot, pod.id_t, None, 0)

msg = request_set_low_reservoir_alert(Decimal("30"))
msg.set_nonce(nonce.getNext())
rsp = radio.send_message_get_message(msg)
response_parse(rsp, pod)


msg = request_set_generic_alert(15, 15)
msg.set_nonce(nonce.getNext())
rsp = radio.send_message_get_message(msg)
sync_word = response_parse(rsp, pod)


msg = request_purge_insulin(Decimal("2.60"))
msg.set_nonce(nonce.getNext())
rsp = radio.send_message_get_message(msg)
response_parse(rsp, pod)

time.sleep(55)

# pm = request_set_pod_expiry_alert((24 * 60 * 2) + (20 * 60))
# rsp = rd.send_message_get_message(msg)
# response_parse(rsp, pod)
#
# schedule = [Decimal("1.0")*48]
# pm = request_set_basal_schedule(schedule, 0, 0, 0)
# rsp = rd.send_message_get_message(msg)
# response_parse(rsp, pod)
#
# pm = request_purge_insulin(Decimal("0.50"))
# rsp = rd.send_message_get_message(msg)
# response_parse(rsp, pod)
#
# pm = request_status()
# rsp = rd.send_message_get_message(msg)
# response_parse(rsp, pod)
#
#
# time.sleep(15)
#
# msg = request_status()
# rsp = rd.send_message_get_message(msg)

exit(0)
