#!/usr/bin/python3
from podcomm.definitions import *
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from decimal import *
import struct
from podcomm.pdmutils import *
import time
from datetime import timedelta, datetime

def get_pod():
    return Pod.Load(POD_FILE + POD_FILE_SUFFIX, POD_FILE + POD_LOG_SUFFIX)


def get_pdm():
    return Pdm(get_pod())


def main():
    schedule = [Decimal("15.00")] * 48
    pdm = get_pdm()
    pdm.set_basal_schedule(schedule, hours=0, minutes=14, seconds=17)
    start_time = time.time()
    while not pdm.pod.state_faulted:
        time.sleep(30)
        pdm.updatePodStatus()
        if time.time() - start_time > 90*60:
            break

    if pdm.pod.state_faulted:
        pdm.deactivate_pod()


if __name__ == '__main__':
    main()
