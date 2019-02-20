#!/usr/bin/python3
from podcomm.rileylink import RileyLink
from podcomm.definitions import *
import logging
import os


logging.basicConfig(level=logging.WARNING)

if os.path.exists(RILEYLINK_MAC_FILE):
    os.remove(RILEYLINK_MAC_FILE)

print("connecting to RL..")
r = RileyLink()
r.connect()
print("Connected. Verifying radio settings..")
r.init_radio(force_init=True)
battery_level = r.get_battery_level()
print("RL reports battery level: %d" % battery_level)
print("All looks good.")