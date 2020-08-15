import time
from decimal import Decimal
import datetime as dt

from podcomm.definitions import configureLogging, getLogger, get_packet_logger
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from omnipy_podsession import PodSession, get_pod_session


def print_pod_status(ps: PodSession):
    ts_now = time.time()
    print(f"Id: {ps.pod_id}")
    print(f"Running {dt.timedelta(seconds=int(ts_now - ps.activation_ts))}")
    print(f"Remaining {dt.timedelta(seconds=80*60*60 + int(ps.activation_ts-ts_now))}")
    print("-------------------------------------")
    if len(ps.temp_basals) == 0 or ps.temp_basals[-1][1] < ts_now:
        print(f"Scheduled basal running at {ps.basal_rate * ps.precision:.2f}U/h")
    else:
        temp_start, temp_end, temp_rate = ps.temp_basals[-1]
        temp_rate = temp_rate * ps.precision
        temp_running_for = int(ts_now - temp_start)
        temp_remaining= int(temp_end - ts_now)

        print(f"Temp basal running at {temp_rate:.2f}U/h, active {dt.timedelta(seconds=temp_running_for)} / {dt.timedelta(seconds=temp_remaining+temp_running_for)}")

    if len(ps.boluses) == 0:
        print(f"Bolus not running")
    else:
        bolus_start, bolus_ticks, bolus_interval = ps.boluses[-1]
        bolus_amount = bolus_ticks * ps.precision
        bolus_end = bolus_ticks * bolus_interval + bolus_start
        if bolus_end <= ts_now:
            print(f"Bolus not running")
        else:
            bolus_remaining_time = int(bolus_end - ts_now)
            bolus_delivered = int((ts_now - bolus_start) / bolus_interval) * ps.precision
            bolus_remaining = bolus_amount - bolus_delivered
            print(f"Bolus running with interval {bolus_interval}s, delivered: {bolus_delivered:.2f}U / {bolus_amount:.2f}U, remaining {dt.timedelta(seconds=bolus_remaining_time)}")
    print("-------------------------------------")
    last_ts, last_minute, last_delivered, last_undelivered, last_reservoir = ps.last_entry
    print(f"Last status at {dt.datetime.fromtimestamp(last_ts):%d-%b %H:%M:%S}")
    print(f"Delivered at status time: {last_delivered:.2f}U")
    print(f"To deliver at status time: {last_undelivered:.2f}U")
    if last_reservoir <= 51.0:
        print(f"Remaining at status time: {last_reservoir:.2f}U")
    else:
        print(f"Remaining at status time: {200 - last_delivered - last_undelivered:.2f}U (estimated)")


configureLogging()
logger = getLogger(with_console=True)
get_packet_logger(with_console=True)

ps = get_pod_session("/home/pi/omnipy/data/pod.db")
# for text, ts, d, nd, r in ps.activity_log:
#     dts = dt.datetime.fromtimestamp(ts)
#
#     print(f'{dts:%d-%b %H:%M:%S} {d}\t{nd}\t{r}\t{text}')

print_pod_status(ps)

pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
pdm = Pdm(pod)
pdm.start_radio()
while True:
    try:
        pdm.update_status()
    except Exception as e:
        print(e)
    pdm.radio.packet_radio.init_radio(True)
pdm.stop_radio()


