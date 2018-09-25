#!/usr/bin/python

import threading
import datetime
from podcomm.sniffer import Sniffer
import sys


def main():
    p = Sniffer(pktHandler, messageHandler, errorHandler)
    p.start()
    print "Started press any key to exit"
    raw_input()
    print "Exiting"
    p.stop()
    print "Done"

def pktHandler(packet):
    print packet
    file = open("omni_packets.log","a")
    file.write(str(packet)+"\n") 
    file.close() 

def messageHandler(message):
    print message
    file = open("omni_messages.log","a")
    file.write(str(message)+"\n") 
    file.close() 

def errorHandler(errstr):
    print errstr
    file = open("omni_errors.log","a")
    file.write(str(errstr)+"\n") 
    file.close() 

if __name__== "__main__":
  main()