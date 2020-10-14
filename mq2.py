#!/home/pi/v/bin/python3
import time
import signal
from threading import Event, Lock
from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.proto.pubsub_pb2 import PubsubMessage
from podcomm.pdm import Pdm
from podcomm.pod import Pod
from podcomm.definitions import *
import simplejson as json
from decimal import *


def get_now():
    return int(time.time() * 1000)


def get_ticks(d: Decimal) -> int:
    return int(round(d / Decimal("0.05")))


def ticks_to_decimal(ticks: int) -> Decimal:
    return Decimal("0.05") * ticks


def seconds_to_hours(minutes: int) -> Decimal:
    return Decimal(minutes) / Decimal("3600")


def is_expired(req):
    if "expiration" in req and req["expiration"] is not None:
        expiration = int(req["expiration"])
        if get_now() > expiration:
            return True
    return False


def status_match(req, pod):
    if "pod_updated" in req and req["pod_updated"] is not None:
        return req["pod_updated"] == int(pod["state_last_updated"] * 1000)


def get_json(message_data):
    return json.loads(bytes.decode(message_data, encoding='UTF-8'))


class MqOperator(object):
    def __init__(self):
        configureLogging()
        self.logger = getLogger(with_console=True)
        get_packet_logger(with_console=True)
        self.logger.info("mq operator is starting")

        with open("settings.json", "r") as stream:
            self.settings = json.load(stream)

        self.i_pdm = None
        self.i_pod = None
        self.g_pdm = None
        self.g_pod = None

        self.decimal_zero = Decimal("0")
        self.i_rate_requested = None
        self.i_rate_duration_requested = None
        self.i_bolus_requested = self.decimal_zero
        self.g_rate_requested = None
        self.g_bolus_requested = self.decimal_zero

        self.started = time.time()
        self.insulin_bolus_pulse_interval = 4
        self.next_pdm_run = time.time()

        self.message_event = Event()
        self.exit_event = Event()
        self.stop_event = Event()
        self.requests_lock = Lock()
        self.requests = []

        subscriber = pubsub_v1.SubscriberClient()
        sub_topic_path = subscriber.topic_path('omnicore17', 'py-cmd')
        subscription_path = subscriber.subscription_path('omnicore17', 'sub-pycmd-mqop')
        try:
            subscriber.create_subscription(subscription_path, sub_topic_path, ack_deadline_seconds=600)
        except AlreadyExists:
            pass

        publisher = pubsub_v1.PublisherClient(
            batch_settings=pubsub_v1.types.BatchSettings(
                max_bytes=4096,
                max_latency=5,
            ),
            client_config={
                "interfaces": {
                    "google.pubsub.v1.Publisher": {
                        "retry_params": {
                            "messaging": {
                                'total_timeout_millis': 60000,  # default: 600000
                            }
                        }
                    }
                }
            },
            publisher_options=pubsub_v1.types.PublisherOptions(
                flow_control=pubsub_v1.types.PublishFlowControl(
                    message_limit=1000,
                    byte_limit=1024 * 64,
                    limit_exceeded_behavior=pubsub_v1.types.LimitExceededBehavior.BLOCK,
                )))

        self.subscriber = subscriber
        self.publisher = publisher
        self.subscription_path = subscription_path
        self.subscription_future = None
        self.publish_future = None
        self.publish_path = self.publisher.topic_path('omnicore17', 'py-rsp')

    def run(self):
        try:
            self.i_pod = Pod.Load("/home/pi/omnipy/data/pod.json", "/home/pi/omnipy/data/pod.db")
            self.i_pdm = Pdm(self.i_pod)
            self.i_pdm.start_radio()

            self.subscription_future = self.subscriber.subscribe(self.subscription_path,
                                                                 callback=self.subscription_callback,
                                                                 # scheduler=ThreadScheduler(
                                                                 #     executor=ThreadPoolExecutor(max_workers=2))
                                                                 )
            while True:
                if self.message_event.wait(5):
                    time.sleep(5)

                if self.exit_event.is_set():
                    break
                if self.message_event.is_set():
                    self.process_requests()

        except Exception:
            raise
        finally:
            self.subscriber.close()
            self.publisher.stop()
            self.stop_event.set()

    def subscription_callback(self, message: PubsubMessage):
        try:
            new_request = get_json(message.data)
            new_request['message'] = message

            with self.requests_lock:
                for request in self.requests:
                    if request['message'].message_id == message.message_id\
                            or request['id'] == new_request['id']:
                        message.ack()
                        break
                else:
                    self.requests.append(new_request)
                    self.message_event.set()
        except Exception as e:
            self.logger.error("Error parsing message in callback", e)
            message.nack()

    def process_requests(self):
        with self.requests_lock:
            self.message_event.clear()
            self.filter_expired()
            self.filter_outdated()
            self.filter_redundant()
            self.sort_requests()

            if len(self.requests) > 0:
                req = self.requests[0]
                msg = req['message']
                try:
                    self.perform_request(req)
                except Exception as e:
                    self.logger.error("Error performing request", e)
                    msg.nack()
                    self.send_response(req, "fail")
                    return

                msg.ack()
                self.send_response(req, "success")

    def filter_expired(self):
        not_expired = []
        for req in self.requests:
            msg = req['message']
            if "expiration" in req and req["expiration"] is not None:
                expiration = int(req["expiration"])
            else:
                expiration = int(msg.publish_time.timestamp() * 1000) + 60 * 1000
            if get_now() > expiration:
                msg.ack()
                self.send_response(req, "expired")
            else:
                not_expired.append(req)
        self.requests = not_expired

    def filter_outdated(self):
        up_to_date = []
        pod = self.i_pod.__dict__
        for req in self.requests:
            msg = req['message']
            if "state" in req and req["state"] is not None:
                last_state = int(pod["state_last_updated"] * 1000)
                if req["state"] != last_state:
                    msg.ack()
                    self.send_response(req, "outdated")
                    continue

            up_to_date.append(req)
        self.requests = up_to_date

    def filter_redundant(self):
        non_redundant = []
        types = {}

        self.requests.sort(key=lambda r: r['message'].publish_time.timestamp(), reverse=True)
        for req in self.requests:
            msg = req['message']
            req_type = req["type"]
            if req_type in types:
                msg.ack()
                self.send_response(req, "redundant")
                continue

            non_redundant.append(req)
            types[req_type] = None
        self.requests = non_redundant

    def sort_requests(self):
        for req in self.requests:
            if "priority" not in req:
                req["priority"] = -1

        self.requests.sort(key=lambda r: r['priority'], reverse=True)

    def send_response(self, request: dict, result: str):
        self.logger.debug(f'responding to request {request["id"]}: {result}')
        request_copy = request.copy()
        request_copy.pop('message')
        response = {
            'request': request_copy,
            'result': result,
            'state': int(self.i_pod.__dict__["state_last_updated"] * 1000),
            'pod': self.i_pod.__dict__
        }
        self.publisher.publish(self.publish_path, json.dumps(response).encode('UTF-8'))

    def perform_request(self, req):
        self.logger.debug(f"performing request {req}")
        req_type = req["type"]

        if req_type == "last_status":
            return
        elif req_type == "update_status":
            self.i_pdm.update_status()
        elif req_type == "bolus":
            rp = req["parameters"]
            bolus_amount = ticks_to_decimal(int(rp["ticks"]))
            bolus_tick_interval = int(rp["interval"])
            self.i_pdm.bolus(bolus_amount, bolus_tick_interval)
        elif req_type == "temp_basal":
            rp = req["parameters"]
            basal_rate = ticks_to_decimal(int(rp["ticks"]))
            basal_duration = seconds_to_hours(int(rp["duration"]))
            self.i_pdm.set_temp_basal(basal_rate, basal_duration)
        else:
            raise InvalidOperation


def _exit_with_grace(operator: MqOperator):
    operator.exit_event.set()
    operator.stop_event.wait()


if __name__ == '__main__':
    exited = False
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/omnipy/google-settings.json"
    while not exited:
        operator = MqOperator()
        try:
            signal.signal(signal.SIGTERM, lambda a, b: _exit_with_grace(operator))
            operator.run()
            exited = True
        except Exception as e:
            print(f'error while running operator\n{e}')
            operator.exit_event.set()
            operator.stop_event.wait()
            time.sleep(10)
