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
        self.pod_check_lock = Lock()
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
        client.subscribe(self.configuration.mqtt_rate_topic, qos=2)

    def on_message(self, client, userdata, message: mqtt.MQTTMessage):
        if message.topic == self.configuration.mqtt_rate_topic:
            ratestr = message.payload.decode()
            try:
                ratespl = ratestr.split(' ')
                rate1 = Decimal(ratespl[0])
                rate2 = Decimal(ratespl[1])
                self.set_rate(rate1, rate2)
            except:
                self.send_msg("failed to parse rate message")
        if message.topic == self.configuration.mqtt_bolus_topic:
            bolusstr = message.payload.decode()
            try:
                bolusspl = ratestr.split(' ')
                bolus1 = Decimal(bolusspl[0])
                bolus2 = Decimal(bolusspl[1])
                self.set_bolus(bolus1, bolus2)
            except:
                self.send_msg("failed to parse bolus message")

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
        time.sleep(10)
        self.g_pdm.start_radio()
        time.sleep(10)

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
            if time.time() - self.started > 25 * 60:
                self.send_msg("rebooting for fun")
                os.system('sudo shutdown -r now')

    def get_i_rate_request(self):
        with self.pod_request_lock:
            return self.i_rate_requested

    def get_i_bolus_request(self):
        with self.pod_request_lock:
            return self.i_bolus_requested

    def get_g_rate_request(self):
        with self.pod_request_lock:
            return self.g_rate_requested

    def get_g_bolus_request(self):
        with self.pod_request_lock:
            return self.g_bolus_requested

    def rate_check(self, requested, scheduled, pod, pdm):
        current_rate, valid_for = self.get_current_rate_state(pod, scheduled)

        requested_for = 30 * 60
        rerequest_threshold = 10 * 60

        if requested < scheduled:
            requested_for = 120 * 60
            rerequest_threshold = 40 * 60

        requested_hours = Decimal(int(requested_for / 1800)) / Decimal("2")

        if current_rate != requested:
            self.send_msg(
                "need to change current rate from %02.2fU/h to %02.2fU/h" % (current_rate, requested))
            self.check_wait = requested_for - rerequest_threshold + 15
            self.change_rate(pdm, pod, requested, requested_hours, scheduled)
        else:
            if valid_for < rerequest_threshold:
                self.send_msg(
                    "need to extend current rate (%02.2fU/h) duration by %02.2f hours" % (
                    current_rate, requested_hours))
                self.check_wait = requested_for - rerequest_threshold + 15
                self.change_rate(pdm, pod, requested, requested_hours, scheduled)
            else:
                self.check_wait = valid_for - rerequest_threshold + 15
                self.send_msg("keeping it cool at %02.2fU/h" % current_rate)

    def bolus_check(self, requested, pod, pdm):
        pass

    def change_rate(self, pdm, pod, rate, hours, scheduled):
        try:
            # rssi_avg = self.pdm.update_status()
            # self.send_result()
            # if rssi_avg < -88:
            #     self.send_msg("RSSI average %d is too low, waiting it out" % rssi_avg)
            #     self.logger.warn("RSSI average %d is too low, maybe later then?" % rssi_avg)
            #     return

            if rate == scheduled:
                if pod.state_basal == BasalState.TempBasal:
                    self.send_msg("calling canceltemp")

                    pdm.cancel_temp_basal()
                    self.send_result(pod)
                else:
                    self.send_msg("letting scheduled rate continue to run")
            else:
                self.send_msg("setting temp %02.2fU/h for %02.2f hours" % (rate, hours))
                pdm.set_temp_basal(rate, hours)
                self.send_result(pod)
        except:
            self.send_msg("that didn't work")
            if pod.state_faulted:
                self.send_msg("pod has faulted trying to deactivate")
                try:
                    pdm.deactivate_pod()
                    self.send_msg("deactivate success")
                except:
                    self.send_msg("deactivation failed")
            self.check_wait = 60
            self.started = time.time() - 30 * 60

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

    def get_current_bolus_total(self, pod):
        pass

    def fix_decimal(self, f):
        f = Decimal(int(f * 20))
        f = f / Decimal("20")
        return f

    def send_result(self, pod):
        self.send_msg(pod.GetString())

    def send_msg(self, msg):
        self.logger.info(msg)
        self.client.publish(self.configuration.mqtt_response_topic,
                            payload="%s %s" % (datetime.utcnow(), msg), qos=2)


if __name__ == '__main__':
    operator = MqOperator()
    operator.run()
