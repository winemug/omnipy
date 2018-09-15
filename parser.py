#!/usr/bin/python

import sys
import datetime
import binascii
from crc import crc16


lastSequences = [-1] * 8
remainingData = 0

def main():
    with open(sys.argv[1]) as f:
        for line in f:

            stripped = ""
            for c in line:
                if ord(c) < 32 or ord(c) > 127:
                    break
                stripped += c

            if len(stripped) == 0:
                continue

            try:
                timestamp = "<date/time unknown>"
                if len(stripped) <= 26 or stripped[26] != ' ':
                    data = stripped[0:].decode("hex")
                else:
                    timestamp = stripped[0:26]
                    data = stripped[27:].decode("hex")
                decode(data, timestamp)
            except:
                print "Failed to decode line: " + stripped

def decode(data, timestamp):
    global remainingData, lastSequences
    p_addr1 = binascii.hexlify(data[0:4])

    p_t = ord(data[4]) >> 5
    p_seq = ord(data[4]) & 0b00011111

    if p_t == 5:
        p_type = "PDM"
    elif p_t == 7:
        p_type = "POD"
    elif p_t == 2:
        p_type = "ACK"
    elif p_t == 4:
        p_type = "CON"
    else:
        p_type = bin(p_t)[2:5].zfill(3)

    if lastSequences[p_t] == p_seq:
        return
    lastSequences[p_t] = p_seq

    p_unk1 = "----"
    p_unk2 = "----"
    p_addr2 = "--------"
    p_len = "----"

    if p_type == "PDM" or p_type == "POD":
        b9 = ord(data[9])
        p_len = "0x%02x" % (ord(data[10]) | (b9 & 3)<<8)
        p_addr2 = binascii.hexlify(data[5:9])
        p_unk1 = "0x%02x" % ((b9 & 0x3C) >> 2)
        p_unk2 = format((b9 >> 6), "#04b")
        p_body = binascii.hexlify(data[11:])
    elif p_type == "ACK":
        p_addr2 = binascii.hexlify(data[5:9])
        p_body = binascii.hexlify(data[9:])
    elif p_type == "CON":
        p_body = binascii.hexlify(data[5:])
    else:
        p_body = binascii.hexlify(data[5:])

    print("%s %s 0x%02x %s %s %s %s %s (0x%02x) %s" % (timestamp, p_type, p_seq, p_addr1, p_addr2, p_unk1, p_unk2, p_len, len(p_body)/2, p_body))

if __name__== "__main__":
  main()