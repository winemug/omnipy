from omnipy_remote import OmniPyRemote
import simplejson as json
import os
from omnipy_response import parse_response_json
import time


class OmnipyRemoteClient:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.remote = OmniPyRemote('omnicore17', 'py-rsp', 'py-cmd', 'client-test3', db_path)

    def start(self):
        pass

    def stop(self):
        pass

def client_main():
    remote = OmniPyRemote('omnicore17', 'py-rsp', 'py-cmd', 'client-test3', '/home/pi/omnipy/client-pubsub.db')
    remote.start()

    while True:
        if remote.incoming_message_event.wait(timeout=5):
            messages = remote.get_messages()
            for msg in messages:
                msg_id = None
                try:
                    msg_id = msg['id']
                    received = msg['receive_time']
                    published = msg['publish_time']
                    message = bytes.decode(msg['message'], encoding='UTF-8')
                    js = json.loads(message)
                    response = parse_response_json(js)
                except Exception as e:
                    print(f'error parsing message\n{e}')
                    if msg_id is not None:
                        remote.mark_as_read([msg_id])

                try:
                    self.record_response(response)
                except Exception as e:
                    pass


    remote.stop()


if __name__ == "__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/omnipy/google-settings.json"
    client = OmnipyRemoteClient('home/pi/omnipy/client-pubsub.db')

    client.start()

    time.sleep(10)

    client.stop()
