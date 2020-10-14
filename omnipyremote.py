import signal
import time
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from logging import Logger, DEBUG
from threading import Timer

import simplejson as json
import os

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.futures import Future
from google.cloud.pubsub_v1.subscriber.message import Message
from google.cloud.pubsub_v1.subscriber.scheduler import ThreadScheduler

from omnipyrequest import *
import sqlite3


class OmniPyRemote:
    def __init__(self, project_id: str, sub_topic: str, pub_topic: str, client_id: str,
                 path_db: str):

        try:
            self.logger = Logger('omnipy_remote', level=DEBUG)
            subscriber = pubsub_v1.SubscriberClient()
            sub_topic_path = subscriber.topic_path(project_id, sub_topic)
            subscription_path = subscriber.subscription_path(project_id, f'sub-{sub_topic}-{client_id}')
            try:
                subscriber.create_subscription(subscription_path, sub_topic_path)
            except AlreadyExists:
                pass

            self.subscriber = subscriber
            self.subscription_path = subscription_path
            self.subscription_future = None

            self.publisher = pubsub_v1.PublisherClient()
            self.pub_topic_path = self.publisher.topic_path(project_id, pub_topic)
            self.project_id = project_id
            self.path_db = path_db
            self.clean_up_timer = None
            self.init_db()

        except Exception as e:
            self.logger.error('Initialization failed', e)
            raise e

    def start(self):
        self.logger.debug('starting')
        try:
            self.publish_unpublished()
        except Exception as e:
            self.logger.error("Failed to publish unpublished messages during start-up", e)

        self.clean_up_after()

        try:
            self.subscription_future = self.subscriber.subscribe(self.subscription_path,
                                                             callback=self.subscription_callback,
                                                                 scheduler=ThreadScheduler(
                                                                     executor=ThreadPoolExecutor(max_workers=2)
                                                                 ))

            self.clean_up_timer = Timer(300.0, self.clean_up)
        except Exception as e:
            self.logger.error("Failed to subscribe to topic", e)

    def stop(self):
        self.logger.debug('stopping')

        if self.clean_up_timer is not None:
            self.clean_up_timer.cancel()

        try:
            if self.subscription_future is not None:
                self.subscription_future.cancel()
                self.subscription_future = None

            self.subscriber.close()
            self.subscriber = None

        except Exception as e:
            self.logger.error("Failed to close the subscription", e)

        try:
            self.publisher.stop()
        except Exception as e:
            self.logger.error("Failed to stop the publisher", e)

    def subscription_callback(self, msg: Message):
        try:
            self.record_incoming_msg(msg)
            try:
                msg.ack()
            except Exception as e:
                self.logger.warning("Failed to ack incoming message", e)
        except Exception as e:
            self.logger.error("Failed to process incoming message", e)
            try:
                msg.modify_ack_deadline(0)
                msg.nack()
            except Exception as e:
                self.logger.warning("Failed to nack message", e)

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

    def mark_as_read(self, message_ids: []):
        if message_ids is None or len(message_ids) == 0:
            return

        with sqlite3.connect(self.path_db) as sqlite_conn:
            for id in message_ids:
                sql = f""" UPDATE incoming SET process_time = ? WHERE rowid = ? """
                sqlite_conn.execute(sql, (int(time.time()*1000), id))

    def publish_str(self, msg_str: str):
        try:
            msg_data = msg_str.encode('UTF-8')
            self.publish_bin(msg_data)
        except Exception as e:
            self.logger.error("Failed to publish message", e)
            raise e

    def publish_bin(self, msg_data: bytearray, rowid=None):
        try:
            if rowid is None:
                rowid = self.record_outgoing_msg(msg_data)
            future = self.publisher.publish(self.pub_topic_path, msg_data)
            future.add_done_callback(lambda future: self.on_publish_done(future, rowid))
        except Exception as e:
            self.logger.error("Failed to publish message", e)
            raise e

    def on_publish_done(self, future: Future, rowid: int):
        try:
            future.result()
            self.update_outgoing_msg_as_published(rowid)
        except Exception as e:
            self.logger.warning("Publisher returned error", e)

    def init_db(self):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = """ CREATE TABLE IF NOT EXISTS incoming (
                      receive_time INTEGER,
                      publish_time INTEGER,
                      process_time INTEGER,
                      message_id TEXT,
                      message_data BLOB
                      ) """
            sqlite_conn.execute(sql)

            sql = """ CREATE TABLE IF NOT EXISTS outgoing (
                      send_time INTEGER,
                      publish_time INTEGER,
                      message_data BLOB
                      ) """
            sqlite_conn.execute(sql)

    def record_incoming_msg(self, msg: Message):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = """SELECT rowid FROM incoming WHERE message_id=?"""
            params = str(msg.message_id)
            c = sqlite_conn.cursor()
            c.execute(sql, [params])
            try:
                row = c.fetchone()
                if row is not None:
                    return row[0]
            finally:
                c.close()

            sql = f""" INSERT INTO incoming (receive_time, publish_time, message_id, message_data)
                      VALUES(?,?,?,?) """
            params = (int(time.time() * 1000), int(msg.publish_time.timestamp() * 1000), str(msg.message_id), msg.data)
            sqlite_conn.execute(sql, params)
            return sqlite_conn.cursor().lastrowid

    def update_incoming_msg_as_processed(self, rowid: int):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" UPDATE incoming SET process_time=? WHERE rowid=?"""
            params = (int(time.time() * 1000), rowid)
            sqlite_conn.execute(sql, params)
        self.clean_up_after()

    def record_outgoing_msg(self, message_data: bytes):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" INSERT INTO outgoing (send_time, message_data)
                      VALUES(?,?) """
            params = (int(time.time() * 1000), message_data)
            sqlite_conn.execute(sql, params)
            return sqlite_conn.cursor().lastrowid

    def update_outgoing_msg_as_published(self, rowid: int):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" UPDATE outgoing SET publish_time=? WHERE rowid=?"""
            params = (int(time.time() * 1000), rowid)
            sqlite_conn.execute(sql, params)
        self.clean_up_after()

    def publish_unpublished(self):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" SELECT rowid, message_data FROM outgoing WHERE publish_time IS NULL """
            c = sqlite_conn.cursor()
            c.execute(sql)
            try:
                rows = c.fetchall()
                if rows is None:
                    return

                for row in rows:
                    try:
                        self.publish_bin(row[1], rowid=row[0])
                    except Exception as e:
                        self.logger.error('error publishing the unpublished', e)
            finally:
                c.close()

    def clean_up_after(self, seconds:int = 90):
        if self.clean_up_timer is not None:
            self.clean_up_timer.cancel()
        self.clean_up_timer = Timer(seconds, self.clean_up)

    def clean_up(self):
        self.clean_up_timer = None
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" DELETE FROM outgoing WHERE publish_time IS NOT NULL AND publish_time < ? """
            sqlite_conn.execute(sql, [int((time.time() - 60)*1000)])
            sql = f""" DELETE FROM incoming WHERE process_time IS NOT NULL AND process_time < ? """
            sqlite_conn.execute(sql, [int((time.time() - 60)*1000)])

def _exit_with_grace(a, b, opr: OmniPyRemote):
    opr.stop()
    #os.sync()
    exit(0)


if __name__ == "__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "c:\\dev\\pluxy\\google-secret.json"
    opr = OmniPyRemote('omnicore17', 'py-rsp', 'py-cmd', 'test1', 'pyremote.db')
    signal.signal(signal.SIGTERM, lambda a, b: _exit_with_grace(a,b, opr))
    signal.signal(signal.SIGABRT, lambda a, b: _exit_with_grace(a, b, opr))

    try:
        opr.start()
        while True:
            opr.publish_str('hey baldi over here!')
            time.sleep(10)
    except KeyboardInterrupt:
        opr.stop()
    except Exception as e:
        opr.logger.error('Service exiting unexpectedly', e)
        opr.stop()
