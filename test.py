#!/usr/bin/python
from __future__ import absolute_import

from podcomm.pod import Pod
from podcomm.pdm import Pdm
from podcomm.radio import Radio, RadioMode
from podcomm.message import Message
from podcomm.nonce import Nonce
import logging
import time

#nc = Nonce(43962, 991134)
#nc.sync(0x3c350421)

logging.basicConfig(level=logging.DEBUG)

pod = Pod(43962, 991134, 0x1f10fc49)
pdm = Pdm(pod)

try:
    for i in range(0, 20):
        pdm.updatePodStatus()
        print(pdm.pod.status)
        time.sleep(10)
except EOFError:
    pass
except KeyboardInterrupt:
    pass
finally:
    pdm.cleanUp()

# radio = Radio(0, msgSequence=0x00, pktSequence=0x00)
# radio.start(radioMode = RadioMode.Pdm)

# try:
#     for i in range(0, 20):
#         msg = Message(0, "PDM", 0x1f10fc49, 0)
#         msg.addContent(0x0e, "\00")
#         print("Sending status request\n%s\n" % msg)
#         response = radio.sendRequestToPod(msg, handleStatusMessage)
#         print("Gotten response\n%s\n" % response)
#         time.sleep(10)
# except EOFError:1f10fc49a01f10fc490000005b
#     pass
# except KeyboardInterrupt:
#     pass

# radio.stop()

# m = ManchesterCodec()

# data = "AB3C"
# data = data.decode("hex")
# print m.encode(data).encode("hex")

# data = "555555555555555566a65555555555555555aa9aaa96aa95aa9aa955a9aa555a9a69aaaa99699596fbc26cd6f67809558218506175c239d5c2d94602c615d5db4d0f58485241"
# data = data.decode("hex")

# data = m.decode(data)
# print data.encode("hex")

# for i in range(len(data)-1, 5, -1):
#     computedValue = crc8(data[0:i])
#     dataValue = ord(data[i])
#     if computedValue == dataValue:
#         print "crc8 match at position %d" % i

# for i in range(len(data)-2, 5, -1):
#     for k in range(0, i-2):
#         computedValue = crc16(data[k:i])
#         dataValue = ord(data[i]) << 8 | ord(data[i+1])
#         if computedValue == dataValue:
#             print "crc16 match for range %d to %d at location %d & %d" % (k, i - 1, i, i+1)