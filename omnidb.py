import sqlite3
from podcomm.definitions import *
from podcomm.protocol_radio import MessageExchange

class OmniDb:
    def __init__(self):
        try:
            self.db_path = DATA_PATH + OMNIPY_DATABASE
            self.logger = getLogger()
            self.logger.info("Initializing database")

            conn = sqlite3.connect()
            with conn:
                sql = """ CREATE TABLE IF NOT EXISTS pods (
                          pod_id INTEGER PRIMARY KEY,
                          radio_address integer,
                          lot integer integer,
                          tid integer integer,
                          registered real,
                          archived real,
                          pod_state integer, pod_minutes integer,
                          insulin_delivered real, insulin_canceled real, insulin_reservoir real
                          ) """

                c = conn.cursor()
                c.execute(sql)

                sql = """ CREATE TABLE IF NOT EXISTS radio_stats (
                          pod_id,
                          start REAL NOT NULL,
                          end REAL NOT NULL,
                          unique_packets INTEGER NOT NULL,
                          repeated_sends INTEGER NOT NULL,
                          repeated_receives INTEGER NOT NULL,
                          receive_timeouts INTEGER NOT NULL,
                          protocol_errors INTEGER NOT NULL,
                          bad_packets INTEGER NOT NULL,
                          radio_errors INTEGER NOT NULL,
                          pa_min INTEGER NOT NULL,
                          pa_max INTEGER NOT NULL,
                          rssi_average INTEGER NOT NULL
                          ) """

                self.unique_packets = 0
                self.repeated_sends = 0
                self.receive_timeouts = 0
                self.repeated_receives = 0
                self.protocol_errors = 0
                self.bad_packets = 0
                self.radio_errors = 0
                self.successful = False
                self.queued = 0
                self.started = 0
                self.ended = 0

                c = conn.cursor()
                c.execute(sql)

                sql = """ CREATE TABLE IF NOT EXISTS pods (
                          timestamp real, 
                          radio_address integer,
                          lot integer,
                          tid integer
                          pod_state integer, pod_minutes integer, pod_last_command text,
                          insulin_delivered real, insulin_canceled real, insulin_reservoir real
                          ) """

                c = conn.cursor()
                c.execute(sql)



        except:
            raise

    def add_msg_exchange(self, msg_exchange):
        msg_exchange = MessageExchange()
        msg_exchange.

    def doi(self):
        try:
                sql = """ INSERT INTO pod_history (timestamp, pod_state, pod_minutes, pod_last_command,
                          insulin_delivered, insulin_canceled, insulin_reservoir)
                          VALUES(?,?,?,?,?,?,?) """

                vals = (time.time(), self.state_progress, self.state_active_minutes,
                        str(self.last_command), self.insulin_delivered, self.insulin_canceled, self.insulin_reservoir)

                c.execute(sql, vals)
        except:
            raise