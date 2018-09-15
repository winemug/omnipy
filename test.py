#!/usr/bin/python

import sys
import datetime
import binascii
from crc import crc8, crc16
from manchester import ManchesterCodec

m = ManchesterCodec()

data = "555555555555555566a65555555555555555aa9aaa96aa95aa9aa955a9aa555a9a69aaaa99699596fbc26cd6f67809558218506175c239d5c2d94602c615d5db4d0f58485241"
data = data.decode("hex")

data = m.Decode(data)
print data.encode("hex")

for i in range(len(data)-1, 5, -1):
    computedValue = crc8(data[0:i])
    dataValue = ord(data[i])
    if computedValue == dataValue:
        print "crc8 match at position %d" % i

for i in range(len(data)-2, 5, -1):
    for k in range(0, i-2):
        computedValue = crc16(data[k:i])
        dataValue = ord(data[i]) << 8 | ord(data[i+1])
        if computedValue == dataValue:
            print "crc16 match for range %d to %d at location %d & %d" % (k, i - 1, i, i+1)
