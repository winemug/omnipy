from podcomm.pdm import Pdm
from podcomm.protocol import *
from podcomm.pod import Pod

def get_pod():
    path = "data/bbe.json"
    log_path = "data/bbe.log"
    pod = None

    try:
        pod = Pod.Load(path)
    except:
        pass

    if pod is None:
        pod = Pod()
        pod.path = path
        pod.log_file_path = log_path
        pod.id_lot = 44147
        pod.id_t = 1100256
        pod.radio_address = 0x1f0e89f0
        pod.Save()

    return pod

def main():
    schedule = [Decimal("2.75")] * 3
    schedule += [Decimal("1.25")] * 3
    schedule += [Decimal("1.75")] * 3
    schedule += [Decimal("0.05")] * 3
    schedule += [Decimal("0.35")] * 3
    schedule += [Decimal("1.95")] * 3
    schedule += [Decimal("1.05")] * 3
    schedule += [Decimal("0.05")] * 3
    schedule += [Decimal("1.65")] * 3
    schedule += [Decimal("0.85")] * 3
    schedule += [Decimal("14.95")] * 3
    schedule += [Decimal("30.00")] * 3
    schedule += [Decimal("0.15")] * 3
    schedule += [Decimal("1.05")] * 3
    schedule += [Decimal("6.95")] * 3
    schedule += [Decimal("1.00")] * 3

    pdm = Pdm(get_pod())
    pdm.bolus(Decimal("0.15"))
    print(pdm.pod)

    pdm.get_radio().stop()

    # pdm.deactivate_pod()
    #
    # pdm.bolus(Decimal("0.25"))
    #
    # pdm.set_basal_schedule(schedule, hours=0, minutes=0, seconds=0)
    # start_time = time.time()
    # while not pdm.pod.state_faulted:
    #     time.sleep(30)
    #     pdm.updatePodStatus()
    #     if time.time() - start_time > 90*60:
    #         break
    #
    # if pdm.pod.state_faulted:
    #     pdm.deactivate_pod()


if __name__ == '__main__':
    main()
