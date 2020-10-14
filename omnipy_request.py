from decimal import Decimal
import simplejson as json
import time

OC_RQ_SYS_ID = "sys_id"
OC_RQ_POD_ID = "pod_id"
OC_RQ_REQ_ID = "req_id"
OC_RQ_REQ_EXPIRY = "req_expiry"

OC_RQ_HEADER = "request"
OC_RQ_TYPE = "type"
OC_RQ_PARAMS = "params"
OC_RQ_PARAMS_LAST_STATUS = "last_status"

OC_RQ_TYPE_BOLUS = "bolus"
OC_RQ_PARAMS_BOLUS_AMOUNT = "amount"
OC_RQ_PARAMS_BOLUS_INTERVAL = "interval"

OC_RQ_TYPE_TEMP_BASAL = "temp_basal"
OC_RQ_PARAMS_TEMP_BASAL_RATE = "basal_rate"
OC_RQ_PARAMS_TEMP_BASAL_DURATION = "basal_duration"

OC_RQ_TYPE_STATUS = "status"
OC_RQ_TYPE_UPDATE_STATUS = "update_status"


def get_now():
    return int(time.time() * 1000)


class OmnipyRequest:
    def __init__(self, sys_id: str = None, pod_id: str = None, req_id: str = None, req_expiry: int = None):
        self.sys_id = sys_id
        self.pod_id = pod_id
        self.req_id = req_id
        self.req_expiry = req_expiry
        self.type = None
        self.bolus_amount = None
        self.bolus_interval = None
        self.temp_rate = None
        self.temp_duration = None
        self.last_status = None
        self.response = None

    def is_expired(self):
        if self.req_expiry is None:
            return False
        else:
            return get_now() >= self.req_expiry

    def get_priority(self) -> int:
        if self.type == OC_RQ_TYPE_TEMP_BASAL:
            return 3
        if self.type == OC_RQ_TYPE_BOLUS:
            return 2
        if self.type == OC_RQ_TYPE_UPDATE_STATUS:
            return 1
        if self.type == OC_RQ_TYPE_STATUS:
            return 0
        return -1


    def bolus(self, bolus_amount: Decimal, tick_interval: int, last_status: int, expiry_seconds: int = 60) -> str:
        ts_now = get_now()
        self.req_id = ts_now
        r = {
            OC_RQ_SYS_ID: self.sys_id,
            OC_RQ_POD_ID: self.pod_id,
            OC_RQ_TYPE: OC_RQ_TYPE_BOLUS,
            OC_RQ_REQ_ID: ts_now,
            OC_RQ_REQ_EXPIRY: ts_now + 1000*60,
            OC_RQ_PARAMS: {
                OC_RQ_PARAMS_BOLUS_AMOUNT: self.get_ticks(bolus_amount),
                OC_RQ_PARAMS_BOLUS_INTERVAL: tick_interval,
                OC_RQ_PARAMS_LAST_STATUS: last_status
            }
        }
        return json.dumps(r)

    def temp_basal(self, basal_rate: Decimal, duration_minutes: int, last_status: int,
                   expiry_seconds: int = 60) -> str:
        ts_now = get_now()
        self.req_id = ts_now
        r = {
            OC_RQ_SYS_ID: self.sys_id,
            OC_RQ_POD_ID: self.pod_id,
            OC_RQ_TYPE: OC_RQ_TYPE_TEMP_BASAL,
            OC_RQ_REQ_ID: ts_now,
            OC_RQ_REQ_EXPIRY: ts_now + 1000*expiry_seconds,
            OC_RQ_PARAMS: {
                OC_RQ_PARAMS_TEMP_BASAL_RATE: self.get_ticks(basal_rate),
                OC_RQ_PARAMS_TEMP_BASAL_DURATION: duration_minutes,
                OC_RQ_PARAMS_LAST_STATUS: last_status
            }
        }
        return json.dumps(r)

    def status(self):
        ts_now = get_now()
        self.req_id = ts_now

        r = {
            OC_RQ_SYS_ID: self.sys_id,
            OC_RQ_POD_ID: self.pod_id,
            OC_RQ_TYPE: OC_RQ_TYPE_STATUS,
            OC_RQ_REQ_ID: ts_now,
        }
        return json.dumps(r)

    def update_status(self, last_status: int, expiry_seconds: int = 60):
        ts_now = get_now()
        self.req_id = ts_now
        r = {
            OC_RQ_SYS_ID: self.sys_id,
            OC_RQ_POD_ID: self.pod_id,
            OC_RQ_TYPE: OC_RQ_TYPE_UPDATE_STATUS,
            OC_RQ_REQ_ID: ts_now,
            OC_RQ_REQ_EXPIRY: ts_now + 1000 * expiry_seconds,
            OC_RQ_PARAMS: {
                OC_RQ_PARAMS_LAST_STATUS: last_status
            }
        }
        return json.dumps(r)


def get_ticks(d: Decimal) ->int:
    return int(round(d / Decimal("0.05")))


def get_decimal(ticks: int) -> Decimal:
    return Decimal("0.05") * ticks


def parse_request_json(js: dict) -> OmnipyRequest:
    r = OmnipyRequest()
    r.sys_id = js[OC_RQ_SYS_ID]
    r.pod_id = js[OC_RQ_POD_ID]
    r.type = js[OC_RQ_TYPE]
    r.req_id = js[OC_RQ_REQ_ID]
    if OC_RQ_REQ_EXPIRY in js:
        r.req_expiry = js[OC_RQ_REQ_EXPIRY]

    if OC_RQ_PARAMS in js:
        p = js[OC_RQ_PARAMS]
        if r.type == OC_RQ_TYPE_BOLUS:
            r.bolus_amount = get_decimal(p[OC_RQ_PARAMS_BOLUS_AMOUNT])
            r.bolus_interval = p[OC_RQ_PARAMS_BOLUS_INTERVAL]
            r.last_status = p[OC_RQ_PARAMS_LAST_STATUS]
        elif r.type == OC_RQ_TYPE_TEMP_BASAL:
            r.temp_rate = get_decimal(p[OC_RQ_PARAMS_TEMP_BASAL_RATE])
            r.temp_duration = p[OC_RQ_PARAMS_TEMP_BASAL_DURATION]
            r.last_status = p[OC_RQ_PARAMS_LAST_STATUS]
        elif r.type == OC_RQ_TYPE_UPDATE_STATUS:
            r.last_status = p[OC_RQ_PARAMS_LAST_STATUS]
        elif r.type == OC_RQ_TYPE_STATUS:
            pass
    return r
