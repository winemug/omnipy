#!/usr/bin/python3
from podcomm.pod import Pod
from podcomm.pdm import Pdm
from podcomm.pdmutils import PdmError
from podcomm.radio import ProtocolError
import logging
import sys

logging.basicConfig(level=logging.DEBUG)

pod = Pod.Load(sys.argv[1])
pdm = Pdm(pod)

try:
    pdm.cancelBolus()
except PdmError as ProtocolError:
    pdm.updatePodStatus()

print(pdm.pod)