#!/usr/bin/python3

import podcomm.definitions
import logging
import time
import requests
import simplejson as json
from Crypto.Cipher import AES
import sys
import os
import base64
from decimal import *
import argparse

logger = getLogging()
ROOT_URL = "http://127.0.0.1:4444"

def get_auth_params():
    with open(".key", "rb") as keyfile:
        key = keyfile.read(32)

    r = requests.get(ROOT_URL + "/omnipy/token", timeout=10)
    print(r.text)
    j = json.loads(r.text)
    token = base64.b64decode(j["result"])

    i = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, i)
    a = cipher.encrypt(token)
    auth = base64.b64encode(a)
    iv = base64.b64encode(i)

    return {"auth": auth, "i": iv}


def main():
    parser = argparse.ArgumentParser(description="Send a command to omnipy API")
    parser.add_argument("url", type=string, default="http://127.0.0.1:4444")

    parser_newpod = parser.add_subparsers("newpod", help="newpod help")
    parser_newpod.add_argument("lot", type=int, help="Lot number of the pod")
    parser_newpod.add_argument("tid", type=int, help="Serial number of the pod")
    parser_newpod.add_argument("address", type=int, help="Radio address of the pod (optional)", default="")

    parser_status = parser.add_subparsers("status", help="status help")
    args = parser.parse_args()



    # pa = get_auth_params()
    # pa["lot"] = "44152"
    # pa["tid"] = "1250086"
    # r = requests.get("http://127.0.0.1:4444/pdm/newpod", params = pa)
    # print(r.text)


if __name__ == '__main__':
    configureLogging()
    main()