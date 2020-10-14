#!/home/pi/v/bin/python3
import requests
import time
import signal
import sys
from threading import Event, Lock
from google.api_core.exceptions import AlreadyExists, DeadlineExceeded
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.proto.pubsub_pb2 import PubsubMessage, ReceivedMessage

from omnipy_messenger import OmniPyMessengerClient
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.definitions import *
import simplejson as json
from decimal import *


def get_now():
    return int(time.time() * 1000)


def get_ticks(d: Decimal) -> int:
    return int(round(d / Decimal("0.05")))


def ticks_to_decimal(ticks: int) -> Decimal:
    return Decimal("0.05") * ticks


def seconds_to_hours(minutes: int) -> Decimal:
    return Decimal(minutes) / Decimal("3600")


def is_expired(req):
    if "expiration" in req and req["expiration"] is not None:
        expiration = int(req["expiration"])
        if get_now() > expiration:
            return True
    return False


def status_match(req, pod):
    if "pod_updated" in req and req["pod_updated"] is not None:
        return req["pod_updated"] == int(pod["state_last_updated"] * 1000)


def get_json(message_data):
    return json.loads(bytes.decode(message_data, encoding='UTF-8'))


def ntp_update():
    os.system('sudo systemctl stop ntp')
    try:
        if os.system('sudo ntpd -gq') != 0:
            raise OSError()
    finally:
        os.system('sudo systemctl start ntp')


def restart():
    os.system('shutdown -r now')


def shutdown():
    os.system('shutdown -h now')


