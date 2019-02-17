#!/usr/bin/python3
import base64
import logging
import os
from decimal import *

import Crypto.Cipher
import simplejson as json
from flask import Flask, request

from podcomm.definitions import *
from podcomm.crc import crc8
from podcomm.packet import Packet
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.rileylink import RileyLink

app = Flask(__name__)


class RestApiException(Exception):
    def __init__(self, msg="Unknown"):
        self.error_message = msg

    def __str__(self):
        return self.error_message


def get_pod():
    return Pod.Load(POD_FILE)


def get_pdm():
    return Pdm(get_pod())


def respond_ok(d="OK"):
    return json.dumps({"success": True, "result": d})


def respond_error(msg="Unknown"):
    return json.dumps({"success": False, "error": msg})


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

        cipher = Crypto.Cipher.AES.new(key, Crypto.Cipher.AES.MODE_CBC, iv)
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
    except RestApiException as rae:
        logging.error("Authentication error: %s", rae)
        raise
    except Exception as e:
        logging.error("Error during verify_auth: %s", e)
        raise

@app.route("/omnipy/result")
def get_result():
    try:
        return respond_ok("%d.%d" % (API_VERSION_MAJOR, API_VERSION_MINOR))
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during result req: %s", e)
        return respond_error("Other error. Please check log files.")

@app.route("/omnipy/version")
def get_api_version():
    try:
        return respond_ok("%d.%d" % (API_VERSION_MAJOR, API_VERSION_MINOR))
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during version req: %s", e)
        return respond_error("Other error. Please check log files.")

@app.route("/omnipy/token")
def create_token():
    try:
        with open(TOKENS_FILE, "a+b") as tokens:
            token = bytes(os.urandom(16))
            tokens.write(token)
        return respond_ok(base64.b64encode(token))
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during create token: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/omnipy/pwcheck")
def check_password():
    try:
        verify_auth(request)

        return respond_ok()
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during check pwd: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/omnipy/takeover")
def take_over():
    try:
        verify_auth(request)

        pod = Pod()
        pod.lot = int(request.args.get('lot'))
        pod.tid = int(request.args.get('tid'))

        r = RileyLink()
        r.connect()
        r.init_radio()
        p = None
        while True:
            data = r.get_packet(30000)
            if data is not None and len(data) > 2:
                calc = crc8(data[2:-1])
                if data[-1] == calc:
                    p = Packet.from_data(data[2:-1])
                    break
        r.disconnect()

        if p is None:
            respond_error("No pdm packet detected")

        pod.address = p.address
        pod.Save(POD_FILE)
        return respond_ok(p.address)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during takeover: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/omnipy/parameters")
def set_pod_parameters():
    try:
        verify_auth(request)

        pod = get_pod()
        pod.lot = int(request.args.get('lot'))
        pod.tid = int(request.args.get('tid'))
        pod.address = int(request.args.get('address'))
        pod.nonceSeed = 0
        pod.lastNonce = None
        pod.packetSequence = 0
        pod.msgSequence = 0
        pod.Save()
        return respond_ok()
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during set pod params: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/omnipy/limits")
def set_limits():
    try:
        verify_auth(request)

        pod = get_pod()
        pod.maximumBolus = Decimal(request.args.get('maxbolus'))
        pod.maximumTempBasal = Decimal(request.args.get('maxbasal'))
        pod.Save()
        return respond_ok()
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during set limits: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/pdm/status")
def get_status():
    try:
        verify_auth(request)

        pdm = get_pdm()
        pdm.updatePodStatus()
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during get status: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/pdm/ack")
def acknowledge_alerts():
    try:
        verify_auth(request)
        mask = Decimal(request.args.get('alertmask'))
        pdm = get_pdm()
        pdm.acknowledge_alerts(mask)
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during acknowledging alerts: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/pdm/deactivate")
def deactivate_pod():
    try:
        verify_auth(request)
        pdm = get_pdm()
        pdm.deactivate_pod()
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during deactivation: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/pdm/bolus")
def bolus():
    try:
        verify_auth(request)

        pdm = get_pdm()
        amount = Decimal(request.args.get('amount'))
        pdm.bolus(amount, False)
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during bolus: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/pdm/cancelbolus")
def cancel_bolus():
    try:
        verify_auth(request)

        pdm = get_pdm()
        pdm.cancelBolus()
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during cancel bolus: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/pdm/settempbasal")
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
    except Exception as e:
        logging.error("Error during set temp basal: %s", e)
        return respond_error("Other error. Please check log files.")


@app.route("/pdm/canceltempbasal")
def cancel_temp_basal():
    try:
        verify_auth(request)

        pdm = get_pdm()
        pdm.cancelTempBasal()
        return respond_ok(pdm.pod.__dict__)
    except RestApiException as rae:
        return respond_error(str(rae))
    except Exception as e:
        logging.error("Error during cancel temp basal: %s", e)
        return respond_error("Other error. Please check log files.")


if __name__ == '__main__':
    if os.path.isfile(TOKENS_FILE):
        os.remove(TOKENS_FILE)
    if os.path.isfile(RESPONSE_FILE):
        os.remove(RESPONSE_FILE)
    app.run(host='0.0.0.0', port=4444)
