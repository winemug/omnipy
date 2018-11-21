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

def on_mqtt_message_arrived(client, userdata, msg):
    global radio
    global mqttClient
    global args
    global mqttPacket
    global mqttMessageReceivedEvent

    mqttReadyToReceiveEvent.wait()

    logging.debug("Received over mqtt: %s", msg.payload)

    mqttReadyToReceiveEvent.clear()
    mqttPacket = packet.Packet(0, msg.payload.decode("hex"))
    mqttMessageEvent.set()

def relayPacket(packet):
    global mqttClient
    global radio

    logging.debug("Publishing to mqtt: %s" % packet)
    if args.RELAY_MODE == "PDM":
        publishTarget = args.MQTT_TOPIC + "/" + PDM_SUBTOPIC
    else:
        publishTarget = args.MQTT_TOPIC + "/" + POD_SUBTOPIC

    mqttClient.publish(publishTarget, payload = packet.data.encode("hex"), qos=2)

exitEvent = threading.Event()
mqttClient = None
args = None
radio = None
mqttMessageReceivedEvent = threading.Event()
mqttReadyToReceiveEvent = threading.Event()
mqttPacket = None

def main():
    global mqttClient
    global args
    global radio
    global mqttMessageEvent

    parser = argparse.ArgumentParser()
    parser.add_argument("--POD-ADDRESS", required=True) 
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

    mqttClient.reconnect_delay_set(min_delay=15, max_delay=120)
    mqttClient.connect_async(args.MQTT_SERVER, port=args.MQTT_PORT, keepalive=60)
    mqttClient.retry_first_connection=True

    radio = Radio(0)
    addr = int(args.POD_ADDRESS, 16)
    radio.start(radioMode = RadioMode.Relay, address = args.POD_ADDRESS)
    mqttClient.on_message = on_mqtt_message_arrived
    mqttClient.loop_start()

    if args.RELAY_MODE == "PDM":
        logging.debug("Waiting for PDM to initiate communication")
        pdmPacket = radio.waitForPacket()
        publishTarget = args.MQTT_TOPIC + "/" + PDM_SUBTOPIC
        while True:
            mqttMessageReceivedEvent.clear()
            mqttClient.publish(publishTarget, payload = pdmPacket.data.encode("hex"), qos=2)
            logging.debug("PDM packet received and published to mqtt: %s" % packet)

            if pdmPacket.type == "ACK" and p.address2 == 0:
                logging.debug("POD need not respond to packet" % packet)
                break
            else:
                logging.debug("Waiting for POD packet on mqtt: %s" % packet)
                mqttReadyToReceiveEvent.set()
                mqttMessageReceivedEvent.wait()
                pdmPacket = radio.sendPacketForRelay(mqttPacket)

    else:
        logging.debug("Waiting for mqtt message to relay to POD")
        publishTarget = args.MQTT_TOPIC + "/" + POD_SUBTOPIC

        while True:
            mqttReadyToReceiveEvent.set()
            mqttMessageReceivedEvent.wait()
            logging.debug("PDM packet received over mqtt: %s" % mqttPacket)
            logging.debug("Relaying packet to pod")
            while True:
                podPacket = radio.sendPacketForRelay(mqttPacket)

                if podPacket is None:
                    if mqttPacket.type == "ACK" and mqttPacket.address2 == 0:
                        logging.debug("Pod need not respond")
                        break
                    else:
                        logging.debug("No response from pod, retrying")
                else:
                    mqttClient.publish(publishTarget, payload = podPacket.data.encode("hex"), qos=2)
                    logging.debug("Pod packet received over radio and published to mqtt: %s" % packet)
            mqttMessageReceivedEvent.clear()

    # try:
    #     while not exitEvent.wait(timeout = 1000):
    #         pass
    # except KeyboardInterrupt:
    #     pass

    # exitEvent.clear()

    radio.stop()
    mqttClient.loop_stop()

def signalHandler(signo, _frame):
    exitEvent.set()

if __name__ == '__main__':
    import signal
    for sig in ('TERM', 'HUP', 'INT'):
        signal.signal(getattr(signal, 'SIG'+sig), signalHandler)
    main()
