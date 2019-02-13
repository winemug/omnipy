#!/usr/bin/python3
import argparse
import logging
import signal
import ssl
import sys
import threading
from paho.mqtt.client import Client, MQTTv311

from podcomm.pdm import Pdm
from podcomm.pod import Pod
from processor import Processor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--POD-CONFIG", required=True)
    parser.add_argument("--MQTT-SERVER", required=True, default=None, nargs="?")
    parser.add_argument("--MQTT-PORT", required=False, default="1881", nargs="?")
    parser.add_argument("--MQTT-SSL", required=False, default="", nargs="?")
    parser.add_argument("--MQTT-CLIENTID", required=True, default="", nargs="?")
    parser.add_argument("--MQTT-TOPIC", required=True, default="", nargs="?")
    parser.add_argument("--LOG-LEVEL", required=False, default="DEBUG", nargs="?")
    parser.add_argument("--LOG-FILE", required=False, default=None, nargs="?")

    args = parser.parse_args()

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    ch.setLevel(level=args.LOG_LEVEL)
    logging.basicConfig(level=args.LOG_LEVEL, handlers=[ch])

    if args.LOG_FILE:
        fh = logging.FileHandler(filename=args.LOG_FILE)
        fh.setFormatter(formatter)
        fh.setLevel(level=args.LOG_LEVEL)
        logging.getLogger().addHandler(fh)

    pod = Pod.Load(args.POD_CONFIG)

    mqtt_client = Client(client_id=args.MQTT_CLIENTID, clean_session=False, protocol=MQTTv311, transport="tcp")

    if args.MQTT_SSL != "":
        mqtt_client.tls_set(certfile=None,
                           keyfile=None, cert_reqs=ssl.CERT_REQUIRED,
                           tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
        mqtt_client.tls_insecure_set(True)

    mqtt_client.reconnect_delay_set(min_delay=5, max_delay=120)
    mqtt_client.retry_first_connection=True

    pdm = Pdm(pod)

    processor = Processor(mqtt_client, args.MQTT_TOPIC, pdm)

    processor.start(args.MQTT_SERVER, int(args.MQTT_PORT), 30)

    try:
        while not exit_event.wait(timeout=10):
            pass
    except KeyboardInterrupt:
        pass

    processor.stop()


exit_event = threading.Event()


def signal_handler(signo, _frame):
    exit_event.set()


if __name__ == '__main__':
    for sig in ('TERM', 'HUP', 'INT'):
        signal.signal(getattr(signal, 'SIG' + sig), signal_handler)
    main()
