#!/usr/bin/python3
import logging
import os
import sys
import simplejson as json
from flask import Flask, request, g
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.packet import Packet
from podcomm.rileylink import RileyLink
from podcomm.crc import crc8
from decimal import *
import base64
from Crypto.Cipher import AES

TOKENS_FILE = ".tokens"
KEY_FILE = ".key"

app = Flask(__name__)

def get_pdm():
    pod = Pod.Load("pod.json")
    pdm = Pdm(pod)
    return pdm

def respond_ok(d = {}):
    return json.dumps({ "success": True, "result": d})

def respond_error(msg = "Unknown"):
    return json.dumps({ "success": False, "error": msg})

def verify_auth(request):
    i = request.args.get("i")
    a = request.args.get("auth")
    if i is None or a is None:
        raise ValueError("Authentication failed")
    
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
        raise ValueError("Invalid authentication token")

@app.route("/omnipy/token")
def create_token():
    try:
        with open(TOKENS_FILE, "a+b") as tokens:
            token = bytes(os.urandom(16))
            tokens.write(token)
        return respond_ok(base64.b64encode(token))
    except Exception as e:
        return respond_error(msg = str(e))

@app.route("/omnipy/pwcheck")
def check_password():
    try:
        verify_auth(request)
        return respond_ok()
    except Exception as e:
        return respond_error(msg = str(e))

@app.route("/omnipy/takeover")
def takeover():
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
                    p = Packet(0, data[2:-1])
                    break
        r.disconnect()

        if p is None:
            respond_error("No pdm packet detected")

        pod.address = p.address
        pod.Save("pod.json")
        return respond_ok({"address": p.address})
    except Exception as e:
        return respond_error(msg = str(e))

@app.route("/pdm/status")
def get_status():
    try:
        verify_auth(request)
        pdm = get_pdm()
        pdm.updatePodStatus()
        return respond_ok(pdm.pod.__dict__)
    except Exception as e:
        return respond_error(msg = str(e))

@app.route("/pdm/bolus")
def bolus():
    try:
        verify_auth(request)

        pdm = get_pdm()
        amount = Decimal(request.args.get('amount'))
        pdm.bolus(amount, False)
        return respond_ok(pdm.pod.__dict__)
    except Exception as e:
        return respond_error(msg = str(e))

@app.route("/pdm/cancelbolus")
def cancelbolus():
    try:
        verify_auth(request)

        pdm = get_pdm()
        pdm.cancelbolus()
        return respond_ok(pdm.pod.__dict__)
    except Exception as e:
        return respond_error(msg = str(e))

@app.route("/pdm/tempbasal")
def tempbasal():
    try:
        verify_auth(request)
        pdm = get_pdm()
        amount = Decimal(request.args.get('amount'))
        hours = Decimal(request.args.get('hours'))
        pdm.setTempBasal(amount, hours, False)
        return respond_ok(pdm.pod.__dict__)
    except Exception as e:
        return respond_error(msg = str(e))

@app.route("/pdm/canceltempbasal")
def canceltempbasal():
    try:
        verify_auth(request)
        pdm = get_pdm()
        pdm.cancelTempBasal()
        return respond_ok(pdm.pod.__dict__)
    except Exception as e:
        return respond_error(msg = str(e))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4444)
