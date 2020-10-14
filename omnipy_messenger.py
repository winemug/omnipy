import signal
import time
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from logging import Logger, DEBUG
from threading import Timer, Event, Condition

import simplejson as json
import os

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.futures import Future
from google.cloud.pubsub_v1.subscriber.message import Message
from google.cloud.pubsub_v1.subscriber.scheduler import ThreadScheduler
import sqlite3


class OmniPyMessengerClient:
    def __init__(self, path_db: str):
        self.path_db = path_db
        self.logger = Logger('omnipy_messenger_client', level=DEBUG)
        self.notify_timer = None
        self.incoming_message_event = Event()

    def notify_after(self, seconds: int = 10):
        if self.notify_timer is not None:
            self.notify_timer.cancel()
        self.notify_timer = Timer(seconds, self.notify)

    def notify(self):
        self.notify_timer = None
        self.incoming_message_event.set()

    def start(self):
        pass

    def stop(self):
        pass

    def get_messages(self) -> []:
        unprocessed = []
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" SELECT rowid, receive_time, publish_time, message_id, message_data FROM incoming WHERE process_time IS NULL ORDER BY publish_time """
            c = sqlite_conn.cursor()
            c.execute(sql)
            try:
                rows = c.fetchall()
                if rows is None:
                    return []

                for row in rows:
                    m = {'id': row[0],
                         'receive_time': row[1],
                         'publish_time': row[2],
                         'message': row[4]
                         }
                    unprocessed.append(m)
            finally:
                c.close()
        return unprocessed

    def mark_as_read(self, msg_id: int):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" UPDATE incoming SET process_time = ? WHERE rowid = ? """
            sqlite_conn.execute(sql, (int(time.time() * 1000), msg_id))

    def publish_str(self, msg_str: str):
        try:
            msg_data = msg_str.encode('UTF-8')
            self.publish_bin(msg_data)
        except Exception as e:
            self.logger.error("Failed to publish message", e)
            raise e

    def publish_bin(self, msg_data: bytes):
        try:
            self.record_outgoing_msg(msg_data)
        except Exception as e:
            self.logger.error("Failed to publish message", e)
            raise e

    def record_outgoing_msg(self, message_data: bytes):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" INSERT INTO outgoing (send_time, message_data)
                      VALUES(?,?) """
            params = (int(time.time() * 1000), message_data)
            sqlite_conn.execute(sql, params)
            return sqlite_conn.cursor().lastrowid
