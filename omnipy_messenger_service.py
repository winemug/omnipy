import requests
import sqlite3
import os
import concurrent
import sys
import threading
import signal
import time
from concurrent.futures.thread import ThreadPoolExecutor
from logging import Logger, DEBUG
from threading import Event
from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.futures import Future
from google.cloud.pubsub_v1.subscriber.message import Message
from google.cloud.pubsub_v1.subscriber.scheduler import ThreadScheduler
from concurrent.futures._base import TimeoutError


class OmniPyMessengerService:
    def __init__(self, project_id: str, sub_topic: str, pub_topic: str, client_id: str,
                 path_db: str):

        try:
            self.stop_requested = Event()
            self.errored = False
            self.stopped = Event()
            self.logger = Logger('omnipy_messenger_service', level=DEBUG)
            subscriber = pubsub_v1.SubscriberClient()
            sub_topic_path = subscriber.topic_path(project_id, sub_topic)
            subscription_path = subscriber.subscription_path(project_id, f'sub-{sub_topic}-{client_id}')
            try:
                subscriber.create_subscription(subscription_path, sub_topic_path, ack_deadline_seconds=30)
            except AlreadyExists:
                pass

            self.subscriber = subscriber
            self.subscription_path = subscription_path
            self.subscription_future = None

            self.publisher = pubsub_v1.PublisherClient(
                client_config={
                    "interfaces": {
                        "google.pubsub.v1.Publisher": {
                            "retry_params": {
                                "messaging": {
                                    'total_timeout_millis': 60000,  # default: 600000
                                }
                            }
                        }
                    }
                },
                publisher_options=pubsub_v1.types.PublisherOptions(
                    flow_control=pubsub_v1.types.PublishFlowControl(
                        message_limit=1000,
                        byte_limit=1024 * 64,
                        limit_exceeded_behavior=pubsub_v1.types.LimitExceededBehavior.BLOCK,
                    )),
                batch_settings=pubsub_v1.types.BatchSettings(
                    max_bytes=1024,  # One kilobyte
                    max_latency=1,  # One second
                ))

            self.pub_topic_path = self.publisher.topic_path(project_id, pub_topic)
            self.project_id = project_id
            self.path_db = path_db
            self.publisher_thread = None
            self.main_thread = None
            self.self_destruct_timer = None
            self.online_check_timer = None
            self.watchdog_activation = None
            self.init_db()
            self.watchdog_good_boy()

        except Exception as ex:
            self.logger.error('Initialization failed', ex)
            raise ex

    def run(self):
        try:
            self.main_thread = threading.Thread(target=self.main)
            self.main_thread.start()
            while True:
                if self.main_thread.join(10):
                    return
                now = time.time()
                if not self.is_watchdog_a_good_boy():
                    self.errored = True
                    self.logger.info('watchdog activated')
                    self.stop_requested.set()
                    self.main_thread.join(10)
                    break
        except:
            self.errored = True

        self.stopped.set()

    def main(self):
        self.logger.debug('starting')

        try:
            self.subscription_future = self.subscriber.subscribe(self.subscription_path,
                                                                 callback=self.subscription_callback,
                                                                 scheduler=ThreadScheduler(
                                                                     executor=ThreadPoolExecutor(max_workers=2)
                                                                 ))
        except Exception as ex:
            self.errored = True
            self.logger.error("Failed to init subscriber", ex)
            return

        self.publisher_thread = threading.Thread(target=self.publisher_main)
        self.publisher_thread.start()

        while True:
            try:
                self.subscription_future.result(timeout=5)
            except TimeoutError:
                if self.stop_requested.wait(1):
                    break
                if self.errored:
                    break
            except Exception as ex:
                self.errored = True
                self.logger.error("subscription pull failure", ex)
                break

        self.logger.debug('stopping')
        if self.subscriber is not None:
            try:
                self.subscriber.close()
            except Exception as ex:
                self.errored = True
                self.logger.error("failed to close subscription", ex)

        try:
            if self.publisher_thread is not None:
                self.publisher_thread.join(30)
        except Exception as ex:
            self.errored = True
            self.logger.error("Error stopping publisher thread", ex)

    def publisher_main(self):
        while True:
            if self.stop_requested.wait(10):
                break
            try:
                self.publish_unpublished()
            except Exception as ex:
                self.errored = True
                self.logger.error("Publishing failed", ex)
                break

        try:
            self.publisher.stop()
        except Exception as ex:
            self.errored = True
            self.logger.error("Error stopping the publisher", ex)

    def subscription_callback(self, msg: Message):
        try:
            self.record_incoming_msg(msg)
        except Exception as ex:
            self.errored = True
            self.stop_requested.set()
            self.logger.error("Failed to record incoming message", ex)
            return

        try:
            msg.ack()
        except Exception as ex:
            self.errored = True
            self.stop_requested.set()
            self.logger.error("Failed to ack incoming message", ex)
            return

        except Exception as e:
            self.logger.error("Failed to process incoming message", e)
            try:
                msg.modify_ack_deadline(0)
                msg.nack()
            except Exception as e:
                self.errored = True
                self.stop_requested.set()
                self.logger.error("Failed to nack message", e)

        self.watchdog_good_boy()

    def on_publish_done(self, future: Future, rowid: int):
        try:
            future.result()
        except Exception as e:
            self.errored = True
            self.stop_requested.set()
            self.logger.error("Publisher returned error", e)
            return

        try:
            self.update_outgoing_msg_as_published(rowid)
        except Exception as e:
            self.errored = True
            self.stop_requested.set()
            self.logger.error("Failed to update database", e)
            return

        self.watchdog_good_boy()

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

            sql = "PRAGMA journal_mode=WAL;"
            sqlite_conn.execute(sql)

            sql = f""" DELETE FROM outgoing WHERE publish_time IS NOT NULL AND publish_time < ? """
            sqlite_conn.execute(sql, [int((time.time() - 1*3600) * 1000)])
            sql = f""" DELETE FROM incoming WHERE process_time IS NOT NULL AND process_time < ? """
            sqlite_conn.execute(sql, [int((time.time() - 6*3600) * 1000)])

    def record_incoming_msg(self, msg: Message):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = """SELECT rowid FROM incoming WHERE message_id=?"""
            params = str(msg.message_id)
            c = sqlite_conn.cursor()
            c.execute(sql, [params])
            row = c.fetchone()
            c.close()
            if row is not None:
                return row[0]

            sql = f""" INSERT INTO incoming (receive_time, publish_time, message_id, message_data)
                      VALUES(?,?,?,?) """
            params = (int(time.time() * 1000), int(msg.publish_time.timestamp() * 1000), str(msg.message_id), msg.data)
            sqlite_conn.execute(sql, params)
            return sqlite_conn.cursor().lastrowid

    def update_outgoing_msg_as_published(self, rowid: int):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" UPDATE outgoing SET publish_time=? WHERE rowid=?"""
            params = (int(time.time() * 1000), rowid)
            sqlite_conn.execute(sql, params)

    def publish_unpublished(self):
        with sqlite3.connect(self.path_db) as sqlite_conn:
            sql = f""" SELECT rowid, message_data FROM outgoing WHERE publish_time IS NULL """
            c = sqlite_conn.cursor()
            c.execute(sql)
            rows = c.fetchall()
            c.close()

        if rows is None:
            return

        for row in rows:
            future = self.publisher.publish(self.pub_topic_path, row[1])
            future.add_done_callback(lambda f: self.on_publish_done(f, row[0]))

    def watchdog_good_boy(self):
        self.watchdog_activation = time.time() + 300
        if self.self_destruct_timer is not None:
            self.self_destruct_timer.cancel()

        self.self_destruct_timer = threading.Timer(interval=600, function=self_destruct)
        self.self_destruct_timer.setDaemon(True)
        self.self_destruct_timer.start()

    def is_watchdog_a_good_boy(self) -> bool:
        now = time.time()
        return now < self.watchdog_activation and self.watchdog_activation - now <= 600


