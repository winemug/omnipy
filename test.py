#!/usr/bin/python
from __future__ import absolute_import

from podcomm.pod import Pod
from podcomm.pdm import Pdm
from podcomm.radio import Radio, RadioMode
from podcomm.message import Message
from podcomm.nonce import Nonce
import logging
import time
from threading import Event

logging.basicConfig(level=logging.INFO)

pod = Pod(43962, 940182, 0x1f0e89f3)
pdm = Pdm(pod)

pdm.updatePodStatus()

print(pdm.pod)

cancelEvent = Event()
pdm.normalBolus(0.15, cancelEvent, confidenceReminder=False)

print(pdm.pod)

pdm.cleanUp()

