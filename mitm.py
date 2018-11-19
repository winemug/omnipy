#!/usr/bin/python

# from podcomm.sniffer import Sniffer
# from podcomm.pdm import Pdm
from podcomm.radio import Radio, RadioMode
from podcomm.packet import Packet
from podcomm.message import Message
from podcomm.nonce import Nonce

import threading
import struct

def main():
    
    #todo: options:
    # 1) initialize new pod
    # 2) choose existing pdm session on disk
    # 3) .. previously paired pod

    parametersObserved = threading.Event()
    lot = int(raw_input("Please enter the lot id of the pod: "))
    tid = int(raw_input("Please enter tid of the pod: "))

    pe = PdmEmulator(lot, tid)

    pe.observe(parametersObserved)

    print("Perform an insulin delivery related operation within the next 60 seconds using the pdm")

    if not parametersObserved.wait(60):
        print("Error: Necessary parameters for the emulator were NOT observed.")
        return

    print("Gathered enough information to emulate the PDM.")
    print("Please shut down the PDM and press ENTER to continue")

    raw_input()
    pe.stop()

    print("\n\n\n*** Did you turn off the Omnipod PDM? ***\n\n")
    response = raw_input("Type \'YES\' in capital letters to continue): ")

    if response == "YES":
        pe.start()
        while displayMenu(pe):
            pass
        pe.stop()
    print("Goodbye then.")

def displayMenu(emulator):
    print("\n\n\n OmniPod PDM Emulator Commands:\n\n")
    print("1 - Request status")
    print("2 - Deliver bolus")

    print("\n0 - Exit\n")
    cmd = raw_input("Enter command to continue: ")
    if cmd == '0':
        return False
    if cmd == '1':
        emulator.requestStatus()
        return True
    if cmd == '2':
        pass

    print("Unknown command!")
    return True

class PdmEmulator:
    def __init__(self, lot, tid):
        self.lot = lot
        self.tid = tid
        self.nonceGenerator = Nonce(lot, tid)
        self.podAddress = None
        self.lastPacketSequence = -1
        self.lastMessageSequence = -1
        self.lastNonce = None
        self.msgUnknownBits = None

    def observe(self, observedEvent):
        self.observedEvent = observedEvent
        self.radio = Radio(0)
        self.radio.start(packetReceivedCallback = self.radioPacketCallback)

    def stop(self):
        self.radio.stop()

    def start(self):
        print("syncing nonce %08X" % self.lastNonce)
        self.nonceGenerator.sync(self.lastNonce)
        self.radio = Radio(0, msgSequence=(self.lastMessageSequence+1)% 16, pktSequence=(self.lastPacketSequence+1) %32)
        self.radio.start(radioMode=RadioMode.Pdm)

    def requestStatus(self):
        msg = Message(0, "PDM", podAddress, unknownBits, lastMessageSequence)
        msg.addContent(0x0e, "\00")
        print("Sending status request\n")
        response = radio.sendPdmMessageAndGetPodResponse(msg)
        print("Gotten response: %s\n" % response)

    def radioPacketCallback(self, packet):
        print("Packet %s" % packet)
        self.podAddress = packet.address
        self.lastPacketSequence = packet.sequence

        if packet.type == "PDM" or packet.type == "POD":
            msg = Message.fromPacket(packet)
            self.lastMessageSequence = msg.sequence
            self.msgUnknownBits = msg.unknownBits

            if msg.type == "PDM" and ord(msg.body[0]) == 0x1A:
                self.lastNonce = struct.unpack('>I',msg.body[2:6])

        if self.podAddress is not None and \
        self.lastPacketSequence is not None and \
        self.lastMessageSequence is not None and \
        self.msgUnknownBits is not None and \
        self.lastNonce is not None:
            self.observedEvent.set()

if __name__== "__main__":
  main()