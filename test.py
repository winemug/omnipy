#!/usr/bin/python

#from podcomm.manchester import ManchesterCodec

# PDM says: 0e0100
# POD says: 1d2803a5a800002d5bff
# PDM acks

from podcomm.radio import Radio, RadioMode
from podcomm.message import Message

radio = Radio(0, msgSequence=10, pktSequence=18)
radio.start(radioMode = RadioMode.Pod)


for i in range(0,10):
    msg = Message(0, "PDM", 0x1f10fc4b, 0x00, 0x00)
    msg.addContent(0x0e, "\00")
    response = radio.sendPdmMessageAndGetPodResponse(msg)
    print("here's your response: %s", response)

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
