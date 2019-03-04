#!/usr/bin/python3
import base64
import os
from decimal import *

from Crypto.Cipher import AES
import simplejson as json
from flask import Flask, request, send_from_directory
from datetime import datetime
from podcomm.crc import crc8
from podcomm.packet import Packet
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.rileylink import RileyLink
from podcomm.definitions import *


app = Flask(__name__, static_url_path="/")
configureLogging()
logger = getLogger()


class RestApiException(Exception):
    def __init__(self, msg="Unknown"):
        self.error_message = msg

    def __str__(self):
        return self.error_message


def get_pod() -> Pod:
    return Pod.Load(POD_FILE + POD_FILE_SUFFIX, POD_FILE + POD_LOG_SUFFIX)


def get_pdm() -> Pdm:
    return Pdm(get_pod())


def archive_pod():
    archive_suffix = datetime.utcnow().strftime("_%Y%m%d_%H%M%S")
    if os.path.isfile(POD_FILE + POD_FILE_SUFFIX):
        os.rename(POD_FILE + POD_FILE_SUFFIX, POD_FILE + archive_suffix + POD_FILE_SUFFIX)
    if os.path.isfile(POD_FILE + POD_LOG_SUFFIX):
        os.rename(POD_FILE + POD_LOG_SUFFIX, POD_FILE + archive_suffix + POD_LOG_SUFFIX)


def respond_ok(result):
    return json.dumps({"success": True, "result": result}, indent=4, sort_keys=True)


def respond_error(msg):
    return json.dumps({"success": False, "result": {"error": msg}}, indent=4, sort_keys=True)


def verify_auth(request_obj):
    try:
        i = request_obj.args.get("i")
        a = request_obj.args.get("auth")
        if i is None or a is None:
            raise RestApiException("Authentication failed")

        iv = base64.b64decode(i)
        auth = base64.b64decode(a)

        with open(KEY_FILE, "rb") as keyfile:
            key = keyfile.read(32)

        cipher = AES.new(key, AES.MODE_CBC, iv)
        token = cipher.decrypt(auth)

        with open(TOKENS_FILE, "a+b") as tokens:
            tokens.seek(0, 0)
            found = False
            while True:
                read_token = tokens.read(16)
                if len(read_token) < 16:
                    break
                if read_token == token:
                    found = True
                    break

            if found:
                while True:
                    read_token = tokens.read(16)
                    if len(read_token) < 16:
                        tokens.seek(-16 - len(read_token), 1)
                        break
                    tokens.seek(-32, 1)
                    tokens.write(read_token)
                    tokens.seek(16, 1)
                tokens.truncate()

        if not found:
            raise RestApiException("Invalid authentication token")
    except RestApiException:
        logger.exception("Authentication error")
        raise
    except Exception:
        logger.exception("Error during verify_auth")
        raise


@app.route("/")
def main_page():
    return app.send_static_file("omnipy.html")


@app.route('/content/<path:path>')
def send_content(path):
    return send_from_directory("static", path)


@app.route(REST_URL_GET_VERSION)
def get_api_version():
    try:
        return respond_ok({"version_major": API_VERSION_MAJOR, "version_minor": API_VERSION_MINOR})
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during version request")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_TOKEN)
def create_token():
    try:
        with open(TOKENS_FILE, "a+b") as tokens:
            token = bytes(os.urandom(16))
            tokens.write(token)
        return respond_ok({"token": base64.b64encode(token)})
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during create token")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_CHECK_PASSWORD)
def check_password():
    try:
        verify_auth(request)

        return respond_ok({})
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during check pwd")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_GET_PDM_ADDRESS)
def get_pdm_address():
    r = RileyLink()
    try:
        verify_auth(request)
        while True:
            timeout = 30000
            if request.args.get('timeout') is not None:
                timeout = int(request.args.get('timeout')) * 1000
                if timeout > 30000:
                    raise RestApiException("Timeout cannot be more than 30 seconds")

            data = r.get_packet(timeout)
            if data is None:
                p = None
                break

            if data is not None and len(data) > 2:
                calc = crc8(data[2:-1])
                if data[-1] == calc:
                    p = Packet.from_data(data[2:-1])
                    break
        if p is None:
            respond_error("No pdm packet detected")

        return respond_ok({"radio_address": p.address})
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error while trying to read radio_address")
        return respond_error("Other error. Please check log files.")
    finally:
        r.disconnect(ignore_errors=True)


@app.route(REST_URL_NEW_POD)
def new_pod():
    try:
        verify_auth(request)

        pod = Pod()

        if request.args.get('id_lot') is not None:
            pod.id_lot = int(request.args.get('id_lot'))
        if request.args.get('id_t') is not None:
            pod.id_t = int(request.args.get('id_t'))
        if request.args.get('radio_address') is not None:
            pod.radio_address = int(request.args.get('radio_address'))

        archive_pod()
        pod.Save(POD_FILE + POD_FILE_SUFFIX)
        return respond_ok({})
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error while creating new pod")
        return respond_error("Other error. Please check log files.")


def _int_parameter(obj, parameter):
    if request.args.get(parameter) is not None:
        obj.__dict__[parameter] = int(request.args.get(parameter))
        return True
    return False


