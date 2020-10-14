from decimal import Decimal
import simplejson as json
import time

OC_RP_SYS_ID = "sys_id"
OC_RP_POD_ID = "pod_id"
OC_RP_REQ_ID = "req_id"
OC_RP_RESULT = "result"
OC_RP_TIME = "time"
OC_RP_POD_JSON = "pod_json"

OC_RP_RESULT_SUCCESS = "success"
OC_RP_RESULT_EXPIRED = "expired"
OC_RP_RESULT_REDUNDANT = "redundant"
OC_RP_RESULT_FAILED = "failed"
OC_RP_RESULT_STATUS_MISMATCH = "mismatch"


def get_now():
    return int(time.time() * 1000)


class OmnipyResponse:
    def __init__(self, sys_id: str = None, pod_id: str = None, req_id: str = None,
                 response_result: str = None,
                 pod_json: dict = None):
        self.sys_id = sys_id
        self.pod_id = pod_id
        self.req_id = req_id
        self.response_time = get_now()
        self.response_result = response_result
        self.pod_json = pod_json

    def as_json_str(self) -> str:
        r = {
            OC_RP_SYS_ID: self.sys_id,
            OC_RP_POD_ID: self.pod_id,
            OC_RP_REQ_ID: self.req_id,
            OC_RP_RESULT: self.response_result,
            OC_RP_TIME: self.response_time,
            OC_RP_POD_JSON: self.pod_json,
        }
        return json.dumps(r)


def parse_response_json(js: dict) -> OmnipyResponse:
    r = OmnipyResponse()
    r.sys_id = js[OC_RP_SYS_ID]
    r.pod_id = js[OC_RP_POD_ID]
    r.req_id = js[OC_RP_REQ_ID]
    r.response_result = js[OC_RP_RESULT]
    r.response_time = js[OC_RP_TIME]
    r.pod_json = js[OC_RP_POD_JSON]
    return r