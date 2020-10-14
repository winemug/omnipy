#!/home/pi/v/bin/python3
import concurrent
import glob
import sqlite3
import time
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.definitions import *
import simplejson as json
from decimal import *
from google.cloud import pubsub_v1
import os


class MqOperator(object):
    def __init__(self):
        configureLogging()
        self.logger = getLogger(with_console=True)
        get_packet_logger(with_console=True)
        self.logger.info("mq operator is starting")

        with open("settings.json", "r") as stream:
            self.settings = json.load(stream)

        self.mqtt_client = None

        self.i_pdm = None
        self.i_pod = None
        self.g_pdm = None
        self.g_pod = None

        self.decimal_zero = Decimal("0")
        self.i_rate_requested = None
        self.i_rate_duration_requested = None
        self.i_bolus_requested = self.decimal_zero
        self.g_rate_requested = None
        self.g_bolus_requested = self.decimal_zero

        self.started = time.time()
        self.insulin_bolus_pulse_interval = 4
        self.clock_updated = time.time()
        self.next_pdm_run = time.time()
        self.publisher = None

    def run(self):
        # self.ntp_update()
        self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
        self.i_pdm = Pdm(self.i_pod)
        # self.i_pdm.start_radio()

        subscriber_client = pubsub_v1.SubscriberClient()
        subscription_path = subscriber_client.subscription_path("omnicore17", "py-cmd")

        streaming_pull_future = subscriber_client.subscribe(subscription_path, callback=self.google_sub_callback)

        self.publisher = pubsub_v1.PublisherClient(
            # Optional
            batch_settings=pubsub_v1.types.BatchSettings(
                max_bytes=1024,  # One kilobyte
                max_latency=1,  # One second
            ),

            # Optional
            publisher_options=pubsub_v1.types.PublisherOptions(
                enable_message_ordering=False,
                flow_control=pubsub_v1.types.PublishFlowControl(
                    message_limit=2000,
                    limit_exceeded_behavior=pubsub_v1.types.LimitExceededBehavior.BLOCK,
                ),
            ),

            # Optional
            client_config={
                "interfaces": {
                    "google.pubsub.v1.Publisher": {
                        "retry_params": {
                            "messaging": {
                                'total_timeout_millis': 300000,  # default: 600000
                            }
                        }
                    }
                }
            },
        )

        while True:
            try:
                streaming_pull_future.result(timeout=3)
            except concurrent.futures._base.TimeoutError:
                if self.next_pdm_run <= time.time():
                    self.run_pdm()
            except Exception as e:
                self.logger.error("What the err?", e)
                raise e

    def google_sub_callback(self, message):
        self.logger.info(
            "Received message {} of message ID {}\n".format(message, message.message_id)
        )
        js = None
        try:
            str_message = bytes.decode(message.data, encoding="ASCII")
            js = json.loads(str(str_message))
        except Exception as e:
            self.logger.error("failed to parse message", e)
        if js is not None:
            try:
                topic = js["topic"]
                msg = js["msg"]
                if self.on_message(topic, msg):
                    message.ack()
            except Exception as e:
                self.logger.error("failed to process message", e)
        self.logger.info("Acknowledged message {}\n".format(message.message_id))


    def on_message(self, topic, message):
        try:
            if topic == self.settings["mqtt_command_topic"]:
                cmd_split = message.split(' ')
                if cmd_split[0] == "temp":
                    temp_rate = self.fix_decimal(cmd_split[1])
                    temp_duration = None
                    if len(cmd_split) > 2:
                        temp_duration = self.fix_decimal(cmd_split[2])
                    self.set_insulin_rate(temp_rate, temp_duration)
                    self.next_pdm_run = time.time()
                elif cmd_split[0] == "bolus":
                    pulse_interval = None
                    bolus = self.fix_decimal(cmd_split[1])
                    if len(cmd_split) > 2:
                        pulse_interval = int(cmd_split[2])
                    self.set_insulin_bolus(bolus, pulse_interval)
                    self.next_pdm_run = time.time()
                elif cmd_split[0] == "status":
                    self.next_pdm_run = time.time()
                elif cmd_split[0] == "reboot":
                    self.send_msg("sir yes sir")
                    os.system('sudo shutdown -r now')
                else:
                    self.send_msg("lol what?")
            elif topic == self.settings["mqtt_sync_request_topic"]:
                if message == "latest":
                    self.send_result(self.i_pod)
                else:
                    spl = message.split(' ')
                    pod_id = spl[0]
                    req_ids = spl[1:]
                    self.fill_request(pod_id, req_ids)
            else:
                self.logger.warn("unknown topic: " + topic)
                return False
            return True
        except Exception as e:
            self.logger.error(e)
            self.send_msg("that didn't seem right")
            return False

    def set_insulin_rate(self, rate: Decimal, duration_hours: Decimal):
        if duration_hours is None:
            self.send_msg("Rate request: Insulin %02.2fU/h" % rate)
        else:
            self.send_msg("Rate request: Insulin {:02.2f}U/h Duration: {:02.2f}h".format(rate, duration_hours))
        self.i_rate_requested = rate
        if duration_hours is not None:
            self.i_rate_duration_requested = duration_hours
        else:
            self.i_rate_duration_requested = Decimal("3.0")

        self.send_msg("Rate request submitted")

    def set_insulin_bolus(self, bolus: Decimal, pulse_interval: int):
        self.send_msg("Bolus request: Insulin %02.2fU" % bolus)
        self.i_bolus_requested = bolus
        if pulse_interval is not None:
            self.send_msg("Pulse interval set: %d" % pulse_interval)
            self.insulin_bolus_pulse_interval = pulse_interval
        else:
            self.insulin_bolus_pulse_interval = 6
        self.send_msg("Bolus request submitted")

    def run_pdm(self):
        self.next_pdm_run = time.time() + 1800
        if not self.check_running():
            return

        if not self.deactivate_on_err():
            return

        if not self.update_status():
            return

        if not self.schedule_request():
            return

        if not self.bolus_request():
            return

    def check_running(self):
        progress = self.i_pod.state_progress
        if 0 <= progress < 8 or progress == 15:
            self.next_pdm_run = time.time() + 300
            return False
        return True

    def deactivate_on_err(self):
        if self.i_pod.state_faulted:
            self.send_msg("deactivating pod")
            try:
                self.i_pdm.deactivate_pod()
                self.send_msg("all is well, all is good")
                self.next_pdm_run = time.time() + 300
                return False
            except:
                self.send_msg("deactivation failed")
                self.next_pdm_run = time.time()
                return False
            finally:
                self.send_result(self.i_pod)
        return True

    def update_status(self):
        self.send_msg("checking pod status")
        try:
            self.i_pdm.update_status()
            self.send_msg("pod reservoir remaining: %02.2fU" % self.i_pod.insulin_reservoir)

            if self.i_pod.insulin_reservoir > 20:
                self.next_pdm_run = time.time() + 1800
            elif self.i_pod.insulin_reservoir > 10:
                self.next_pdm_run = time.time() + 600
            else:
                self.next_pdm_run = time.time() + 300
            return True
        except:
            self.send_msg("failed to get pod status")
            self.next_pdm_run = time.time() + 60
            return False
        finally:
            self.send_result(self.i_pod)

    def schedule_request(self):
        if self.i_rate_requested is not None:
            rate = self.i_rate_requested
            duration = self.i_rate_duration_requested

            self.send_msg("setting temp %02.2fU/h for %02.2f hours" % (rate, duration))
            try:
                self.i_pdm.set_temp_basal(rate, duration)
            except:
                self.send_msg("failed to set tb")
                self.next_pdm_run = time.time()
                return False
            finally:
                self.send_result(self.i_pod)

            self.send_msg("temp set")
            self.i_rate_requested = None
        return True

    def bolus_request(self):
        if self.i_bolus_requested is not None and self.i_bolus_requested > self.decimal_zero:
            self.send_msg("Bolusing %02.2fU" % self.i_bolus_requested)
            try:
                self.i_pdm.bolus(self.i_bolus_requested, self.insulin_bolus_pulse_interval)
                self.i_bolus_requested = None
            except:
                self.send_msg("failed to execute bolus")
                self.next_pdm_run = time.time() + 60
                return False
            finally:
                self.send_result(self.i_pod)

            self.i_bolus_requested = None
            self.send_msg("bolus is bolus")
        return True

    def fix_decimal(self, f):
        i_ticks = round(float(f) * 20.0)
        d_val = Decimal(i_ticks) / Decimal("20")
        return d_val

    def send_result(self, pod):
        msg = pod.GetString()
        if pod.pod_id is None:
            return
        self.logger.info("sending pod result")
        self.send_msg(msg, self.settings["mqtt_json_topic"])
        self.send_msg(msg, self.settings["mqtt_status_topic"])

    def send_msg(self, msg, topic="omnipy_response"):
        self.logger.info("sending msg: " + msg + " topic: " + topic)
        topic_path = self.publisher.topic_path("omnicore17", "py-rsp")
        msg_str = json.dumps({"topic": topic, "msg": msg})
        self.publisher.publish(topic_path, data=msg_str.encode(encoding="ASCII"))

    def ntp_update(self):
        if self.clock_updated is not None:
            if time.time() - self.clock_updated < 3600:
                return

        self.logger.info("Synchronizing clock with network time")
        try:
            os.system('sudo systemctl stop ntp')
            os.system('sudo ntpd -gq')
            os.system('sudo systemctl start ntp')
            self.logger.info("update successful")
            self.clock_updated = time.time()
        except:
            self.logger.info("update failed")

    def fill_request(self, pod_id, req_ids):
        db_path = self.find_db_path(pod_id)
        if db_path is None:
            self.send_msg("but I can't?")
            return

        with sqlite3.connect(db_path) as conn:
            for req_id in req_ids:
                req_id = int(req_id)
                cursor = conn.execute("SELECT rowid, timestamp, pod_json FROM pod_history WHERE rowid = " + str(req_id))
                row = cursor.fetchone()
                if row is not None:
                    js = json.loads(row[2])
                    js["pod_id"] = pod_id
                    js["last_command_db_id"] = row[0]
                    js["last_command_db_ts"] = row[1]

                    self.send_msg(self.settings["mqtt_json_topic"],
                                        json.dumps(js))
                cursor.close()

    def find_db_path(self, pod_id):
        self.i_pod._fix_pod_id()
        if self.i_pod.pod_id == pod_id:
            return "/home/pi/omnipy/data/pod.db"

        found_db_path=None
        for db_path in glob.glob("/home/pi/omnipy/data/*.db"):
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("SELECT pod_json FROM pod_history WHERE pod_state > 0 LIMIT 1")
                row = cursor.fetchone()
                if row is not None:
                    js = json.loads(row[0])
                    if "pod_id" not in js or js["pod_id"] is None:
                        found_id = "L" + str(js["id_lot"]) + "T" + str(js["id_t"])
                    else:
                        found_id = js["pod_id"]

                    if found_id == pod_id:
                        found_db_path = db_path
                        break
            cursor.close()
        return found_db_path


if __name__ == '__main__':
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/omnipy/google-settings.json"
    operator = MqOperator()
    operator.run()
