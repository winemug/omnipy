#!/usr/bin/python

import pdm
import threading

def main():
    
    #todo: options:
    # 1) initialize new pod
    # 2) choose existing pdm session on disk
    # 3) .. previously paired pod

    lot = int(raw_input("Please enter the lot id of the pod: "))
    tid = int(raw_input("Please enter tid of the pod: "))
    print("Starting the PDM emulator")
    emulator = pdm.pdm(lot, tid)
    emulator.startObservation()
    print("Perform an insulin delivery related operation within the next 60 seconds on the real pdm")

    if not emulator.parametersObserved.wait(60):
        print("Error: Necessary parameters for the emulator were NOT observed.")
        return

    print("Gathered enough information to emulate the PDM.")
    print("Please shut down the PDM and press ENTER to continue")

    raw_input()
    emulator.stopObservation()

    print("\n\n\n*** Did you turn off the Omnipod PDM? ***\n\n")
    response = raw_input("Type \'YES\' in capital letters to continue): ")

    if response == "YES":
        while displayMenu():
            pass

    print("Goodbye then.")

def displayMenu():
    print("\n\n\n OmniPod PDM Emulator Commands:\n\n")
    print("1 - Deliver bolus")
    print("2 - Stop insulin delivery")

    print("\n0 - Exit\n")
    cmd = raw_input("Enter command to continue: ")
    if cmd == '0':
        return False
    if cmd == '1':
        pass
    if cmd == '2':
        pass

    print("Unknown command!")
    return True

if __name__== "__main__":
  main()