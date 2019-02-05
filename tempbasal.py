#!/usr/bin/python3
from podcomm.pod import Pod
from podcomm.pdm import Pdm
import logging
import sys
from decimal import *

logging.basicConfig(level=logging.DEBUG)

pod = Pod.Load(sys.argv[1])
pdm = Pdm(pod)

amount = Decimal(sys.argv[2])
hours = Decimal(sys.argv[3])

print("\nSetting temp basal of %.2f units for %.1f hours\n" % (amount, hours))

pdm.setTempBasal(amount, hours, False)
pdm.cleanUp()

print(pdm.pod)