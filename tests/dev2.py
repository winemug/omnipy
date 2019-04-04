from podcomm.protocol_common import PdmMessage, PdmRequest, PodMessage, PodResponse
from podcomm.protocol import *
from podcomm.nonce import Nonce
from podcomm.protocol_radio import PdmRadio, RadioPacket, RadioPacketType, TxPower
from podcomm.crc import crc16, crc8
from tests.mock_radio import MockPacketRadio
from podcomm.pod import Pod

import time

pod = Pod()
pod.radio_address = 0x1f010101
rd = PdmRadio(0x1f010101, 11, 11)
pod.id_t = 0x0007a75c
pod.id_lot = 0x0000ad89

nonce = Nonce(pod.id_lot, pod.id_t, None, 0)
#nonce.reset()
# msg = request_assign_address(pod.radio_address)
# rsp = rd.send_message_get_message(msg, ack_address_override=pod.radio_address, tx_power=TxPower.Lowest)
# response_parse(rsp, pod)
#
# msg = request_setup_pod(pod.id_lot, pod.id_t, pod.radio_address, 2019, 5, 28, 21, 8)
# rsp = rd.send_message_get_message(msg, ack_address_override=pod.radio_address)
# response_parse(rsp, pod)

# print(pod)
# exit(0)

#########################################

# msg = request_set_low_reservoir_alert(Decimal("30"))
# rsp = rd.send_message_get_message(msg)
# response_parse(rsp, pod)

msg = request_set_generic_alert(15, 15)
msg.set_nonce(nonce.getNext())
rsp = rd.send_message_get_message(msg)
sync_word = response_parse(rsp, pod)

nonce.sync(sync_word, msg.sequence)


rd.message_sequence = msg.sequence


msg = request_set_generic_alert(15, 15)
msg.set_nonce(nonce.getNext())
rsp = rd.send_message_get_message(msg)
response_parse(rsp, pod)


msg = request_purge_insulin(Decimal("2.60"))
msg.set_nonce(nonce.getNext())
rsp = rd.send_message_get_message(msg)
response_parse(rsp, pod)

#
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

time.sleep(15)

msg = request_status()
rsp = rd.send_message_get_message(msg)

print(pod)
exit(0)
