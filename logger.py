#!/usr/bin/python

import threading
import datetime
from podcomm.protocol import Protocol, ProtocolEmulation

def main():
    p = Protocol(messageHandler, protocolEmulation = ProtocolEmulation.Sniffer)
    p.start()
    
    raw_input()
    p.stop()

def messageHandler(message):
    print message

if __name__== "__main__":
  main()