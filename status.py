#!/usr/bin/python3
from podcomm.pod import Pod
from podcomm.pdm import Pdm
import logging
import sys
import time

logging.basicConfig(level=logging.DEBUG)

pod = Pod.Load(sys.argv[1])
pdm = Pdm(pod)

pdm.updatePodStatus()
print(pdm.pod)

pdm.cleanUp()
    