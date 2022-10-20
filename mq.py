import datetime
import random
import traceback
import uuid
from logging import FileHandler

import simplejson as json
import datetime as dt
import glob
import re
import sqlite3
import requests
import time
import signal
import sys
from threading import Event

from op_comm import OmnipyCommunicator
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.definitions import *
from decimal import Decimal


def get_now():
    return int(time.time() * 1000)


def get_ticks_from_float(f: float) -> int:
    if f is None:
        return None

    fr = round(f, 2)
    return int(round(fr * 20))

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

        self.i_pdm: Pdm = None
        self.i_pod: Pod = None

        self.insulin_bolus_pulse_interval = 4
        self.next_pdm_run = time.time()

        self.exit_requested = Event()
        self.stopped = Event()
        self.request_ids = dict()
        self.opc = OmnipyCommunicator(host='localhost', port=1883, client_id='opa-omnipy-mq', tls=False)
        self.db_path_cache = dict()
        self.clock_updated = False

    def run(self):
        time.sleep(5)
        try:
            self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
            self.i_pdm = Pdm(self.i_pod)
            self.i_pdm.start_radio()
            self.opc.start(on_command_received=self.command_received)

            next_ping = time.time() - 10

            while True:
                time.sleep(20)
                ts_now = time.time()
                if ts_now > next_ping:
                    try:
                        requests.get("https://hc-ping.com/0a575069-cdf8-417b-abad-bb9d32acd5ea", timeout=10)
                        next_ping = ts_now + 300
                    except Exception as ex:
                        next_ping = ts_now + 60
                        self.logger.error('Failed to ping hc, not online?', ex)
                if self.exit_requested.is_set():
                    return
        finally:
            self.stopped.set()

    def command_received(self, request: dict):
        if 'id' not in request:
            print('received request without id')
            return

        if request['id'] in self.request_ids:
            print('ignoring duplicate request')
            return

        self.request_ids[request['id']] = None
        self.logger.debug(f'new request received, type: {request["type"]}, id: {request["id"]}')

        if "expiration" in request and request["expiration"] is not None:
            expiration = int(request["expiration"])
            t_now = get_now()
            if t_now > expiration:
                self.logger.debug(f'this request seems to be expired')
                self.send_response(request, dict(executed=False, reason='expired',
                                                 expiration=expiration,
                                                 process_time=t_now))
                return

        if "required_pod_state" in request and request["required_pod_state"] is not None:
            if self.i_pod is None or self.i_pod.state_last_updated is None or self.i_pod.state_last_updated == 0:
                self.logger.debug(f'this request has incorrect state')
                self.send_response(request, dict(executed=False, reason='pod_not_found',
                                                 required_state=request['required_pod_state'],
                                                 process_time=get_now()))
                return
            else:
                last_state = int(self.i_pod.state_last_updated * 1000)
                if last_state != request['required_pod_state']:
                    self.logger.debug(f'this request has incorrect state')
                    self.send_response(request, dict(executed=False, reason='state_mismatch',
                                                     required_state=request['required_pod_state'],
                                                     active_state=self.i_pod.state_last_updated,
                                                     process_time=get_now()))
                    return

        result = None
        try:
            result = self.perform_request(request)
            self.logger.debug("Request executed")
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.error("Error performing request")
            result = dict(error=str(ex), trace=traceback.format_exception(exc_type, exc_value, exc_traceback))
        finally:
            self.send_response(request, result)

    def send_response(self, request: dict, result: dict):
        response = dict(request_id=request['id'], result=result)
        self.opc.send_response(response)

    def perform_request(self, req) -> dict:
        self.logger.debug(f"performing request {req}")
        req_type = req["type"]
        if not self.clock_updated:
            if req_type != "update_time":
                ntp_update()
                self.clock_updated = True

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
            self.clock_updated = True
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
            pod_uuid = None
            db_id = None
            if "pod_uuid" in rp:
                pod_uuid = uuid.UUID(rp["pod_uuid"])
            if "db_id" in rp:
                db_id = int(rp["db_id"])
            return self.get_record(pod_uuid, db_id)
        elif req_type == "newpod":
            rp = req["parameters"]
            iu_per_ml = int(rp["iu_per_ml"])
            self.new_pod(iu_per_ml)
            return self.active_pod_state()
        elif req_type == "pair":
            self.pair_pod()
            return self.active_pod_state()
        elif req_type == "activate":
            self.activate_pod()
            return self.active_pod_state()
        elif req_type == "start":
            rp = req["parameters"]
            basal_ticks = int(rp["basal_ticks"])
            self.start_pod(basal_ticks)
            return self.active_pod_state()
        elif req_type == "mx":
            self.i_pod.radio_message_sequence += 2
            self.i_pod.radio_message_sequence %= 16
            with open(self.i_pod.path, "w") as stream:
                json.dump(self.i_pod.__dict__, stream, indent=4, sort_keys=True)
            os.system("sudo systemctl restart omnipy-mq")
            return dict(executed=True)
        else:
            return dict(executed=False,
                        reason='unknown_request_type',
                        request_type=req_type)

    def active_pod_state(self):
        record_response = self.get_record(pod_uuid=None, db_id=-1)
        db_id = None
        status_ts = None
        insulin_delivered = None
        insulin_canceled = None
        insulin_reservoir = None
        pod_progress = None
        if 'record' in record_response:
            record = record_response['record']
            if record is not None:
                db_id = record['last_command_db_id']
                if record['state_last_updated'] is None:
                    status_ts = 0
                else:
                    status_ts = int(record['state_last_updated'] * 1000)
                insulin_delivered = get_ticks_from_float(record['insulin_delivered'])
                insulin_canceled = get_ticks_from_float(record['insulin_canceled'])
                insulin_reservoir = get_ticks_from_float(record['insulin_reservoir'])
                pod_progress = record['state_progress']

        return dict(executed=True,
                    pod_uuid=record_response['uuid'],
                    last_record_id=db_id,
                    status_ts=status_ts,
                    insulin_delivered=insulin_delivered,
                    insulin_canceled=insulin_canceled,
                    insulin_reservoir=insulin_reservoir,
                    pod_progress=pod_progress)

    def get_record(self, pod_uuid: uuid, db_id: int):
        archived_ts = None
        if pod_uuid is None:
            pod_uuid = uuid.UUID(self.i_pod.uuid)
        if pod_uuid == uuid.UUID(self.i_pod.uuid):
            db_path = "/home/pi/omnipy/data/pod.db"
        else:
            db_path = self.find_db_path(pod_uuid)
            if db_path is not None:
                ds = re.findall('.+pod_(.+).db', db_path)[0]
                archived_ts = dt.datetime(year=int(ds[0:4]), month=int(ds[4:6]), day=int(ds[6:8]),
                                          hour=int(ds[9:11]), minute=int(ds[11:13]), second=int(ds[13:15])).timestamp()

        record_response = dict(uuid=str(pod_uuid))
        record_response['pod_archived'] = archived_ts is not None
        record_response['pod_archived_ts'] = archived_ts
        record_response['executed'] = False

        if db_path is None:
            record_response['reason'] = 'pod_not_found'
            return record_response

        with sqlite3.connect(db_path) as conn:
            cursor = None
            try:
                if db_id is None:
                    sql = """SELECT rowid, timestamp, pod_json FROM pod_history ORDER BY rowid"""
                    cursor = conn.execute(sql)
                elif db_id == -1:
                    sql = """SELECT rowid, timestamp, pod_json FROM pod_history ORDER BY rowid DESC LIMIT 1"""
                    cursor = conn.execute(sql)
                else:
                    sql = """SELECT rowid, timestamp, pod_json FROM pod_history WHERE rowid = ?"""
                    cursor = conn.execute(sql, (db_id,))

                row = cursor.fetchone()

                if row is None:
                    record_response['reason'] = 'not_found'
                else:
                    js = json.loads(row[2])

                    if js is None:
                        record_response['record'] = None
                    else:
                        if "data" in js:
                            js = js["data"]
                        js["last_command_db_id"] = row[0]
                        js["last_command_db_ts"] = row[1]
                    record_response['executed'] = True
                    record_response['record'] = js

                return record_response

            finally:
                if cursor is not None:
                    cursor.close()

    def find_db_path(self, pod_uuid: uuid):
        if pod_uuid in self.db_path_cache:
            return self.db_path_cache[pod_uuid]

        db_path = None
        for path in glob.glob("/home/pi/omnipy/data/*.json"):
            if path.endswith("pod.json"):
                continue

            if path in self.db_path_cache.keys():
                continue

            with open(path, 'r') as fd:
                try:
                    candidate_pod = json.load(fd)
                except:
                    candidate_pod = None

            if candidate_pod is not None and 'uuid' in candidate_pod:
                if pod_uuid == uuid.UUID(candidate_pod['uuid']):
                    db_path = path[:path.rindex('.json')] + '.db'
                    self.db_path_cache[pod_uuid] = db_path
                    break

        return db_path

    def start_pod(self, hourly_ticks: int):
        decimal_rate = ticks_to_decimal(hourly_ticks)
        schedule = []
        for _ in range(0, 48):
            schedule.append(decimal_rate)

        self.i_pdm.inject_and_start(schedule)

    def activate_pod(self):
        self.i_pdm.activate_pod()

    def pair_pod(self):
        req_address = 0x34000000 + random.randint(0, 0x1000000)
        self.i_pdm.pair_pod(req_address, utc_offset=0)

    def new_pod(self, iu_per_ml: int):
        self.i_pod.Save()
        self.i_pdm.stop_radio()
        self.i_pdm = None
        self.i_pod = None

        archive_suffix = datetime.datetime.utcnow().strftime("_%Y%m%d_%H%M%S")
        pod_prefix = '/home/pi/omnipy/data/pod'

        if os.path.isfile(pod_prefix + '.json'):
            os.rename(pod_prefix + '.json', pod_prefix + archive_suffix + '.json')
        if os.path.isfile(pod_prefix + '.db'):
            os.rename(pod_prefix + '.db', pod_prefix + archive_suffix + '.db')

        self.i_pod = Pod()
        self.i_pod.iu_per_ml = iu_per_ml
        self.i_pod.path = '/home/pi/omnipy/data/pod.json'
        self.i_pod.path_db = '/home/pi/omnipy/data/pod.db'
        self.i_pod.Save()
        if self.i_pdm is not None:
            self.i_pdm.stop_radio()
            self.i_pdm = None
        time.sleep(5)
        self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
        self.i_pdm = Pdm(self.i_pod)



def _exit_with_grace(mqo: MqOperator):
    mqo.exit_requested.set()
    mqo.stopped.wait(15)
    exit(0)


def err_exit(type, value, tb):
    exit(1)


def main():
    sys.excepthook = err_exit
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


if __name__ == '__main__':
    main()


def test():
    op = MqOperator()
    op.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
    op.i_pdm = Pdm(op.i_pod)
    return op
