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

        self.decimal_zero = Decimal("0")
        self.i_rate_requested = None
        self.i_rate_duration_requested = None
        self.i_bolus_requested = self.decimal_zero
        self.g_rate_requested = None
        self.g_bolus_requested = self.decimal_zero
        self.pod_request_lock = Lock()
        self.pod_check_event = Event()

        self.started = time.time()
        self.insulin_max_bolus_at_once = Decimal("1.00")
        self.insulin_bolus_interval = 180
        self.insulin_bolus_pulse_interval = 4

        self.insulin_long_temp_rate_threshold = Decimal("1.6")
        self.insulin_long_temp_duration = Decimal("3.0")
        self.insulin_short_temp_duration = Decimal("1.0")

        self.glucagon_long_temp_rate_threshold = Decimal("4.0")
        self.glucagon_long_temp_duration = Decimal("6.0")
        self.glucagon_short_temp_duration = Decimal("1.0")


    def run(self):
        self.ntp_update()
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
        self.ntp_update()

    def on_message(self, client, userdata, message: mqtt.MQTTMessage):
        if message.topic == self.configuration.mqtt_command_topic:
            try:
                cmd_str = message.payload.decode()
                cmd_split = cmd_str.split(' ')
                if cmd_split[0] == "temp":
                    temp_rate = self.fix_decimal(cmd_split[1])
                    temp_duration = None
                    if len(cmd_split) > 2:
                        temp_duration = self.fix_decimal(cmd_split[2])
                    self.set_insulin_rate(temp_rate, temp_duration)
                elif cmd_split[0] == "bolus":
                    pulse_interval = None
                    bolus = self.fix_decimal(cmd_split[1])
                    if len(cmd_split) > 2:
                        pulse_interval = int(cmd_split[2])
                    self.set_insulin_bolus(bolus, pulse_interval)
                elif cmd_split[0] == "reboot":
                    self.send_msg("sir yes sir")
                    os.system('sudo shutdown -r now')
                else:
                    self.send_msg("lol what?")
            except:
                self.send_msg("that didn't seem right")

    def on_disconnect(self, client, userdata, rc):
        self.logger.info("Disconnected from mqtt server")

    def set_insulin_rate(self, rate: Decimal, duration_hours: Decimal):
        if duration_hours is None:
            self.send_msg("Rate request: Insulin %02.2fU/h" % rate)
        else:
            self.send_msg("Rate request: Insulin {:02.2f}U/h Duration: {:02.2f}h".format(rate, duration_hours))
        with self.pod_request_lock:
            self.i_rate_requested = rate
            self.i_rate_duration_requested = duration_hours
        self.send_msg("Rate request submitted")
        self.pod_check_event.set()

    def set_insulin_bolus(self, bolus: Decimal, pulse_interval: int):
        self.send_msg("Bolus request: Insulin %02.2fU" % bolus)
        with self.pod_request_lock:
            previous = self.i_bolus_requested
            self.i_bolus_requested = bolus
            if pulse_interval is not None:
                self.send_msg("Pulse interval set: %d" % pulse_interval)
                self.insulin_bolus_pulse_interval = pulse_interval
        if previous > self.decimal_zero:
            self.send_msg("Warning: %03.2fU bolus remains undelivered from previous requested" % previous)
        self.send_msg("Bolus request submitted")
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

        try:
            self.pdm_loop_main()
        except:
            os.system('sudo shutdown -r now')

    def pdm_loop_main(self):
        check_wait = 1
        while True:
            if self.pod_check_event.wait(check_wait):
                self.pod_check_event.clear()
                time.sleep(5)

            progress = self.i_pod.state_progress

            if 0 <= progress < 8 or progress == 15:
                check_wait = 3600
                continue

            if progress > 9:
                self.send_msg("deactivating pod")
                try:
                    self.i_pdm.deactivate_pod()
                    self.send_msg("all is well, all is good")
                    self.send_result(self.i_pod)
                    check_wait = 3600
                except:
                    self.send_msg("deactivation failed")
                    check_wait = 1
                continue

            try:
                self.send_msg("checking pod status")
                self.i_pdm.update_status()
                if self.i_pod.state_faulted:
                    self.send_msg("pod is faulted! oh my")
                    check_wait = 1
                    continue
                self.send_msg("pod reservoir remaining: %02.2fU" % self.i_pod.insulin_reservoir)

                if self.i_pod.insulin_reservoir > 20:
                    check_wait = 1800
                elif self.i_pod.insulin_reservoir > 10:
                    check_wait = 600
                else:
                    check_wait = 300
            except:
                self.send_msg("couldn't reach pod I guess?")
                check_wait = 300

            with self.pod_request_lock:
                if self.i_rate_requested is not None:
                    rate = self.i_rate_requested
                    duration = self.i_rate_duration_requested
                    if duration is None:
                        if rate <= self.insulin_long_temp_rate_threshold:
                            duration = self.insulin_long_temp_duration
                        else:
                            duration = self.insulin_short_temp_duration

                    self.send_msg("setting temp %02.2fU/h for %02.2f hours" % (rate, duration))
                    try:
                        self.i_pdm.set_temp_basal(rate, duration)
                    except:
                        self.send_msg("failed to set tb")
                        check_wait = 1
                        continue
                    finally:
                        self.send_result(self.i_pod)

                    self.send_msg("temp set")
                    self.i_rate_requested = None

            time.sleep(5)
            with self.pod_request_lock:
                bolus_request = self.i_bolus_requested
                if bolus_request > self.decimal_zero:
                    _, last_bolus_time = self.i_pod.get_bolus_total()
                    time_since_last_bolus = time.time() - last_bolus_time
                    self.send_msg("Active bolus request of %02.2fU" % bolus_request)
                    if time_since_last_bolus < self.insulin_bolus_interval:
                        check_wait = self.insulin_bolus_interval - time_since_last_bolus
                        self.send_msg("Postponing bolus request for %d seconds" % check_wait)
                    else:
                        if bolus_request > self.insulin_max_bolus_at_once:
                            to_bolus = self.insulin_max_bolus_at_once
                        else:
                            to_bolus = bolus_request

                        self.send_msg("Bolusing %02.2fU" % to_bolus)
                        self.i_bolus_requested -= to_bolus
                        try:
                            self.i_pdm.bolus(to_bolus, self.insulin_bolus_pulse_interval)
                        except:
                            self.i_bolus_requested += to_bolus
                            self.send_msg("failed to execute bolus")
                            check_wait = 1
                            continue
                        finally:
                            self.send_result(self.i_pod)

                        if self.i_bolus_requested > self.decimal_zero:
                            check_wait = self.insulin_bolus_interval
                            self.send_msg("donesies, remaining to bolus: %03.2fU" % self.i_bolus_requested)
                        else:
                            self.send_msg("bolus is bolus")

    def fix_decimal(self, f):
        i_ticks = round(float(f) * 20.0)
        d_val = Decimal(i_ticks) / Decimal("20")
        return d_val

    def send_result(self, pod):
        msg = pod.GetString()
        self.logger.info(msg)
        self.client.publish(self.configuration.mqtt_json_topic,
                            payload=msg, qos=2)

    def send_msg(self, msg):
        self.logger.info(msg)
        self.client.publish(self.configuration.mqtt_response_topic,
                            payload="%s (%s UTC)" % (msg, datetime.utcnow().strftime("%H:%M:%S")), qos=2)

    def ntp_update(self):
        self.logger.info("Synchronizing clock with network time")
        try:
            os.system('sudo systemctl stop ntp')
            os.system('sudo ntpd -gq')
            os.system('sudo systemctl start ntp')
            self.logger.info("update successful")
        except:
            self.logger.info("update failed")

if __name__ == '__main__':
    operator = MqOperator()
    operator.run()
