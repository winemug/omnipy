#!/bin/python

import paho.mqtt.client as mqtt
import podcomm.radio as radio
import podcomm.packet as packet
source = "OR1"
target = "OR2"

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(target)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global rad
    p = packet.Packet(0, msg.payload.decode("hex"))
    rad.send(p)

def radioCallback(packet):
    global client
    client.publish(source, payload = packet.data.encode("hex"))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("192.168.8.80", 1883, 60)

rad = radio.Radio(0)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.

client.loop_start()
rad.start(radioCallback)
print "press any key to quit"
raw_input()
rad.stop()
client.loop_stop()