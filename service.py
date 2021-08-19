import logging
import os
import uuid
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

from models import PodModel, PodMessage
from op_comm import OmnipyCommunicator
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


class OmnipyService(object):
    def __init__(self, logger, db_path):
        self.logger = logger
        self.db_path = db_path
        self.exit_requested = Event()
        self.stopped = Event()
        self.request_ids = dict()

        self.initialize_db()
        self.opc = OmnipyCommunicator(host='localhost', port=1883, client_id='opa-omnipy-mq', tls=False)
        self.db_path_cache = dict()

    def archive_pod(self, pod):
        if self.pdm is not None and self.pdm.pod.uuid == pod.uuid:
            self.pdm.stop_radio()
            self.pdm = None

    def get_pdm(self, pod_uuid: uuid):
        if self.pdm is not None and self.pdm.pod.uuid == pod_uuid:
            return self.pdm

        selected_pod = next([pod for pod in self.pods if pod.uuid == pod_uuid], None)
        if selected_pod is None:
            return None

        if self.pdm is not None:
            self.pdm.stop_radio()
            self.pdm = None

        self.pdm = Pdm(selected_pod)
        self.pdm.start_radio()
        return self.pdm

    def run(self):
        time.sleep(5)
        try:
            self.opc.start(on_command_received=self.command_received)

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
                if self.exit_requested.is_set():
                    if self.pdm is not None:
                        self.pdm.stop_radio()
                    break
        finally:
            self.stopped.set()

    def stop(self, timeout=15):
        self.exit_requested.set()
        self.stopped.wait(timeout)

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
            self.logger.error("Error performing request")
            result = dict(error=str(ex))
        finally:
            self.send_response(request, result)

    def send_response(self, request: dict, result: dict):
        response = dict(request_id=request['id'], result=result)
        self.opc.send_response(response)

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
            pod_uuid = None
            db_id = None
            if "pod_uuid" in rp:
                pod_uuid = uuid.UUID(rp["pod_uuid"])
            if "db_id" in rp:
                db_id = int(rp["db_id"])
            return self.get_record(pod_uuid, db_id)
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
        if 'record' in record_response:
            record = record_response['record']
            if record is not None:
                db_id = record['last_command_db_id']
                status_ts = int(record['state_last_updated'] * 1000)
                insulin_delivered = record['insulin_delivered']
                insulin_canceled = record['insulin_canceled']
                insulin_reservoir = record['insulin_reservoir']

        return dict(executed=True,
                    pod_uuid=record_response['uuid'],
                    last_record_id=db_id,
                    status_ts=status_ts,
                    insulin_delivered=insulin_delivered,
                    insulin_canceled=insulin_canceled,
                    insulin_reservoir=insulin_reservoir)

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
            return response

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
                        records.append(
                            dict(db_id=db_id,
                                 record=None)
                        )
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

    def find_available_address(self):
        address_range = list(range(0x34010000, 0x340100ff))



    def new_pod(self) -> PodModel:
        pod = PodModel()
        pod.id = uuid
        pod.active = False
        pod.radio_address = row[1]
        pod.message_sequence = row[2]
        pod.packet_sequence = row[3]
        pod.nonce = row[4]
        pod.seed = row[5]

    def load_pod(self, pod_id: uuid) -> PodModel:
        with sqlite3.connect(self.db_path) as conn:
            sql = "SELECT active, radio_address, message_sequence, packet_sequence, nonce, seed FROM pods WHERE id = ?"
            row = conn.execute(sql, (str(pod_id),)).fetchone()
            if row is None:
                return None

            pod = PodModel()
            pod.id = uuid
            pod.active = row[0] == 1
            pod.radio_address = row[1]
            pod.message_sequence = row[2]
            pod.packet_sequence = row[3]
            pod.nonce = row[4]
            pod.seed = row[5]
            return pod

    def save_pod(self, pod: PodModel):
        with sqlite3.connect(self.db_path) as conn:
            sql = "REPLACE INTO pods(id, active, radio_address, message_sequence, packet_sequence, nonce, seed) VALUES(?, ?, ?, ?, ?, ?, ?)"
            conn.execute(sql, (str(pod.id), 1 if pod.active else 0, pod.radio_address, pod.message_sequence, pod.packet_sequence, pod.nonce, pod.seed))

    def save_message(self, pod_id: uuid, message: PodMessage):
        with sqlite3.connect(self.db_path) as conn:
            record_msg_id = message.id
            if message.id is None:
                sql = "SELECT message_id FROM messages WHERE pod_id = ? ORDER BY message_id DESC LIMIT 1"
                row = conn.execute(sql, (str(pod_id),)).fetchone()
                if row is None:
                    record_msg_id = 0
                else:
                    record_msg_id = row[0] + 1

            if record_msg_id is None:
                sql = "INSERT INTO messages(pod_id, message_id, request_ts, request_text, request_data, response_ts, response_text, response_data) VALUES(?, ?, ?, ?, ?, ?, ?, ?)"
                conn.execute(sql, (str(pod_id), record_msg_id,
                                   message.request_ts, message.request_text, message.request_data,
                                   message.response_ts, message.response_text, message.response_data))
            else:
                sql = "UPDATE messages SET request_ts = ?, request_text = ?, request_data = ?, response_ts = ?, response_text = ?, response_data = ? WHERE pod_id = ? AND message_id = ?"
                conn.execute(sql, (message.request_ts, message.request_text, message.request_data,
                                   message.response_ts, message.response_text, message.response_data,
                                   str(pod_id), record_msg_id))

            message.id = record_msg_id

    def initialize_db(self):
        with sqlite3.connect(self.db_path) as conn:
            sql = "PRAGMA journal_mode=WAL;"
            conn.execute(sql)

            sql = """ CREATE TABLE IF NOT EXISTS pods (
                      id TEXT PRIMARY KEY,
                      active INTEGER NOT NULL,
                      radio_address INTEGER,
                      message_sequence INTEGER,
                      packet_sequence INTEGER,
                      nonce INTEGER,
                      seed INTEGER)
                      """
            conn.execute(sql)

            sql = """ CREATE TABLE IF NOT EXISTS messages (
                      pod_id TEXT NOT NULL,
                      message_id INTEGER NOT NULL,
                      request_ts REAL,
                      request_text TEXT,
                      request_data BLOB,
                      response_ts REAL,
                      response_text TEXT,
                      response_data BLOB
                      ) """
            conn.execute(sql)


def _exit_with_grace(service: OmnipyService):
    service.stop()
    exit(0)


def err_exit(type, value, tb):
    exit(1)


def setup_logging(path: str = None, console: bool = True):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    if path is not None:
        fh = logging.FileHandler(path)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    if console:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger

def main():
    sys.excepthook = err_exit
    logger = setup_logging('service.log')
    db_path = '/home/pi/omnipy/data/omnipy.db'
    service = OmnipyService(logger, db_path)
    try:
        signal.signal(signal.SIGTERM, lambda a, b: _exit_with_grace(service))
        signal.signal(signal.SIGABRT, lambda a, b: _exit_with_grace(service))
        service.run()
    except KeyboardInterrupt:
        service.stop()
        exit(0)
    except Exception as e:
        print(f'error while running operator\n{e}')
        service.stop()
        exit(1)


if __name__ == '__main__':
    main()
