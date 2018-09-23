#!/usr/bin/python

import sys
import datetime
import binascii
from argparse import ArgumentParser
from decoder import Decoder

def main():
    parser = ArgumentParser(description="parse omnipod packets.")
    parser.add_argument("filename", help="input file containing raw data")
    pargs = parser.parse_args()
    decoder = Decoder()

    with open(pargs.filename) as f:
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
            except:
                continue
            decoder.receivePacket(timestamp, data)

if __name__== "__main__":
  main()