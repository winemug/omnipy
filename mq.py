#!/home/pi/v/bin/python3
import datetime as dt
import glob
import re
import sqlite3
import requests
import time
import signal
import sys
from threading import Event
from omnipy_messenger import OmniPyMessengerClient
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.definitions import *
import simplejson as json
from decimal import Decimal


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

        self.insulin_bolus_pulse_interval = 4
        self.next_pdm_run = time.time()

        self.exit_requested = Event()
        self.stopped = Event()
        self.messages = []
        self.omc: OmniPyMessengerClient = None
        self.db_path_cache = dict()
        self.clock_updated = False

    def run(self):
        time.sleep(5)
        try:
            self.omc = OmniPyMessengerClient('/home/pi/omnipy/data/messenger.db')
            self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
            self.i_pdm = Pdm(self.i_pod)
            self.i_pdm.start_radio()

            next_ping = time.time() - 10
            while True:
                ts_now = time.time()
                if ts_now > next_ping:
                    try:
                        requests.get("https://hc-ping.com/0a575069-cdf8-417b-abad-bb9d32acd5ea", timeout=10)
                        next_ping = ts_now + 300
                    except Exception as ex:
                        next_ping = ts_now + 60
                        self.logger.error('Failed to ping hc, not online?', ex)
                self.process_messages()
                if self.exit_requested.is_set():
                    return
        finally:
            self.stopped.set()

    def pull_messages(self):
        messages = self.omc.get_messages()
        if self.exit_requested.is_set():
            return False

        new_request_received = False
        for message in messages:
            try:
                request = get_json(message['message'])
                if request['id'] in [msg['request']['id'] for msg in self.messages]:
                    continue
                new_request_received = True
                self.logger.debug(f'new request received, type: {request["type"]}, id: {request["id"]}')
                message['request'] = request
                self.messages.append(message)
            except Exception as ex:
                self.logger.error("Error parsing message, ignoring.", ex)
                self.omc.mark_as_read(message['id'])
        return new_request_received

    def process_messages(self):
        try:
            while True:
                while self.pull_messages():
                    time.sleep(3)

                if len(self.messages) == 0 or self.exit_requested.is_set():
                    break

                self.filter_state_outdated()
                self.filter_expired()
                self.sort_requests()
                self.filter_redundant()

                if len(self.messages) == 0:
                    break
                message = self.messages[0]
                request = message['request']
                result = None
                try:
                    result = self.perform_request(request)
                    self.logger.debug("Request executed")
                except Exception as ex:
                    self.logger.error("Error performing request", ex)
                    result = dict(error=str(ex))
                finally:
                    self.omc.mark_as_read(message["id"])
                    self.messages.remove(message)
                    self.send_response(request, result)

        except Exception as ex:
            self.logger.error("Error performing requests", ex)

    def send_response(self, request: dict, result: dict):
        response = dict(request_id=request['id'], result=result)
        self.omc.publish_bin(json.dumps(response, ensure_ascii=False).encode('UTF-8'))

    def filter_expired(self):
        not_expired = []
        for message in self.messages:
            request = message['request']
            if "expiration" in request and request["expiration"] is not None:
                expiration = int(request["expiration"])
            else:
                expiration = int(message['publish_time']) + 180 * 1000
            t_now = get_now()
            if t_now > expiration:
                self.omc.mark_as_read(message['id'])
                self.send_response(request, dict(executed=False, reason='expired',
                                                 expiration=expiration,
                                                 reported_publish_time=message['publish_time'],
                                                 receive_time=message['receive_time'],
                                                 process_time=t_now))
            else:
                not_expired.append(message)
        self.messages = not_expired

    def filter_state_outdated(self):
        up_to_date = []
        for message in self.messages:
            request = message['request']
            if "required_pod_state" in request and request["required_pod_state"] is not None:
                if self.i_pod is None or self.i_pod.state_last_updated is None or self.i_pod.state_last_updated == 0:
                    self.omc.mark_as_read(message['id'])
                    self.send_response(request, dict(executed=False, reason='pod_not_found',
                                                     required_state=request['required_pod_state'],
                                                     receive_time=message['receive_time'],
                                                     process_time=get_now()))
                    continue
                else:
                    last_state = int(self.i_pod.state_last_updated * 1000)
                    if self.i_pod.state_last_updated != request['required_pod_state']:
                        self.omc.mark_as_read(message['id'])
                        self.send_response(request, dict(executed=False, reason='state_mismatch',
                                                         required_state=request['required_pod_state'],
                                                         active_state=self.i_pod.state_last_updated,
                                                         receive_time=message['receive_time'],
                                                         process_time=get_now()))
                    continue
            up_to_date.append(message)
        self.messages = up_to_date

    def filter_redundant(self):
        non_redundant = []
        type_ids = {}

        self.messages.sort(key=lambda m: m['publish_time'],
                           reverse=True)
        for message in self.messages:
            request = message['request']
            req_type = request["type"]
            if req_type not in ["last_status", "run", "get_record"]:
                if req_type in type_ids:
                    self.omc.mark_as_read(message["id"])
                    self.send_response(request, dict(executed=False, reason='made_redundant',
                                                     surpassing_request_id=type_ids[req_type],
                                                     active_state=self.i_pod.state_last_updated,
                                                     receive_time=message['receive_time'],
                                                     process_time=get_now()))
                    continue

            non_redundant.append(message)
            type_ids[req_type] = request['id']

        self.messages = non_redundant

    def sort_requests(self):
        for req in [msg['request'] for msg in self.messages]:
            if "priority" not in req:
                req["priority"] = -1

        self.messages.sort(key=lambda m: m['request']['priority'], reverse=True)

    def perform_request(self, req) -> dict:
        self.logger.debug(f"performing request {req}")
        req_type = req["type"]

        if req_type == "last_status":
            return self.active_pod_state()
        elif req_type == "update_status":
            self.i_pdm.update_status(2)
            return self.active_pod_state()
        elif req_type == "bolus":
            rp = req["parameters"]
            bolus_amount = ticks_to_decimal(int(rp["ticks"]))
            bolus_tick_interval = int(rp["interval"])
            self.i_pdm.bolus(bolus_amount, bolus_tick_interval)
            return self.active_pod_state()
        elif req_type == "cancel_bolus":
            self.i_pdm.cancel_bolus()
            return self.active_pod_state()
        elif req_type == "temp_basal":
            rp = req["parameters"]
            basal_rate = ticks_to_decimal(int(rp["ticks"]))
            basal_duration = seconds_to_hours(int(rp["duration"]))
            self.i_pdm.set_temp_basal(basal_rate, basal_duration)
            return self.active_pod_state()
        elif req_type == "cancel_temp_basal":
            self.i_pdm.cancel_temp_basal()
            return self.active_pod_state()
        elif req_type == "deactivate":
            self.i_pdm.deactivate_pod()
            return self.active_pod_state()
        elif req_type == "update_time":
            ntp_update()
            return dict(executed=True)
        elif req_type == "restart":
            restart()
            return dict(executed=True)
        elif req_type == "shutdown":
            shutdown()
            return dict(executed=True)
        elif req_type == "run":
            rp = req["parameters"]
            ret = os.system(rp["command"])
            if ret != 0:
                return dict(executed=False,
                            reason='exit_code_non_zero',
                            exit_code=ret)
            return dict(executed=True)
        elif req_type == "get_record":
            rp = req["parameters"]
            pod_id = None
            db_id = None
            if "pod_id" in rp:
                pod_id = rp["pod_id"]
            if "db_id" in rp:
                db_id = int(rp["db_id"])
            return self.get_record(pod_id, db_id)
        else:
            return dict(executed=False,
                        reason='unknown_request_type',
                        request_type=req_type)

    def active_pod_state(self):
        if self.i_pod is None or self.i_pod.state_last_updated is None or self.i_pod.state_last_updated == 0:
            return dict(executed=True,
                        pod_id=None,
                        last_record_id=None,
                        status_ts=None,
                        status=None)
        else:
            last_status_ts = int(self.i_pod.__dict__["state_last_updated"] * 1000)
            return dict(executed=True,
                        pod_id=self.i_pod.pod_id,
                        last_record_id=self.i_pod.last_command_db_id,
                        status_ts=last_status_ts,
                        status=self.i_pod.__dict__)

    def get_record(self, pod_id: str, db_id: int):
        archived_ts = None
        if pod_id is None or pod_id == self.i_pod.pod_id:
            db_path = "/home/pi/omnipy/data/pod.db"
        else:
            db_path = self.find_db_path(pod_id)
            if db_path is not None:
                ds = re.findall('.+pod_(.+).db', db_path)[0]
                archived_ts = dt.datetime(year=int(ds[0:4]), month=int(ds[4:6]), day=int(ds[6:8]),
                                          hour=int(ds[9:11]), minute=int(ds[11:13]), second=int(ds[13:15])).timestamp()

        response = self.active_pod_state()
        response['pod_archived'] = archived_ts is not None
        response['pod_archived_ts'] = archived_ts
        response['executed'] = False

        if db_path is None:
            response['reason'] = 'pod_not_found'
            return response

        with sqlite3.connect(db_path) as conn:
            cursor = None
            try:
                if db_id is None:
                    sql = """SELECT rowid, timestamp, pod_json FROM pod_history ORDER BY rowid"""
                    cursor = conn.execute(sql)
                else:
                    sql = """SELECT rowid, timestamp, pod_json FROM pod_history WHERE rowid = ?"""
                    cursor = conn.execute(sql, str(db_id))

                rows = cursor.fetchall()

                if rows is None or len(rows) == 0:
                    response['reason'] = 'not_found'
                else:
                    records = []
                    for row in rows:
                        js = json.loads(row[2])

                        if js is None:
                            records.append(
                                dict(db_id=db_id,
                                     record=None)
                            )
                        else:
                            if "data" in js:
                                js = js["data"]
                            js["last_command_db_id"] = row[0]
                            js["last_command_db_ts"] = row[1]
                            records.append(dict(db_id=row[0], record=js))
                    response['executed'] = True
                    response['records'] = records

                return response

            finally:
                if cursor is not None:
                    cursor.close()

    def find_db_path(self, pod_id: str):
        if pod_id in self.db_path_cache:
            return self.db_path_cache[pod_id]

        db_path = None
        for path in glob.glob("/home/pi/omnipy/data/*.db"):
            if path.endswith("pod.db"):
                continue

            if path in self.db_path_cache.keys():
                continue

            with sqlite3.connect(path) as conn:
                cursor = None
                try:
                    sql = "SELECT pod_json FROM pod_history WHERE pod_state > 2 AND pod_json IS NOT NULL"
                    cursor = conn.execute(sql)
                    row = cursor.fetchone()

                    if row is None:
                        continue

                    js = json.loads(row[2])
                    if "pod_id" not in js or js["pod_id"] is None:
                        continue
                    self.db_path_cache[js["pod_id"]] = db_path
                    if pod_id == js["pod_id"]:
                        db_path = path
                        break
                finally:
                    if cursor is not None:
                        cursor.close()

        return db_path


def _exit_with_grace(mqo: MqOperator):
    mqo.exit_requested.set()
    mqo.stopped.wait(15)
    exit(0)


def err_exit(type, value, tb):
    exit(1)


if __name__ == '__main__':
    sys.excepthook = err_exit
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/omnipy/google-settings.json"
    operator = MqOperator()
    try:
        signal.signal(signal.SIGTERM, lambda a, b: _exit_with_grace(operator))
        signal.signal(signal.SIGABRT, lambda a, b: _exit_with_grace(operator))
        operator.run()
    except KeyboardInterrupt:
        operator.exit_requested.set()
        operator.stopped.wait()
        exit(0)
    except Exception as e:
        print(f'error while running operator\n{e}')
        operator.exit_requested.set()
        operator.stopped.wait(15)
        exit(1)
