import sqlite3
import time
from podcomm.exceptions import OmnipyDbError
from podcomm.pod import Pod
from podcomm.definitions import *
from podcomm.protocol_radio import MessageExchange
from threading import RLock

class OmniDb:

    __instance = None

    def __new__(cls):
        if OmniDb.__instance is None:
            OmniDb.__instance = object.__new__(cls)
        return OmniDb.__instance

    def __init__(self):
        try:
            self.db_path = DATA_PATH + OMNIPY_DATABASE
            self.logger = getLogger()
            self.active_pod = None
            self.lock = RLock()
            self.logger.info("Initializing database")

            conn = sqlite3.connect(self.db_path)
            with conn:
                sql = """ CREATE TABLE IF NOT EXISTS pods (
                          id INTEGER PRIMARY KEY,
                          registered real,
                          archived real,
                          radio_address integer,
                          pod_json text
                          ) """
                c = conn.cursor()
                c.execute(sql)

                sql = """ CREATE TABLE IF NOT EXISTS pod_history (
                          id integer PRIMARY KEY,
                          pod_id integer,
                          pod_state integer,
                          pod_minutes integer,
                          insulin_delivered real,
                          insulin_canceled real,
                          insulin_reservoir real,
                          started REAL NOT NULL,
                          ended REAL NOT NULL,
                          queued REAL NOT NULL,
                          unique_sent integer NOT NULL,
                          unique_received integer NOT NULL,
                          total_sent integer NOT NULL,
                          total_received integer NOT NULL,
                          receive_timeouts integer NOT NULL,
                          send_failures integer NOT NULL,
                          protocol_errors integer NOT NULL,
                          bad_packets integer NOT NULL,
                          radio_errors integer NOT NULL,
                          avg_rssi integer NOT NULL,
                          pa_min integer NOT NULL,
                          pa_max integer NOT NULL,
                          successful integer NOT NULL,
                          FOREIGN KEY (pod_id) REFERENCES pods (id)
                          ) """
                c = conn.cursor()
                c.execute(sql)

                sql = """ CREATE TABLE IF NOT EXISTS omnipy (
                          active_pod_id integer,
                          uptime_total integer,
                          uptime_max integer,
                          pods_count integer,
                          pods_faulted integer,
                          pod_minutes_total integer,
                          insulin_delivered_total real,
                          insulin_remain_total real,
                          exchanges_total int,
                          exchanges_failed_total int,
                          exchange_duration_total int,
                          FOREIGN KEY (active_pod_id) REFERENCES pods (id)
                          ) """
                c = conn.cursor()
                c.execute(sql)

        except Exception as e:
            raise OmnipyDbError("Failed to initialize database") from e

    def get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            return conn
        except Exception as e:
            print(e)
        return None

    def get_active_pod(self):
        with self.lock:
            try:
                if self.active_pod is None:
                    with self.get_connection() as conn:
                        sql = "SELECT pod_json FROM pods INNER JOIN omnipy ON omnipy.active_pod_id = pods.id"
                        cur = conn.cursor()
                        cur.execute(sql)
                        r = cur.fetchall()
                        if len(r) == 0:
                            return None
                        pod_json = r[0][0]

            except Exception as e:
                raise OmnipyDbError("Failed to get the currently active pod") from e
        return self.active_pod

    def archive_pod(self, pod):
        with self.lock:
            pod.db_archived = time.time()
            self._insert_pod(pod)
            self._set_active_pod(None)
            self.active_pod = None

    def create_pod(self):
        with self.lock:
            pod = Pod()
            pod.db_registered = time.time()
            self._insert_pod(pod)
            self._set_active_pod(pod.db_id)
            self.active_pod = pod
            return pod

    def update_pod(self, pod):
        with self.lock:
            if pod.db_id is None:
                raise OmnipyDbError("Pod is not in the database")
            self._insert_pod(pod)

    def _set_active_pod(self, pod):
        sql = "UPDATE omnipy SET active_pod_id = ?"
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if pod is None:
                    cur.execute(sql, None)
                else:
                    cur.execute(sql, pod.db_id)
                pod.db_id = cur.lastrowid
        except Exception as e:
            raise OmnipyDbError("Failed to create new pod") from e

    def _insert_pod(self, pod):
        pod = Pod()
        sql = ''' INSERT OR REPLACE INTO pods(
                          id,
                          registered,
                          archived,
                          radio_address,
                          pod_json)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) '''

        pod_values = (pod.db_id, pod.db_registered, pod.db_archived, pod.radio_address, pod.id_lot, pod.id_t, pod.var_utc_offset,
                      pod.var_activation_date, pod.var_insertion_date, pod.id_version_pi, pod.id_version_pm,
                      pod.state_progress, pod.state_active_minutes, pod.insulin_delivered, pod.insulin_canceled,
                      pod.insulin_reservoir, pod.fault_event, pod.fault_event_rel_time, pod.fault_table_access,
                      pod.fault_insulin_state_table_corruption, pod.fault_internal_variables, pod.fault_immediate_bolus_in_progress,
                      pod.fault_progress_before, pod.fault_progress_before_2, pod.fault_information_type2_last_word)

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, pod_values)
                pod.db_id = cur.lastrowid
        except Exception as e:
            raise OmnipyDbError("Failed to create new pod") from e

    def add_comms(self):
        sql = """ CREATE TABLE IF NOT EXISTS comm (
                  id integer PRIMARY KEY,
                  pod_id integer,
                  pod_state integer,
                  pod_minutes integer,
                  insulin_delivered real,
                  insulin_canceled real,
                  insulin_reservoir real,
                  started REAL NOT NULL,
                  ended REAL NOT NULL,
                  queued REAL NOT NULL,
                  unique_sent integer NOT NULL,
                  unique_received integer NOT NULL,
                  total_sent integer NOT NULL,
                  total_received integer NOT NULL,
                  receive_timeouts integer NOT NULL,
                  send_failures integer NOT NULL,
                  protocol_errors integer NOT NULL,
                  bad_packets integer NOT NULL,
                  radio_errors integer NOT NULL,
                  avg_rssi integer NOT NULL,
                  pa_min integer NOT NULL,
                  pa_max integer NOT NULL,
                  successful integer NOT NULL,
                  FOREIGN KEY (pod_id) REFERENCES pods (id)
                  ) """
