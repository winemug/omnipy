import simplejson as json
import time
import os

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1


def get_now():
    return int(time.time() * 1000)


os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/omnipy/google-settings.json"
subscriber = pubsub_v1.SubscriberClient()
sub_topic_path = subscriber.topic_path('omnicore17', 'py-rsp')
subscription_path = subscriber.subscription_path('omnicore17', 'sub-pyrsp-tmop')
try:
    subscriber.create_subscription(subscription_path, sub_topic_path, ack_deadline_seconds=10)
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
publish_topic = publisher.topic_path('omnicore17', 'py-cmd')


def get_response(req: {}) -> {}:
    print(f'Sending request: {req}')
    publisher.publish(publish_topic, json.dumps(req).encode('UTF-8'))

    print(f"Waiting for response")
    while True:
        response = subscriber.pull(subscription_path, max_messages=100)

        for msg in response.received_messages:
            rsp = json.loads(bytes.decode(msg.message.data, encoding='UTF-8'))
            rsp_req = rsp['request']
            if rsp_req['id'] == req['id']:
                print(f'!matched: {msg}')
                subscriber.acknowledge(subscription_path, ack_ids=[msg.ack_id])
                return rsp
            else:
                print(f'no match: {rsp_req["id"]}')
                subscriber.acknowledge(subscription_path, ack_ids=[msg.ack_id])
                # subscriber.modify_ack_deadline(subscription_path, [msg.ack_id], 0)


def get_last_state() -> int:
    response = get_response({
        'type': 'last_status',
        'id': get_now(),
        'expiration': None,
        'state': None
    })
    return response['state']


def status():
    return get_response({
        'type': 'update_status',
        'id': get_now(),
        'expiration': get_now() + 120 * 1000,
        'state': get_last_state(),
    })


def bolus(ticks: int, interval: int):
    return get_response(
        {
            'type': 'bolus',
            'id': get_now(),
            'expiration': None,
            'state': get_last_state(),
            'parameters': {
                'ticks': ticks,
                'interval': interval
            }
        })


print(get_response({
    'type': 'cancel_temp_basal',
    'id': get_now(),
    'expiration': get_now() + 120 * 1000,
    'state': None,
}))
subscriber.close()
publisher.stop()
