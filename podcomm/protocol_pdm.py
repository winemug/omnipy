from podcomm.definitions import OMNIPY_LOGGER
from podcomm.pod import POD_NONCE_SYNCWORD
from podcomm.protocol import response_parse, PdmError, request_status
import logging


def update_status(pod, radio, update_type=0):
    logger = logging.getLogger(OMNIPY_LOGGER)
    try:
        logger.info("Updating pod status, request type %d" % update_type)
        pod.last_command = {"command": "STATUS", "type": update_type, "success": False}
        request = request_status(update_type)
        return _send_request(pod, radio, request)
    except Exception:
        raise
    finally:
        pod._savePod()


def _send_request(pod, radio, request, nonce=None, double_take=False,
                 expect_critical_follow_up=False):
    logger = logging.getLogger(OMNIPY_LOGGER)
    if nonce is not None:
        request.set_nonce(nonce.getNext())
        pod.data[POD_NONCE_SYNCWORD] = None

    response, rssi = radio.send_message_get_message(request, double_take=double_take,
                                                         expect_critical_follow_up=expect_critical_follow_up)
    response_parse(response, pod)

    if nonce is not None and pod.data[POD_NONCE_SYNCWORD] is not None:
        logger.info("Nonce resync requested")
        nonce.sync(pod.data[POD_NONCE_SYNCWORD], request.sequence)
        request.set_nonce(nonce.getNext())
        pod.data[POD_NONCE_SYNCWORD] = None
        radio.message_sequence = request.sequence
        response = radio.send_message_get_message(request, double_take=double_take,
                                                             expect_critical_follow_up=expect_critical_follow_up)
        response_parse(response, pod)
        if pod.nonce_syncword is not None:
            nonce.get_nonce().reset()
            raise PdmError("Nonce sync failed")

    return rssi