class MqOperator(object):
    def __init__(self):
        configureLogging()
        self.logger = getLogger(with_console=True)
        get_packet_logger(with_console=True)
        self.logger.info("mq operator is starting")

        with open("settings.json", "r") as stream:
            self.settings = json.load(stream)

        self.i_pdm: Pdm = None
        self.i_pod: Pod = None
        self.g_pdm: Pdm = None
        self.g_pod: Pod = None

        self.insulin_bolus_pulse_interval = 4
        self.next_pdm_run = time.time()

        self.exit_event = Event()
        self.stop_event = Event()
        self.requests = []
        self.executed_req_ids = []
        self.omc: OmniPyMessengerClient = None

        self.clock_updated = False

    def run(self):
        t = threading.Thread(target=self.main)
        t.start()
        t.join()

    def main(self):
        time.sleep(5)
        try:
            self.omc = OmniPyMessengerClient('/home/pi/omnipy/data/messenger.db')
            self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
            self.i_pdm = Pdm(self.i_pod)
            self.i_pdm.start_radio()

            while True:
                time.sleep(3)
                self.pull_messages()
                if self.exit_event.is_set():
                    break
                self.process_requests()

        except Exception:
            raise
        finally:
            self.stop_event.set()

    def pull_messages(self):
        last_ping = None
        while True:
            time.sleep(3)
            messages = self.omc.get_messages()
            if self.exit_event.is_set():
                break
            for message in messages:
                self.process_message(message)
                if self.exit_event.is_set():
                    break
            self.process_requests()
            if last_ping is None or last_ping + 300 < time.time():
                try:
                    requests.get("https://hc-ping.com/0a575069-cdf8-417b-abad-bb9d32acd5ea", timeout=10)
                    last_ping = time.time()
                except:
                    pass

    def process_message(self, message: {}):
        try:
            new_request = get_json(message['message'])
            new_request['req_msg_id'] = message['id']
            new_request['req_msg_publish_time'] = message['publish_time']

            if new_request['req_msg_id'] in self.executed_req_ids\
                    or new_request['id'] in [r['id'] for r in self.requests]:
                self.omc.mark_as_read(message['id'])
            else:
                self.logger.debug(f'new request received, type: {new_request["type"]}, id: {new_request["id"]}')
                self.requests.append(new_request)

        except Exception as e:
            self.logger.error("Error parsing message in callback", e)
            self.omc.mark_as_read(message['id'])

    def process_requests(self):
        while True:
            self.filter_expired()
            self.filter_outdated()
            self.filter_redundant()
            self.sort_requests()

            if len(self.requests) > 0:
                req = self.requests[0]
                self.requests = self.requests[1:]
                self.executed_req_ids.append(req['id'])
            else:
                break

            self.omc.mark_as_read(req["req_msg_id"])
            try:
                self.perform_request(req)
                self.send_response(req, "success")
            except Exception as e:
                self.logger.error("Error performing request", e)
                self.send_response(req, "fail")

    def filter_expired(self):
        not_expired = []
        for req in self.requests:
            if "expiration" in req and req["expiration"] is not None:
                expiration = int(req["expiration"])
            else:
                expiration = int(req["req_msg_publish_time"]) + 90 * 1000
            if get_now() > expiration:
                self.omc.mark_as_read(req["req_msg_id"])
                self.send_response(req, "expired")
            else:
                not_expired.append(req)
        self.requests = not_expired

    def filter_outdated(self):
        up_to_date = []
        pod = self.i_pod.__dict__
        for req in self.requests:
            if "state" in req and req["state"] is not None:
                last_state = int(pod["state_last_updated"] * 1000)
                if req["state"] != last_state:
                    self.omc.mark_as_read(req["req_msg_id"])
                    self.send_response(req, "outdated")
                    continue

            up_to_date.append(req)
        self.requests = up_to_date

    def filter_redundant(self):
        non_redundant = []
        types = {}

        self.requests.sort(key=lambda r: r['req_msg_publish_time'],
                           reverse=True)
        for req in self.requests:
            req_type = req["type"]
            if req_type in types:
                self.omc.mark_as_read(req["req_msg_id"])
                self.send_response(req, "redundant")
                continue

            non_redundant.append(req)
            types[req_type] = None
        self.requests = non_redundant

    def sort_requests(self):
        for req in self.requests:
            if "priority" not in req:
                req["priority"] = -1

        self.requests.sort(key=lambda r: r['priority'], reverse=True)

    def send_response(self, request: dict, result: str):
        self.logger.debug(f'responding to request {request["id"]}: {result}')
        request_copy = request.copy()
        request_copy.pop('req_msg_id')
        request_copy.pop('req_msg_publish_time')
        response = {
            'request': request_copy,
            'result': result,
            'state': int(self.i_pod.__dict__["state_last_updated"] * 1000),
            'pod': self.i_pod.__dict__
        }
        self.omc.publish_bin(json.dumps(response).encode('UTF-8'))

    def perform_request(self, req):
        self.logger.debug(f"performing request {req}")
        req_type = req["type"]

        if req_type == "last_status":
            return
        elif req_type == "update_status":
            self.i_pdm.update_status(2)
        elif req_type == "bolus":
            rp = req["parameters"]
            bolus_amount = ticks_to_decimal(int(rp["ticks"]))
            bolus_tick_interval = int(rp["interval"])
            self.i_pdm.bolus(bolus_amount, bolus_tick_interval)
        elif req_type == "temp_basal":
            rp = req["parameters"]
            basal_rate = ticks_to_decimal(int(rp["ticks"]))
            basal_duration = seconds_to_hours(int(rp["duration"]))
            self.i_pdm.set_temp_basal(basal_rate, basal_duration)
        elif req_type == "cancel_temp_basal":
            self.i_pdm.cancel_temp_basal()
        elif req_type == "deactivate":
            self.i_pdm.deactivate_pod()
        elif req_type == "update_time":
            ntp_update()
        elif req_type == "restart":
            restart()
        elif req_type == "shutdown":
            shutdown()
        elif req_type == "run":
            rp = req["parameters"]
            ret = os.system(rp["command"])
            if ret != 0:
                raise InvalidOperation
        else:
            raise InvalidOperation

import sys
import threading


def setup_thread_excepthook():
    """
    Workaround for `sys.excepthook` thread bug from:
    http://bugs.python.org/issue1230540

    Call once from the main thread before creating any threads.
    """

    init_original = threading.Thread.__init__

    def init(self, *args, **kwargs):

        init_original(self, *args, **kwargs)
        run_original = self.run

        def run_with_except_hook(*args2, **kwargs2):
            try:
                run_original(*args2, **kwargs2)
            except Exception:
                sys.excepthook(*sys.exc_info())

        self.run = run_with_except_hook

    threading.Thread.__init__ = init


def _exit_with_grace(mqo: MqOperator):
    mqo.exit_event.set()
    mqo.stop_event.wait(15)
    exit(0)


def err_exit(type, value, tb):
    exit(1)


if __name__ == '__main__':
    setup_thread_excepthook()
    sys.excepthook = err_exit
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/omnipy/google-settings.json"
    operator = MqOperator()
    try:
        signal.signal(signal.SIGTERM, lambda a, b: _exit_with_grace(operator))
        signal.signal(signal.SIGABRT, lambda a, b: _exit_with_grace(operator))
        operator.run()
    except KeyboardInterrupt:
        operator.exit_event.set()
        operator.stop_event.wait()
        exit(0)
    except Exception as e:
        print(f'error while running operator\n{e}')
        operator.exit_event.set()
        operator.stop_event.wait(15)
        exit(1)
