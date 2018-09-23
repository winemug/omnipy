#!/usr/bin/python

import threading
import datetime
from podcomm import pdm
from podcomm import message

def main():
    p = pdm.Pdm()
    p.start(messageHandler, True)
    
    raw_input()
    p.stop()

def messageHandler(message):
    print message

if __name__== "__main__":
  main()