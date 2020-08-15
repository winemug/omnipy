#!/home/pi/v/bin/python3
import time
import signal
from threading import Event, Lock
from google.api_core.exceptions import AlreadyExists, DeadlineExceeded
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.proto.pubsub_pb2 import PubsubMessage, ReceivedMessage
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


def ntp_update():
    os.system('sudo systemctl stop ntp')
    os.system('sudo ntpd -gq')
    os.system('sudo systemctl start ntp')


def restart():
    os.system('shutdown -r now')


def shutdown():
    os.system('shutdown -h now')


class MqOperator(object):
    def __init__(self):
        configureLogging()
        self.logger = getLogger(with_console=True)
        get_packet_logger(with_console=True)
        self.logger.info("mq operator is starting")

        with open("settings.json", "r") as stream:
            self.settings = json.load(stream)

        self.i_pdm: Pdm = None
        self.i_pod: Pod = None
        self.g_pdm: Pdm = None
        self.g_pod: Pod = None

        self.insulin_bolus_pulse_interval = 4
        self.next_pdm_run = time.time()

        self.exit_event = Event()
        self.stop_event = Event()
        self.requests = []
        self.executed_req_ids = []

        subscriber = pubsub_v1.SubscriberClient()
        sub_topic_path = subscriber.topic_path('omnicore17', 'py-cmd')
        subscription_path = subscriber.subscription_path('omnicore17', 'sub-pycmd-mqop')
        try:
            subscriber.create_subscription(subscription_path, sub_topic_path, ack_deadline_seconds=10)
        except AlreadyExists:
            pass

        publisher = pubsub_v1.PublisherClient(
            # batch_settings=pubsub_v1.types.BatchSettings(
            #     max_bytes=4096,
            #     max_latency=5,
            # ),
            # client_config={
            #     "interfaces": {
            #         "google.pubsub.v1.Publisher": {
            #             "retry_params": {
            #                 "messaging": {
            #                     'total_timeout_millis': 60000,  # default: 600000
            #                 }
            #             }
            #         }
            #     }
            # },
            # publisher_options=pubsub_v1.types.PublisherOptions(
            #     flow_control=pubsub_v1.types.PublishFlowControl(
            #         message_limit=1000,
            #         byte_limit=1024 * 64,
            #         limit_exceeded_behavior=pubsub_v1.types.LimitExceededBehavior.BLOCK,
            #     ))
        )

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

            while True:
                self.pull_messages()
                if self.exit_event.is_set():
                    break
                self.process_requests()

        except Exception:
            raise
        finally:
            self.subscriber.close()
            self.publisher.stop()
            self.stop_event.set()

    def pull_messages(self):
        while True:
            try:
                response = self.subscriber.pull(self.subscription_path, max_messages=5, timeout=3)
            except DeadlineExceeded:
                break

            if self.exit_event.is_set():
                break
            for received_msg in response.received_messages:
                self.process_message(received_msg)
                if self.exit_event.is_set():
                    break

    def process_message(self, received_msg: ReceivedMessage):
        message = received_msg.message
        try:
            new_request = get_json(message.data)
            new_request['req_msg_id'] = message.message_id
            new_request['req_msg_ack_id'] = received_msg.ack_id
            new_request['req_msg_publish_time'] = message.publish_time.seconds * 1000 + message.publish_time.nanos

            if new_request['id'] in self.executed_req_ids\
                    or new_request['req_msg_id'] in [r['req_msg_id'] for r in self.requests]:
                self.ack(received_msg.ack_id)
            else:
                self.logger.debug(f'new request received, type: {new_request["type"]}, id: {new_request["id"]}')
                self.requests.append(new_request)

        except Exception as e:
            self.logger.error("Error parsing message in callback", e)
            self.nack(received_msg.ack_id)

    def process_requests(self):
        while True:
            self.filter_expired()
            self.filter_outdated()
            self.filter_redundant()
            self.sort_requests()

            if len(self.requests) > 0:
                req = self.requests[0]
                self.requests = self.requests[1:]
                self.executed_req_ids.append(req['id'])
            else:
                break

            self.ack(req["req_msg_ack_id"])
            try:
                self.perform_request(req)
                self.send_response(req, "success")
            except Exception as e:
                self.logger.error("Error performing request", e)
                self.send_response(req, "fail")

    def filter_expired(self):
        not_expired = []
        for req in self.requests:
            if "expiration" in req and req["expiration"] is not None:
                expiration = int(req["expiration"])
            else:
                expiration = int(req["req_msg_publish_time"]) + 90 * 1000
            if get_now() > expiration:
                self.ack(req["req_msg_ack_id"])
                self.send_response(req, "expired")
            else:
                not_expired.append(req)
        self.requests = not_expired

    def filter_outdated(self):
        up_to_date = []
        pod = self.i_pod.__dict__
        for req in self.requests:
            if "state" in req and req["state"] is not None:
                last_state = int(pod["state_last_updated"] * 1000)
                if req["state"] != last_state:
                    self.ack(req["req_msg_ack_id"])
                    self.send_response(req, "outdated")
                    continue

            up_to_date.append(req)
        self.requests = up_to_date

    def filter_redundant(self):
        non_redundant = []
        types = {}

        self.requests.sort(key=lambda r: r['req_msg_publish_time'],
                           reverse=True)
        for req in self.requests:
            req_type = req["type"]
            if req_type in types:
                self.ack(req["req_msg_ack_id"])
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
        request_copy.pop('req_msg_id')
        request_copy.pop('req_msg_ack_id')
        request_copy.pop('req_msg_publish_time')
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
        elif req_type == "deactivate":
            self.i_pdm.deactivate_pod()
        elif req_type == "update_time":
            ntp_update()
        elif req_type == "restart":
            restart()
        elif req_type == "shutdown":
            shutdown()
        else:
            raise InvalidOperation

    def ack(self, ack_id):
        self.subscriber.acknowledge(self.subscription_path, [ack_id])

    def nack(self, ack_id):
        self.subscriber.modify_ack_deadline(self.subscription_path, [ack_id], 0)


def _exit_with_grace(mqo: MqOperator):
    mqo.exit_event.set()
    mqo.stop_event.wait()


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
