#!/usr/bin/python
from podcomm.pod import Pdm
import binascii

def main():
  pdm = Pdm()
  pdm.start()
  raw_input()
  pdm.stop()

def msgHandler(msg):
  for ctype, content in msg.getContents():
    if ctype == 0x07:
      print ("Assign pod address request, address: %s" % binascii.hexlify(content))
    elif ctype == 0x0e: # status request
      print("Status request, content: %s" % binascii.hexlify(content))
    else:
      print ("Unknown message content, type: 0x%02X content: %s" % ctype, binascii.hexlify(content))


def errHandler():
  print "error"

if __name__== "__main__":
  main()