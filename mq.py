import time
import os
from datetime import datetime

import jsonpickle

from configuration import OmnipyConfiguration
from podcomm.pdm import Pdm, PdmLock
from podcomm.pod import Pod
from podcomm.pr_rileylink import RileyLink
from podcomm.definitions import *
from logging import FileHandler
import simplejson as json
from threading import Thread
import signal
import base64
from decimal import *
from threading import Lock, Event
import paho.mqtt.client as mqtt


class MqOperator(object):
    pdm = ...  # type: Pdm

    def __init__(self):
        configureLogging()
        self.logger = getLogger(with_console=True)
        get_packet_logger(with_console=True)
        self.logger.info("mq operator is starting")

        with open("settings.json", "r") as stream:
            lines = stream.read()
            txt = ""
            for line in lines:
                txt = txt + line
        self.configuration = jsonpickle.decode(txt)
        self.client = mqtt.Client(client_id=self.configuration.mqtt_clientid, protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.tls_set(ca_certs="/etc/ssl/certs/DST_Root_CA_X3.pem")
        self.i_pdm = None
        self.i_pod = None
        self.g_pdm = None
        self.g_pod = None
        self.i_rate_requested = None
        self.i_bolus_requested = None
        self.g_rate_requested = None
        self.g_bolus_requested = None
        self.pod_request_lock = Lock()
        self.pod_check_event = Event()
        self.started = time.time()

    def run(self):
        t = Thread(target=self.pdm_loop)
        t.start()
        time.sleep(5)

        connected = False
        while not connected:
            try:
                self.client.connect(self.configuration.mqtt_host, self.configuration.mqtt_port)
                connected = True
            except:
                time.sleep(30)

        self.client.loop_forever(retry_first_connection=True)

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        self.send_msg("Well hello there")
        client.subscribe(self.configuration.mqtt_command_topic, qos=2)

    def on_message(self, client, userdata, message: mqtt.MQTTMessage):
        if message.topic == self.configuration.mqtt_command_topic:
            try:
                cmd_str = message.payload.decode()
                cmd_split = cmd_str.split(' ')
                if cmd_split[0] == "temp":
                    temp_rate = Decimal(cmd_split[1])
                    self.set_rate(temp_rate, Decimal("0"))
                elif cmd_split[0] == "bolus":
                    bolus = Decimal(cmd_split[1])
                    self.set_bolus(bolus, Decimal("0"))
                else:
                    self.send_msg("lol what?")
            except:
                self.send_msg("that didn't seem right")

    def on_disconnect(self, client, userdata, rc):
        self.logger.info("Disconnected from mqtt server")

    def set_rate(self, rate1: Decimal, rate2: Decimal):
        self.send_msg("Rate request: Insulin %02.2fU/h Glucagon %02.2fU/h" % (rate1, rate2))
        with self.pod_request_lock:
            self.i_rate_requested = rate1
            self.g_rate_requested = rate2
        self.pod_check_event.set()

    def set_bolus(self, bolus1: Decimal, bolus2: Decimal):
        self.send_msg("Bolus request: Insulin %02.2fU Glucagon %02.2fU" % (bolus1, bolus2))
        with self.pod_request_lock:
            self.i_bolus_requested = bolus1
            self.g_bolus_requested = bolus2
        self.pod_check_event.set()

    def pdm_loop(self):
        self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
        self.i_pdm = Pdm(self.i_pod)
        self.g_pod = Pod.Load("/home/pi/glucopy/data/pod.json", "/home/pi/glucopy/data/pod.db")
        self.g_pdm = Pdm(self.g_pod)

        self.i_pdm.start_radio()
        time.sleep(2)
        #self.g_pdm.start_radio()
        #time.sleep(10)

        self.check_wait = 3600
        while True:
            if self.pod_check_event.wait(self.check_wait):
                time.sleep(10)
                self.pod_check_event.clear()

            wait1 = 3600
            wait2 = 3600
            wait3 = 3600
            wait4 = 3600

            if self.i_pod.state_progress == 8 or self.i_pod.state_progress == 9:
                req = self.get_i_rate_request()
                if req is not None:
                    self.rate_check(req, 1.6, self.i_pod, self.i_pdm)
                    wait1 = self.check_wait

                req = self.get_i_bolus_request()
                if req is not None:
                    self.bolus_check(req, self.i_pod, self.i_pdm)
                    wait3 = self.check_wait

            if self.g_pod.state_progress == 8 or self.g_pod.state_progress == 9:
                time.sleep(5)
                req = self.get_g_rate_request()
                if req is not None:
                    self.rate_check(req, 0.3, self.g_pod, self.g_pdm)
                    wait1 = self.check_wait

                req = self.get_g_bolus_request()
                if req is not None:
                    self.bolus_check(req, self.g_pod, self.g_pdm)
                    wait3 = self.check_wait

            self.check_wait = min(wait1, wait2, wait3, wait4)
            if self.started is None or time.time() - self.started > 45 * 60:
                self.send_msg("rebooting for fun")
                os.system('sudo shutdown -r now')

    def get_i_rate_request(self):
        with self.pod_request_lock:
            req = self.i_rate_requested
            self.i_rate_requested = None
            return req

    def get_i_bolus_request(self):
        with self.pod_request_lock:
            return self.i_bolus_requested

    def get_g_rate_request(self):
        with self.pod_request_lock:
            req = self.g_rate_requested
            self.g_rate_requested = None
            return req

    def get_g_bolus_request(self):
        with self.pod_request_lock:
            return self.g_bolus_requested

    def rate_check(self, requested, scheduled, pod, pdm):
        requested_hours = Decimal("0")
        if requested < scheduled:
            requested_hours = Decimal("3.0")
        elif requested > scheduled:
            requested_hours = Decimal("1.0")
        else:
            self.send_msg("cancelling temp basal, if any")
            try:
                pdm.cancel_temp_basal()
            except:
                self.send_msg("nope, not good")
            finally:
                self.send_result(pod)
            return

        requested_rate = self.fix_decimal(requested)

        self.send_msg("setting temp %02.2fU/h for %02.2f hours" % (requested, requested_hours))

        try:
            pdm.set_temp_basal(requested_rate, requested_hours)
        except:
            self.send_msg("nope, not good")
        finally:
            self.send_result(pod)

    def bolus_check(self, requested, pod, pdm):
        if pod.last_enacted_bolus_start:
            boluswait = time.time() - pod.last_enacted_bolus_start
            if boluswait < 180:
                self.check_wait = boluswait
                return

        current_total = pod.get_bolus_total()
        bolus_remain = self.fix_decimal(float(requested) - current_total)
        self.send_msg(
            "current bolus total: %03.2fU requested total: %03.2fU" % (current_total, requested))
        if bolus_remain >= Decimal("0.05"):
            to_bolus = Decimal(0)
            if bolus_remain > Decimal("0.5"):
                to_bolus = Decimal("0.5")
                self.check_wait = 180
            else:
                to_bolus = bolus_remain

            self.send_msg(
                "Pending to bolus: %03.2fU, bolusing %02.2fU" % (bolus_remain, to_bolus))

            try:
                pdm.bolus(to_bolus)
            except:
                self.send_msg("nope, not good")
            finally:
                self.send_result(pod)

    def get_current_rate_state(self, pod, scheduled):
        if pod.last_enacted_temp_basal_start is not None \
                and pod.last_enacted_temp_basal_duration is not None:
            if pod.last_enacted_temp_basal_amount >= 0:
                now = time.time()
                temp_basal_end = pod.last_enacted_temp_basal_start + \
                                 (pod.last_enacted_temp_basal_duration * 3600)
                if now <= temp_basal_end:
                    return self.fix_decimal(pod.last_enacted_temp_basal_amount), int(temp_basal_end - now)

        return scheduled, 7 * 24 * 60

    def fix_decimal(self, f):
        f = Decimal(int(f * 20))
        f = f / Decimal("20")
        return f

    def send_result(self, pod):
        msg = pod.GetString()
        self.logger.info(msg)
        self.client.publish(self.configuration.mqtt_json_topic,
                            payload="%s %s" % (datetime.utcnow(), msg), qos=2)

    def send_msg(self, msg):
        self.logger.info(msg)
        self.client.publish(self.configuration.mqtt_response_topic,
                            payload="%s %s" % (datetime.utcnow(), msg), qos=2)


if __name__ == '__main__':
    operator = MqOperator()
    operator.run()
