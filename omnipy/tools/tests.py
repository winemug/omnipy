#!/usr/bin/python3
import logging
import time
import requests
import simplejson as json
from Crypto.Cipher import AES
import os
from podcomm.pdm import Pdm
from podcomm.pod import Pod
import base64
from decimal import *


def get_auth_params():
    with open(".key", "rb") as keyfile:
        key = keyfile.read(32)

    r = requests.get("http://localhost:4444/omnipy/token", timeout=10)
    print(r.text)
    j = json.loads(r.text)
    token = base64.b64decode(j["result"])

    i = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, i)
    a = cipher.encrypt(token)
    auth = base64.b64encode(a)
    iv = base64.b64encode(i)

    return {"auth": auth, "i": iv}


# logging.basicConfig(level = logging.DEBUG)
# pod = Pod()
# pod.lot = 44152
# pod.tid = 1220073
# pod.address = 0x1f10fc4b
# pod.Save("b97.json")

logging.basicConfig(level=logging.DEBUG)
pod = Pod.Load("b96.json")
pdm = Pdm(pod)
pdm.updatePodStatus(0)
pdm.updatePodStatus(1)
pdm.updatePodStatus(2)
pdm.updatePodStatus(3)
pdm.updatePodStatus(5)
pdm.updatePodStatus(6)
pdm.updatePodStatus(0x46)
pdm.updatePodStatus(0x50)
pdm.updatePodStatus(0x51)

#pdm.setTempBasal(Decimal(2.35), Decimal(2.5))

# pdm.updatePodStatus()
# print(pod)
# pdm.setTempBasal(Decimal(0.35), Decimal(1))
# time.sleep(20)
# pdm.updatePodStatus()
# print(pod)
# pdm.setTempBasal(Decimal(0.35), Decimal(1))
# print(pod)
# pdm.updatePodStatus()
# print(pod)
# pdm.cancelTempBasal()
# print(pod)
# time.sleep(2)
# pdm.cancelTempBasal()
# print(pod)
# time.sleep(2)

# pa = get_auth_params()
# pa["lot"] = "44152"
# pa["tid"] = "1250086"
# r = requests.get("http://127.0.0.1:4444/pdm/newpod", params = pa)
# print(r.text)

# pa = get_auth_params()
# r2 = requests.get("http://localhost:4444/pdm/status", params=pa, timeout=90)
# print(r2.text)



