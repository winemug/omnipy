#!/usr/bin/python

import pdm
import threading
import podcomm/pdm
import podcomm/message
import datetime

def main():
    try:
        p = pdm.Pdm()
        p.start(messageHandler, True)
        raw_input()
        p.stop()
    except:
        print("something didn't work out quite alright")

def messageHandler(message):
    print message

if __name__== "__main__":
  main()