#!/usr/bin/python3
import logging
import sys
from decimal import *

from podcomm.pdm import Pdm
from podcomm.pod import Pod

logging.basicConfig(level=logging.DEBUG)

pod = Pod.Load(sys.argv[1])
pdm = Pdm(pod)

amount = Decimal(sys.argv[2])

print("\nStarting bolus of %.2f units\n" % amount)


pdm.bolus(amount, False)

