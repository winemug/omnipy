#!/usr/bin/python

import paho.mqtt.client as mqttc
import ssl
from podcomm.radio import Radio, RadioMode
import podcomm.packet as packet
import threading
import argparse
import logging

POD_SUBTOPIC = "podsez"
PDM_SUBTOPIC = "pdmsez"

def on_mqtt_connect(client, userdata, flags, rc):
    global args
    logging.debug("Connected with result code "+str(rc))
    if args.RELAY_MODE == "PDM":
        client.subscribe(args.MQTT_TOPIC + "/" + POD_SUBTOPIC)
    else:
        client.subscribe(args.MQTT_TOPIC + "/" + PDM_SUBTOPIC)

def on_mqtt_disconnect(client, userdata, rc):
    logging.debug("disconnected from mqtt")

def on_mqtt_message_receive(client, userdata, msg):
    global radio
    global mqttClient
    global args
    global correspondance

    logging.debug("Received message: %s", msg.payload)
    if str(msg.payload) == "----":
        return

    p = packet.Packet(0, msg.payload.decode("hex"))
    received = radio.sendAndReceive(p)
    publishPacket(p)

def on_mqtt_message_publish(client, userdata, mid):
    pass    

def radioCallback(packet):
    global mqttClient
    global messageEvent
    global correspondance
    global radio

    correspondance = None
    messageEvent.clear()
    logging.debug("Received packet: %s", packet)
    publishPacket(packet)
    messageEvent.wait(timeout = 30000)
    return correspondance

def publishPacket(packet):
    if args.RELAY_MODE == "PDM":
        publishTarget = args.MQTT_TOPIC + "/" + PDM_SUBTOPIC
    else:
        publishTarget = args.MQTT_TOPIC + "/" + POD_SUBTOPIC

    if packet is not None:
        mqttClient.publish(publishTarget, payload = packet.data.encode("hex"))
    else:
        mqttClient.publish(publishTarget, payload = "!!!!")

messageEvent = threading.Event()
correspondance = None
exitEvent = threading.Event()
mqttClient = None
args = None
radio = None

def main():
    global mqttClient
    global args
    global radio

    parser = argparse.ArgumentParser()
    parser.add_argument("--MQTT-SERVER", required=True) 
    parser.add_argument("--MQTT-PORT", required=False, default="1881", nargs="?") 
    parser.add_argument("--MQTT-SSL", required=False, default="", nargs="?") 
    parser.add_argument("--MQTT-CLIENTID", required=True) 
    parser.add_argument("--MQTT-TOPIC", required=True)
    parser.add_argument("--RELAY-MODE", required = True, choices=["PDM", "POD"])
    parser.add_argument("--LOG-LEVEL", required = False, choices=["DEBUG", "INFO"], default="INFO")

    args = parser.parse_args()

    logging.basicConfig(level=args.LOG_LEVEL)

    mqttClient = mqttc.Client(client_id=args.MQTT_CLIENTID, clean_session=True, transport="tcp")
    if args.MQTT_SSL != "":
        mqttClient.tls_set(certfile=None,
                                    keyfile=None, cert_reqs=ssl.CERT_REQUIRED,
                                    tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
        mqttClient.tls_insecure_set(True)

    mqttClient.on_connect = on_mqtt_connect
    mqttClient.on_disconnect = on_mqtt_disconnect
    mqttClient.on_message = on_mqtt_message_receive
    mqttClient.on_publish = on_mqtt_message_publish

    mqttClient.reconnect_delay_set(min_delay=15, max_delay=120)
    mqttClient.connect_async(args.MQTT_SERVER, port=args.MQTT_PORT, keepalive=60)
    mqttClient.retry_first_connection=True

    radio = Radio(0)
    mqttClient.loop_start()
    radio.start(recvCallback = radioCallback, radioMode = RadioMode.Pdm if args.RELAY_MODE == "POD" else RadioMode.Pod)

    try:
        while not exitEvent.wait(timeout = 1000):
            pass
    except KeyboardInterrupt:
        pass

    exitEvent.clear()

    radio.stop()
    mqttClient.loop_stop()

def signalHandler(signo, _frame):
    exitEvent.set()

if __name__ == '__main__':
    import signal
    for sig in ('TERM', 'HUP', 'INT'):
        signal.signal(getattr(signal, 'SIG'+sig), signalHandler)
    main()
