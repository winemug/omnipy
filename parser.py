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
            timestamp = "<date/time unknown>"
            if len(line) <= 26 or line[26] != ' ':
                data = line[0:len(line)-1].decode("hex")
            else:
                timestamp = line[0:26]
                data = line[27:len(line)-1].decode("hex")
            decode(data, timestamp)

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

    p_seq2 = 0xff
    b9 = ord(data[9])
    crcOK = False
    if p_type == "PDM" or p_type == "POD":
        remainingData = 0
        p_bodylen = ord(data[10]) | (b9 & 3)<<8
        p_addr2 = binascii.hexlify(data[5:9])
        p_seq2 = (b9 & 0x3C) >> 2
        if (p_bodylen > 23):
            if p_bodylen == 24:
                p_body = binascii.hexlify(data[11:35])
                remainingData = 0
            else:
                p_body = binascii.hexlify(data[11:36])
                remainingData = p_bodylen - 25
        else:
            p_crc16 = ord(data[11+p_bodylen]) << 8 | ord(data[12+p_bodylen])
            c_crc16 = crc16(data[5:11+p_bodylen])
            crcOK = p_crc16 == c_crc16
        if (crcOK):
            p_body = binascii.hexlify(data[11:11+p_bodylen])

    elif p_type == "ACK":
        p_addr2 = binascii.hexlify(data[5:9])
        p_bodylen = 0
        p_body = ""
    elif p_type == "CON":
        p_addr2 = ""
        if remainingData > 31:
            p_bodylen = 31
        else:
            p_bodylen = remainingData

        if p_bodylen > len(data) - 8:
            p_bodylen = len(data) - 8

        remainingData -= p_bodylen
        p_body = binascii.hexlify(data[6:6+p_bodylen])
    else:
        p_body = binascii.hexlify(data)
        p_bodylen = len(data)
        print(p_addr1, p_type, "0x%02x" % p_seq,  p_body)

    if crcOK:
        if lastSequences[p_t] == p_seq:
            return
        lastSequences[p_t] = p_seq
        print("%s %s %s 0x%02x 0x%02x 0x%02x %s" % (timestamp, p_addr1, p_type, p_seq, p_seq2, p_bodylen, p_body))
    else:
        print("%s %s %s 0x%02x 0x%02x 0x%02x %s <CRC ERROR>" % (timestamp, p_addr1, p_type, p_seq, p_seq2, p_bodylen, binascii.hexlify(data)))

if __name__== "__main__":
  main()