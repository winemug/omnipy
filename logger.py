#!/usr/bin/python

import pdm
import threading
import podcomm/listener
import datetime

def main():
    try:
        r = listener.RFListener(0, processData)
        r.start()
        raw_input()
        r.stop()
    except:
        print("something didn't work out quite alright")

def processData(data, timestamp):
    t = datetime.datetime.utcfromtimestamp(timestamp)
    t = t.strftime("%Y-%m-%d %H:%M:%S.%f")
    print(t + " " + data.encode("hex"))

if __name__== "__main__":
  main()