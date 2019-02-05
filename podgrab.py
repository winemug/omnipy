#!/usr/bin/python3
from podcomm.pod import Pod
from podcomm.pdm import Pdm
from podcomm.packet import Packet
from podcomm.rileylink import RileyLink
import logging
import sys
from podcomm.crc import crc8

logging.basicConfig(level=logging.DEBUG)

pod = Pod()
pod.lot = int(sys.argv[1])
pod.tid = int(sys.argv[2])
pod.lastNonce = None

r = RileyLink("88:6b:0f:44:fc:1b")
print("connecting to RL")
r.connect()
print("initializing")
r.init_radio()
print("ready to listen for pdm")

p = None
while True:
    data = r.get_packet(30000)
    if data is not None and len(data) > 2:
        calc = crc8(data[2:-1])
        if data[-1] == calc:
            p = Packet(0, data[2:-1])
            break

r.disconnect()
print("disconnected")

print("Setting address as 0x%08x" % p.address)
pod.address = p.address
pod.Save(sys.argv[3])

print("Now put the pdm away, wait until it's not communicating with the pod or shut it off")
input("press enter to continue")

pdm = Pdm(pod)
pdm.updatePodStatus()
print(pod)
pdm.cleanUp()

print("done.")

