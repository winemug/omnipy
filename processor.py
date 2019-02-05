import datetime
import logging
import threading
import time
import requests
from decimal import Decimal
from queue import Queue
import subprocess
from threading import Thread, Event

class Processor:
    def __init__(self, mqtt_client, main_topic, pdm):
        self.mqtt_client = mqtt_client
        self.main_topic = main_topic
        self.pdm = pdm
        self.rq = Queue()
        self.sq = Queue()

        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.on_message = self.on_mqtt_message_receive
        self.mqtt_client.on_publish = self.on_mqtt_message_publish
        self.last_comm = None

    def start(self, mqtt_server, mqtt_port, keep_alive_seconds):
        logging.info("connecting to mqtt service")
        self.mqtt_client.connect(mqtt_server, port=mqtt_port, keepalive=keep_alive_seconds)
        self.mqtt_client.loop_start()

    def stop(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()

    def on_mqtt_connect(self, client, userdata, flags, rc):
        logging.info("Connected to mqtt server with result code "+str(rc))
        self.mqtt_client.subscribe(self.main_topic + "/command")
        logging.info("Subscribed")

    def on_mqtt_disconnect(self, client, userdata, rc):
        logging.info("Disconnected from mqtt with result code "+str(rc))

    def on_mqtt_message_publish(self, client, userdata, mid):
        logging.info("mqtt message published: " + str(mid))

    def on_mqtt_message_receive(self, client, userdata, msg):
        try:
            logging.info("mqtt message received: %s" % msg.payload)
            msg_string = msg.payload.decode(encoding="ASCII")
            message_data = str(msg_string).split('|')
            reference = message_data[0]
            result = False

            command_age = time.time() - (float(reference) / 1000)
            logging.info("command age: %f seconds" % command_age)
            if command_age < 45:
                retries = 2
                while not result and retries > 0:
                    try:
                        retries -= 1
                        result = self.parse_and_execute(message_data)
                    except Exception as e:
                        logging.error("Exception: %s" % e)
                        logging.info("Trying %d more time(s)" % retries)
            if command_age < 300:
                self.send_result(result, reference)
            else:
                logging.warn("Command is more than 5 minutes old, ignoring")
        except Exception as e:
            logging.error("Error parsing message: %s" % e.message)

    def parse_and_execute(self, message_data):
        command = message_data[1]
        parameter1 = message_data[2]
        parameter2 = message_data[3]

        try:
            if command == "STATUS":
                self.pdm.updatePodStatus()
            if command == "BOLUS":
                amount = Decimal(parameter1)
                self.pdm.bolus(amount, False)
            if command == "CANCELBOLUS":
                self.pdm.cancelBolus()
            if command == "SETTEMPBASAL":
                amount = Decimal(parameter1)
                duration = Decimal(parameter2)
                self.pdm.setTempBasal(amount, duration)
            if command == "CANCELTEMPBASAL":
                self.pdm.cancelTempBasal()

            requests.get("https://hc-ping.com/910eb8fd-8b82-4f26-a900-3a8ba4345513")
            self.last_comm = time.time()
            return True
        except Exception as e:
            print(e)
            logging.error("Error executing command %s: %s" % (command, str(e)))
            return False


    def send_result(self, result, reference):
        msg = reference + "|"
        if result:
            msg += "OK|"
        else:
            msg += "FAILED|"

        pod = self.pdm.pod

        msg += "%d|%d|%f|%f|%d|%d|%d|%d|%s|%s|%d|%d" % \
               (pod.lastUpdated, pod.activeMinutes, pod.totalInsulin, pod.canceledInsulin, pod.progress,
                pod.bolusState, pod.basalState, pod.reservoir, pod.alarms, pod.faulted, pod.lot, pod.tid)

        logging.debug("Sending response: " + msg)

        self.mqtt_client.publish(self.main_topic + "/response", payload=msg, retain=False, qos=2)

