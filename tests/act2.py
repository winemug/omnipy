from podcomm.protocol_common import PdmMessage, PdmRequest, PodMessage, PodResponse
from podcomm.protocol import *
from podcomm.nonce import Nonce
from podcomm.protocol_radio import PdmRadio, RadioPacket, RadioPacketType, TxPower
from podcomm.crc import crc16, crc8
from tests.mock_radio import MockPacketRadio
from podcomm.pod import Pod

import time


pod = None
try:
    pod = pod.Load("/home/ba/newpod2.json", "/home/ba/newpod2.json.log")
except:
    pass

if pod is None:
    pod = Pod()
    pod.path = "/home/ba/newpod2.json"
    pod.log_file_path = "/home/ba/newpod2.json.log"


req_address = 0x1f000015
radio = PdmRadio(0xffffffff)

msg = request_assign_address(req_address)
rsp = radio.send_message_get_message(msg, ack_address_override=req_address, tx_power=TxPower.Lowest)
response_parse(rsp, pod)
pod.Save("/home/ba/newpod1.json")

radio.message_sequence = 1
msg = request_setup_pod(pod.id_lot, pod.id_t, pod.radio_address, 2019, 4, 3, 21, 35)
rsp = radio.send_message_get_message(msg, ack_address_override=pod.radio_address)
response_parse(rsp, pod)
pod.Save()

parse_version_response(bytearray.fromhex("02080002080002020000ab0f000e8246931f000011"), pod)
parse_version_response(bytearray.fromhex("13881008340a5002080002080002030000ab0f000e82461f000011"), pod)

radio.stop()

radio = PdmRadio(req_address)
nonce = Nonce(pod.id_lot, pod.id_t, None, 0)

def nonce_msg():
    msg.set_nonce(nonce.getNext())
    pod.nonce_syncword = None
    rsp = radio.send_message_get_message(msg)
    response_parse(rsp, pod)
    if pod.nonce_syncword is not None:
        nonce.sync(syncWord=pod.nonce_syncword, msgSequence=msg.sequence)
        msg.set_nonce(nonce.getNext())
        radio.message_sequence = msg.sequence
        rsp = radio.send_message_get_message(msg)
        response_parse(rsp, pod)
        if pod.nonce_syncword is not None:
            raise Exception()

    pod.Save()

msg = request_set_low_reservoir_alert(Decimal("30"))
nonce_msg()


msg = request_set_generic_alert(15, 15)
nonce_msg()


msg = request_purge_insulin(Decimal("2.60"))
nonce_msg()

time.sleep(55)

msg = request_set_pod_expiry_alert((24 * 60 * 2) + (20 * 60))
nonce_msg()

schedule = [Decimal("1.0")*48]
msg = request_set_basal_schedule(schedule, 0, 0, 0)
nonce_msg()

msg = request_purge_insulin(Decimal("0.50"))
nonce_msg()

msg = request_status()
rsp = radio.send_message_get_message(msg)
response_parse(rsp, pod)
pod.Save()


time.sleep(15)

msg = request_status()
rsp = radio.send_message_get_message(msg)
pod.Save()

exit(0)
