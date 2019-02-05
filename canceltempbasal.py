#!/usr/bin/python3
from podcomm.pod import Pod
from podcomm.pdm import Pdm
import logging
import sys

logging.basicConfig(level=logging.DEBUG)

pod = Pod.Load(sys.argv[1])
pdm = Pdm(pod)

pdm.cancelTempBasal()
pdm.cleanUp()

print(pdm.pod)