def _float_parameter(obj, parameter):
    if request.args.get(parameter) is not None:
        obj.__dict__[parameter] = float(request.args.get(parameter))
        return True
    return False


def _bool_parameter(obj, parameter):
    if request.args.get(parameter) is not None:
        val = str(request.args.get(parameter))
        bval = False
        if val == "1" or val.capitalize() == "TRUE":
            bval = True
        obj.__dict__[parameter] = bval
        return True
    return False


@app.route(REST_URL_SET_POD_PARAMETERS)
def set_pod_parameters():
    try:
        verify_auth(request)

        pod = get_pod()
        reset_nonce = False
        if _int_parameter(pod, "id_lot"):
            reset_nonce = True
        if _int_parameter(pod, "id_t"):
            reset_nonce = True

        if reset_nonce:
            pod.nonce_last = None
            pod.nonce_seed = 0

        if _int_parameter(pod, "radio_address"):
            pod.radio_packet_sequence = 0
            pod.radio_message_sequence = 0

        _float_parameter(pod, "var_utc_offset")
        _float_parameter(pod, "var_maximum_bolus")
        _float_parameter(pod, "var_maximum_temp_basal_rate")
        _float_parameter(pod, "var_alert_low_reservoir")
        _int_parameter(pod, "var_alert_replace_pod")
        _bool_parameter(pod, "var_notify_bolus_start")
        _bool_parameter(pod, "var_notify_bolus_cancel")
        _bool_parameter(pod, "var_notify_temp_basal_set")
        _bool_parameter(pod, "var_notify_temp_basal_cancel")
        _bool_parameter(pod, "var_notify_basal_schedule_change")

        pod.Save()
        return respond_ok({})
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during set pod parameters")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_RL_INFO)
def get_rl_info():
    try:
        verify_auth(request)

        r = RileyLink()
        info = r.get_info()
        return respond_ok(info)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.error("Error during get RL info")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_STATUS)
def get_status():
    try:
        verify_auth(request)

        t = request.args.get('type')
        if t is not None:
            req_type = int(t)
        else:
            req_type = 0

        pdm = get_pdm()
        pdm.updatePodStatus(req_type)
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during get status")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_ACK_ALERTS)
def acknowledge_alerts():
    try:
        verify_auth(request)

        mask = Decimal(request.args.get('alertmask'))
        pdm = get_pdm()
        pdm.acknowledge_alerts(mask)
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during acknowledging alerts")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_DEACTIVATE_POD)
def deactivate_pod():
    try:
        verify_auth(request)
        pdm = get_pdm()
        pdm.deactivate_pod()
        archive_pod()
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during deactivation")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_BOLUS)
def bolus():
    try:
        verify_auth(request)

        pdm = get_pdm()
        amount = Decimal(request.args.get('amount'))
        pdm.bolus(amount)
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during bolus")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_CANCEL_BOLUS)
def cancel_bolus():
    try:
        verify_auth(request)

        pdm = get_pdm()
        pdm.cancelBolus()
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during cancel bolus")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_SET_TEMP_BASAL)
def set_temp_basal():
    try:
        verify_auth(request)

        pdm = get_pdm()
        amount = Decimal(request.args.get('amount'))
        hours = Decimal(request.args.get('hours'))
        pdm.setTempBasal(amount, hours, False)
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during set temp basal")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_CANCEL_TEMP_BASAL)
def cancel_temp_basal():
    try:
        verify_auth(request)

        pdm = get_pdm()
        pdm.cancelTempBasal()
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during cancel temp basal")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_PDM_BUSY)
def is_pdm_busy():
    try:
        pdm = get_pdm()
        result = pdm.is_busy()
        return respond_ok({"busy": result})
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during cancel temp basal")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_OMNIPY_SHUTDOWN)
def shutdown():
    try:
        pdm = get_pdm()
        if pdm.is_busy():
            return respond_error("cannot shutdown while pdm is busy")
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during shutdown")
        return respond_error("Other error. Please check log files.")


@app.route(REST_URL_OMNIPY_RESTART)
def restart():
    try:
        pdm = get_pdm()
        if pdm.is_busy():
            return respond_error("cannot restart while pdm is busy")
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception:
        logger.exception("Error during restart")
        return respond_error("Other error. Please check log files.")


if __name__ == '__main__':
    try:
        logger.info("Rest api is starting")
        if os.path.isfile(TOKENS_FILE):
            logger.debug("removing tokens from previous session")
            os.remove(TOKENS_FILE)
        if os.path.isfile(RESPONSE_FILE):
            logger.debug("removing response queue from previous session")
            os.remove(RESPONSE_FILE)
    except IOError as ioe:
        logger.warning("Error while removing stale files: %s", exc_info=ioe)

    try:
        os.system("sudo systemctl restart systemd-timesyncd")
        os.system("sudo systemctl daemon-reload")
    except:
        logger.exception("Error while reloading timesync daemon")

    try:
        app.run(host='0.0.0.0', port=4444)
    except:
        logger.exception("Error while running rest api, exiting")
        raise
