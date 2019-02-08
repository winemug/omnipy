#!/usr/bin/python3
from flask import Flask, request
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.packet import Packet
from podcomm.rileylink import RileyLink
from podcomm.crc import crc8
import simplejson as json

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
    pdm = get_pdm()
    pdm.updatePodStatus()
    return respond(True, pdm.pod.__dict__)

@app.route("/pdm/newpod")
def grab_pod():
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4444)
