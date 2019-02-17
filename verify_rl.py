#!/usr/bin/python3
from podcomm.rileylink import RileyLink
from podcomm.definitions import *
import logging
import os


logging.basicConfig(level=logging.DEBUG)

if os.path.exists(RILEYLINK_MAC_FILE):
    os.remove(RILEYLINK_MAC_FILE)

print("connecting to RL..")
r = RileyLink()
r.connect()
print("Connected. Verifying radio settings..")
r.init_radio(force_init=True)
print("All good, disconnecting..")
r.disconnect()
print("Disconnected")
