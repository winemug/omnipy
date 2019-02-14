#!/usr/bin/python3
from podcomm.pod import Pod
from podcomm.pdm import Pdm
from podcomm.pdmutils import PdmError
import logging
import sys
import time
from decimal import *

logging.basicConfig(level=logging.DEBUG)

pod = Pod.Load(sys.argv[1])
pdm = Pdm(pod)

amount = Decimal(sys.argv[2])

print("\nStarting bolus of %.2f units\n" % (amount))


try:
    pdm.bolus(amount, False)
    print("Bolus started status:")
    pdm.updatePodStatus()
    print(pdm.pod)
except PdmError as e:
    pdm.updatePodStatus()

print("\n\nBolusing %.2f units\n\nPress ctrl+c to cancel\n\n" % (amount))

try:
    while True:
        print("Getting interim status")
        pdm.updatePodStatus()
        print(pdm.pod)
        if pdm.pod.bolusState != 2:
            break
        time.sleep(5)

except KeyboardInterrupt:
    print("\nCancelling bolus...\n")
    pdm.cancelBolus()

print("Getting final status")

pdm.updatePodStatus()
print(pdm.pod)

pdm.cleanUp()

print(pdm.pod)