#!/usr/bin/python3
from podcomm.rileylink import RileyLink
from podcomm.definitions import *
import os


logger = getLogger()

if os.path.exists(RILEYLINK_MAC_FILE):
    os.remove(RILEYLINK_MAC_FILE)

print("connecting to RL..")
r = RileyLink()
r.connect()
print("Connected. Verifying radio settings..")
r.init_radio(force_init=True)
info = r.get_info()
print(info)
print("All looks good.")