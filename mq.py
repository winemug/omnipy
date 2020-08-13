#!/home/pi/v/bin/python3
import asyncio
import glob
import sqlite3
import time
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.definitions import *
import simplejson as json
from decimal import *
from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_1, QOS_2


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

        self.msg_to_send = []

    async def run(self):
        self.ntp_update()
        self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
        self.i_pdm = Pdm(self.i_pod)
        self.i_pdm.start_radio()
        #time.sleep(10)
        not_yet_connected = True

        config = {
            'keep_alive': 15,
            'ping_delay': 5,
            'default_qos': 1,
            'default_retain': False,
            'auto_reconnect': False,
            'reconnect_max_interval': 5,
            'reconnect_retries': 10000
        }
        self.mqtt_client = MQTTClient(config=config, client_id=self.settings["mqtt_client_id"])
        while True:
            try:
                await self.mqtt_client.connect(f'mqtts://{self.settings["mqtt_host"]}:{self.settings["mqtt_port"]}'
                                               ,cleansession=not_yet_connected)
                not_yet_connected = False
                await self.mqtt_client.subscribe([
                    (self.settings['mqtt_command_topic'], QOS_1),
                    (self.settings['mqtt_sync_request_topic'], QOS_1),

                ])
                self.logger.info("Subscribed")

                while True:
                    if self.next_pdm_run <= time.time():
                        await self.run_pdm()
                    else:
                        while True:
                            try:
                                await self.try_send_messages()
                                message = await self.mqtt_client.deliver_message(timeout=5)
                                if message is None:
                                    break
                                packet = message.publish_packet
                                topic = packet.variable_header.topic_name
                                payload = packet.payload.data.decode()
                                self.logger.info(f"Incoming message on topic: {topic}")
                                await self.on_message(topic, payload)
                            except asyncio.TimeoutError:
                                break
            except Exception as e:
                self.logger.error("Connection error", e)
                time.sleep(5)

    async def on_message(self, topic, message):
        try:
            if topic == self.settings["mqtt_command_topic"]:
                cmd_split = message.split(' ')
                if cmd_split[0] == "temp" or cmd_split[0] == "t":
                    temp_rate = self.fix_decimal(cmd_split[1])
                    temp_duration = None
                    if len(cmd_split) > 2:
                        temp_duration = self.fix_decimal(cmd_split[2])
                    await self.set_insulin_rate(temp_rate, temp_duration)
                    self.next_pdm_run = time.time()
                elif cmd_split[0] == "bolus" or cmd_split[0] == "b":
                    pulse_interval = None
                    bolus = self.fix_decimal(cmd_split[1])
                    if len(cmd_split) > 2:
                        pulse_interval = int(cmd_split[2])
                    await self.set_insulin_bolus(bolus, pulse_interval)
                    self.next_pdm_run = time.time()
                elif cmd_split[0] == "status" or cmd_split[0] == "s":
                    self.next_pdm_run = time.time()
                elif cmd_split[0] == "reboot" or cmd_split[0] == "r":
                    await self.send_msg("sir yes sir")
                    os.system('sudo shutdown -r now')
                # elif cmd_split[0] == "halt" or cmd_split[0] == "h":
                #     await self.send_msg("sir bye sir")
                #     os.system('sudo shutdown -h now')
                else:
                    await self.send_msg("lol what?")
            elif topic == self.settings["mqtt_sync_request_topic"]:
                if message == "latest":
                    await self.send_result(self.i_pod)
                else:
                    spl = message.split(' ')
                    pod_id = spl[0]
                    req_ids = spl[1:]
                    await self.fill_request(pod_id, req_ids)
        except Exception as e:
            self.logger.error(e)
            await self.send_msg("that didn't seem right")

    async def set_insulin_rate(self, rate: Decimal, duration_hours: Decimal):
        if duration_hours is None:
            await self.send_msg("Rate request: Insulin %02.2fU/h" % rate)
        else:
            await self.send_msg("Rate request: Insulin {:02.2f}U/h Duration: {:02.2f}h".format(rate, duration_hours))
        self.i_rate_requested = rate
        if duration_hours is not None:
            self.i_rate_duration_requested = duration_hours
        else:
            self.i_rate_duration_requested = Decimal("3.0")

        await self.send_msg("Rate request submitted")

    async def set_insulin_bolus(self, bolus: Decimal, pulse_interval: int):
        await self.send_msg("Bolus request: Insulin %02.2fU" % bolus)
        self.i_bolus_requested = bolus
        if pulse_interval is not None:
            await self.send_msg("Pulse interval set: %d" % pulse_interval)
            self.insulin_bolus_pulse_interval = pulse_interval
        else:
            self.insulin_bolus_pulse_interval = 6
        await self.send_msg("Bolus request submitted")

    async def run_pdm(self):
        self.next_pdm_run = time.time() + 1800
        if not await self.check_running():
            return

        if not await self.deactivate_on_err():
            return

        if not await self.update_status():
            return

        if not await self.schedule_request():
            return

        if not await self.bolus_request():
            return

    async def check_running(self):
        progress = self.i_pod.state_progress
        if 0 <= progress < 8 or progress == 15:
            self.next_pdm_run = time.time() + 300
            return False
        return True

    async def deactivate_on_err(self):
        if self.i_pod.state_faulted:
            await self.send_msg("deactivating pod")
            try:
                self.i_pdm.deactivate_pod()
                await self.send_msg("all is well, all is good")
                self.next_pdm_run = time.time() + 300
                return False
            except:
                await self.send_msg("deactivation failed")
                self.next_pdm_run = time.time()
                return False
            finally:
                await self.send_result(self.i_pod)
        return True

    async def update_status(self):
        await self.send_msg("checking pod status")
        try:
            self.i_pdm.update_status()
            await self.send_msg("pod reservoir remaining: %02.2fU" % self.i_pod.insulin_reservoir)

            if self.i_pod.insulin_reservoir > 20:
                self.next_pdm_run = time.time() + 1800
            elif self.i_pod.insulin_reservoir > 10:
                self.next_pdm_run = time.time() + 600
            else:
                self.next_pdm_run = time.time() + 300
            return True
        except:
            await self.send_msg("failed to get pod status")
            self.next_pdm_run = time.time() + 60
            return False
        finally:
            await self.send_result(self.i_pod)

    async def schedule_request(self):
        if self.i_rate_requested is not None:
            rate = self.i_rate_requested
            duration = self.i_rate_duration_requested

            await self.send_msg("setting temp %02.2fU/h for %02.2f hours" % (rate, duration))
            try:
                self.i_pdm.set_temp_basal(rate, duration)
            except:
                await self.send_msg("failed to set tb")
                self.next_pdm_run = time.time()
                return False
            finally:
                await self.send_result(self.i_pod)

            await self.send_msg("temp set")
            self.i_rate_requested = None
        return True

    async def bolus_request(self):
        if self.i_bolus_requested is not None and self.i_bolus_requested > self.decimal_zero:
            await self.send_msg("Bolusing %02.2fU" % self.i_bolus_requested)
            try:
                self.i_pdm.bolus(self.i_bolus_requested, self.insulin_bolus_pulse_interval)
                self.i_bolus_requested = None
            except:
                await self.send_msg("failed to execute bolus")
                self.next_pdm_run = time.time() + 60
                return False
            finally:
                await self.send_result(self.i_pod)

            self.i_bolus_requested = None
            await self.send_msg("bolus is bolus")
        return True

    def fix_decimal(self, f):
        i_ticks = round(float(f) * 20.0)
        d_val = Decimal(i_ticks) / Decimal("20")
        return d_val

    async def send_result(self, pod):
        msg = pod.GetString()
        if pod.pod_id is None:
            return
        self.msg_to_send.append((self.settings["mqtt_json_topic"],
                            bytearray(msg, encoding='ascii'), False))

        self.msg_to_send.append((self.settings["mqtt_status_topic"],
                            bytearray(msg, encoding='ascii'), True))

        await self.try_send_messages()

    async def send_msg(self, msg):
        self.logger.info(msg)
        self.msg_to_send.append((self.settings["mqtt_response_topic"],
                                 bytearray(msg, encoding='ascii'), True))
        await self.try_send_messages()

    async def try_send_messages(self):
        while len(self.msg_to_send) > 0:
            try:
                topic, msg, retain = self.msg_to_send[0]
                self.mqtt_client.publish(topic,
                                               msg,
                                               retain=retain,
                                               qos=QOS_1)
                if len(self.msg_to_send) > 1:
                    self.msg_to_send = self.msg_to_send[1:-1]
                else:
                    self.msg_to_send = []
            except:
                break

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

    async def fill_request(self, pod_id, req_ids):
        db_path = self.find_db_path(pod_id)
        if db_path is None:
            await self.send_msg("but I can't?")
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

                    await self.mqtt_client.publish(self.settings["mqtt_json_topic"],
                                        bytearray(json.dumps(js), encoding='ascii'), QOS_1)
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
    while True:
        operator = MqOperator()
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(operator.run())
        except Exception as e:
            print("force stopping async io loop due error: %s" % e)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
