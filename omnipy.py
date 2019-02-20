#!/usr/bin/python3

from podcomm.definitions import *
import requests
import simplejson as json
from Crypto.Cipher import AES
import os
import base64
import argparse

ROOT_URL = "http://127.0.0.1:4444"

configureLogging()
logger = getLogger()


def get_auth_params():
    with open(KEY_FILE, "rb") as keyfile:
        key = keyfile.read(32)

    r = requests.get(ROOT_URL + REST_URL_TOKEN, timeout=10)
    j = json.loads(r.text)
    token = base64.b64decode(j["result"])

    i = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, i)
    a = cipher.encrypt(token)
    auth = base64.b64encode(a)
    iv = base64.b64encode(i)

    return {"auth": auth, "i": iv}


def call_api(root, path, pa):
    r = requests.get(root + path, params = pa)
    print(r.text)


def new_pod(args, pa):
    pa["lot"] = args.lot
    pa["tid"] = args.tid
    call_api(args.url, REST_URL_TAKEOVER_EXISTING_POD, pa)


def status(args, pa):
    call_api(args.url, REST_URL_STATUS, pa)


def main():
    parser = argparse.ArgumentParser(description="Send a command to omnipy API")
    parser.add_argument("-u", "--url", type=str, default="http://127.0.0.1:4444", required=False)

    subparsers = parser.add_subparsers(dest="sub_cmd")
    subparser = subparsers.add_parser("newpod", help="newpod -h")
    subparser.add_argument("lot", type=int, help="Lot number of the pod")
    subparser.add_argument("tid", type=int, help="Serial number of the pod")
    subparser.set_defaults(func=new_pod)

    subparser = subparsers.add_parser("status", help="status -h")
    subparser.set_defaults(func=status)

    args = parser.parse_args()
    pa = get_auth_params()
    args.func(args, pa)


if __name__ == '__main__':
    main()