def self_destruct():
    os.system('sudo /sbin/shutdown -r now')


def setup_thread_excepthook():
    init_original = threading.Thread.__init__

    def init(self, *args, **kwargs):

        init_original(self, *args, **kwargs)
        run_original = self.run

        def run_with_except_hook(*args2, **kwargs2):
            try:
                run_original(*args2, **kwargs2)
            except:
                sys.excepthook(*sys.exc_info())

        self.run = run_with_except_hook

    threading.Thread.__init__ = init


def _exit_with_grace(oms: OmniPyMessengerService):
    oms.stop_requested.set()
    oms.stopped.wait(15)
    exit(0)


def err_exit(type, value, tb):
    exit(1)


def ping_or_die(retries: int = 3):
    while True:
        try:
            requests.get("https://hc-ping.com/0a575069-cdf8-417b-abad-bb9d32acd5ea", timeout=10)
            break
        except:
            print("failed to ping health-check.io")
            retries -= 1
            if retries == 0:
                self_destruct()
            else:
                time.sleep(30)


if __name__ == '__main__':
    setup_thread_excepthook()
    sys.excepthook = err_exit
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/omnipy/google-settings.json"
    oms = None
    try:
        ping_or_die()
        oms = OmniPyMessengerService('omnicore17', 'py-cmd', 'py-rsp', 'omnipy', '/home/pi/omnipy/data/messenger.db')
        signal.signal(signal.SIGTERM, lambda a, b: _exit_with_grace(oms))
        signal.signal(signal.SIGABRT, lambda a, b: _exit_with_grace(oms))
        oms.run()
    except KeyboardInterrupt:
        if oms is None:
            exit(1)
        oms.stop_requested.set()
        if not oms.stopped.wait(10):
            oms.errored = True
    except Exception as e:
        print(f'error while running messenger service\n{e}')
        if oms is not None:
            oms.stop_requested.set()
            oms.stopped.wait(10)
        exit(1)

    if oms is None:
        exit(1)
    elif oms.errored:
        exit(1)
    else:
        exit(0)
