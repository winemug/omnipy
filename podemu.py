#!/usr/bin/python
from podcomm.pod import Pod
import binascii

def main():
    pod = Pod(msgHandler, errHandler, 123456, 123456)
    pod.start()
    raw_input()
    pod.stop()

def msgHandler(msg):
    for ctype, content in msg.getContents():
        if ctype == 0x07:
             address = binascii.hexlify(content)
             print ("Assign pod address request, address: %s" % address)
        else:
            print ("Unknown message content, type: 0x%02X content: %s" % ctype, binascii.hexlify(content))



def errHandler():
    print "error"

if __name__== "__main__":
  main()