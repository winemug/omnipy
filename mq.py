import time
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
        self.rate_requested = None
        self.rate_request_lock = Lock()
        self.rate_check_lock = Lock()
        self.rate_check_event = Event()

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
        self.logger.info("Connected to mqtt server")
        client.subscribe(self.configuration.mqtt_command_topic, qos=2)
        client.subscribe(self.configuration.mqtt_rate_topic, qos=2)
        self.send_msg("Well hello there")

    def on_message(self, client, userdata, message: mqtt.MQTTMessage):
        ratestr = message.payload.decode()
        self.logger.info("Message %s %s %s " % (message.topic, message.timestamp, ratestr))
        try:
            ratespl = ratestr.split(' ')
            rate1 = Decimal(ratespl[0])
            rate2 = Decimal(ratespl[1])
            self.set_rate(rate1, rate2)
        except:
            self.send_msg("failed to parse message")

    def on_disconnect(self, client, userdata, rc):
        self.logger.info("Disconnected from mqtt server")

    def set_rate(self, rate1: Decimal, rate2: Decimal):
        self.logger.info("Rate request: Insulin %02.2fU/h Glucagon %02.2fU/h" % (rate1, rate2))
        with self.rate_request_lock:
            self.rate_requested = rate1, rate2
        self.trigger_check()

    def pdm_loop(self):
        self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
        self.i_pdm = Pdm(self.i_pod)
        self.g_pod = Pod.Load("/home/pi/glucopy/data/pod.json", "/home/pi/glucopy/data/pod.db")
        self.g_pdm = Pdm(self.g_pod)
        self.check_wait = 3600
        while(True):
            if self.rate_check_event.wait(self.check_wait):
                self.rate_check_event.clear()

            with self.rate_request_lock:
                i_requested, g_requested = self.rate_requested

            wait1 = 3600
            wait2 = 3600

            if self.i_pod.state_progress == 8 or self.i_pod.state_progress == 9:
                self.i_pdm.start_radio()
                self.rate_check(i_requested, 1.6, self.i_pod, self.i_pdm)
                wait1 = self.check_wait
                self.i_pdm.stop_radio()

            if self.g_pod.state_progress == 8 or self.g_pod.state_progress == 9:
                self.g_pdm.start_radio()
                self.rate_check(g_requested, 0.3, self.g_pod, self.g_pdm)
                wait2 = self.check_wait
                self.g_pdm.stop_radio()

            self.check_wait = min(wait1, wait2)

    def trigger_check(self):
        self.rate_check_event.set()

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
                    "need to extend current rate (%02.2fU/h) duration by %02.2f hours" % (current_rate, requested_hours))
                self.check_wait = requested_for - rerequest_threshold + 15
                self.change_rate(pdm, pod, requested, requested_hours, scheduled)
            else:
                self.check_wait = valid_for - rerequest_threshold + 15
                self.send_msg("keeping it cool at %02.2fU/h" % current_rate)

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
                    self.logger.info("calling canceltemp, ensuring no temp running")
                    self.send_msg("calling canceltemp")

                    pdm.cancel_temp_basal()
                    self.send_result(pod)
                else:
                    self.logger.info("letting scheduled rate continue to run")
            else:
                self.logger.info("setting temp %02.2fU/h for %02.2f hours" % (rate, hours))
                self.send_msg("setting temp %02.2fU/h for %02.2f hours" % (rate, hours))
                pdm.set_temp_basal(rate, hours)
                self.send_result(pod)
        except:
            self.send_msg("that didn't work")
            if pod.state_faulted:
                self.send_msg("pod has faulted trying to deactivate")
                try:
                    #pdm.deactivate_pod()
                    self.send_msg("deactivate success")
                except:
                    self.send_msg("deactivation failed")
            self.check_wait = 60

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
        self.send_msg(pod.GetString())

    def send_msg(self, msg):
        self.client.publish(self.configuration.mqtt_response_topic,
                            payload="%s %s" % (datetime.utcnow(), msg), qos=2)


if __name__ == '__main__':
    operator = MqOperator()
    operator.run()
