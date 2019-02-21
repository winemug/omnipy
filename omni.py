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
    print("turn on your pdm and request pod status")
    call_api(args.url, REST_URL_TAKEOVER_EXISTING_POD, pa)


def temp_basal(args, pa):
    pa["amount"] = args.basalrate
    pa["hours"] = args.hours
    call_api(args.url, REST_URL_SET_TEMP_BASAL, pa)


def cancel_temp_basal(args, pa):
    call_api(args.url, REST_URL_CANCEL_TEMP_BASAL, pa)


def bolus(args, pa):
    pa["amount"] = args.units
    call_api(args.url, REST_URL_BOLUS, pa)


def cancel_bolus(args, pa):
    call_api(args.url, REST_URL_CANCEL_BOLUS, pa)


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

    subparser = subparsers.add_parser("tempbasal", help="tempbasal -h")
    subparser.add_argument("basalrate", type=str, help="Temporary basal rate in U/h. e.g '1.5' for 1.5U/h")
    subparser.add_argument("hours", type=str, help="Number of hours for setting the temporary basal rate. e.g '0.5' for 30 minutes")
    subparser.set_defaults(func=temp_basal)

    subparser = subparsers.add_parser("bolus", help="bolus -h")
    subparser.add_argument("units", type=str, help="amount of insulin in units to bolus")
    subparser.set_defaults(func=bolus)

    subparser = subparsers.add_parser("canceltempbasal", help="canceltempbasal -h")
    subparser.set_defaults(func=cancel_temp_basal)

    subparser = subparsers.add_parser("cancelbolus", help="cancelbolus -h")
    subparser.set_defaults(func=cancel_bolus)

    args = parser.parse_args()
    pa = get_auth_params()
    args.func(args, pa)


if __name__ == '__main__':
    main()
