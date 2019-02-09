#!/usr/bin/python3
import sys
import simplejson as json
from flask import Flask, request
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.packet import Packet
from podcomm.rileylink import RileyLink
from podcomm.crc import crc8
from Decimal import *

app = Flask(__name__)

def get_pdm():
    pod = Pod.Load("pod.json")
    pdm = Pdm(pod)
    return pdm

def respond_ok(success, d = {}):
    return json.dumps({ "success": True, "result:": d})

def respond_error(msg = "Unknown"):
    return json.dumps({ "success": False, "error:": msg})

@app.route("/pdm/status")
def get_status():
    try:
        pdm = get_pdm()
        pdm.updatePodStatus()
        return respond(True, pdm.pod.__dict__)
    except:
        return respond_error(msg = sys.exc_info()[0])

@app.route("/pdm/newpod")
def grab_pod():
    try:
        pod = Pod()
        pod.lot = request.args.get('lot')
        pod.tid = request.args.get('tid')

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
    except:
        return respond_error(msg = sys.exc_info()[0])

@app.route("/pdm/bolus")
def bolus():
    try:
        pdm = get_pdm()
        amount = Decimal(request.args.get('amount'))
        pdm.bolus(amount, False)
        return respond(True, pdm.pod.__dict__)
    except:
        return respond_error(msg = sys.exc_info()[0])

@app.route("/pdm/cancelbolus")
def cancelbolus():
    try:
        pdm = get_pdm()
        pdm.cancelbolus()
        return respond(True, pdm.pod.__dict__)
    except:
        return respond_error(msg = sys.exc_info()[0])

@app.route("/pdm/tempbasal")
def tempbasal():
    try:
        pdm = get_pdm()
        amount = Decimal(request.args.get('amount'))
        hours = Decimal(request.args.get('hours'))
        pdm.setTempBasal(amount, hours, False)
        return respond(True, pdm.pod.__dict__)
    except:
        return respond_error(msg = sys.exc_info()[0])

@app.route("/pdm/canceltempbasal")
def canceltempbasal():
    try:
        pdm = get_pdm()
        pdm.cancelTempBasal()
        return respond(True, pdm.pod.__dict__)
    except:
        return respond_error(msg = sys.exc_info()[0])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4444)
