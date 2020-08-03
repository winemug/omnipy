from decimal import Decimal

import simplejson as json

OC_BOLUS_BEHAVIOR_CANCEL_RUNNING = "cancel_running"
OC_BOLUS_BEHAVIOR_QUEUE_AFTER = "queue_after"
OC_BOLUS_BEHAVIOR_FAIL = "fail"

OC_RQ_SYS_ID = "sys_id"
OC_RQ_POD_ID = "pod_id"

OC_RQ_HEADER = "request"
OC_RQ_TYPE = "type"
OC_RQ_TYPE_BOLUS = "bolus"

OC_RQ_PARAMS = "params"
OC_RQ_PARAMS_BOLUS_AMOUNT = "amount"
OC_RQ_PARAMS_BOLUS_INTERVAL = "interval"
OC_RQ_PARAMS_BOLUS_BEHAVIOR = "behavior"

def bolus_request(sys_id: str, pod_id: str, bolus_amount: Decimal, tick_interval: int,
                  behavior: str) -> str:
    r = {
        OC_RQ_SYS_ID: sys_id,
        OC_RQ_POD_ID: pod_id,
        OC_RQ_TYPE: OC_RQ_TYPE_BOLUS,
    }
    return json.dumps(r)
