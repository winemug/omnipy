#!/usr/bin/python3
import logging
import sys

from podcomm.pdm import Pdm
from podcomm.pod import Pod

logging.basicConfig(level=logging.DEBUG)

pod = Pod.Load(sys.argv[1])
pdm = Pdm(pod)

pdm.updatePodStatus()
print(pdm.pod)

    