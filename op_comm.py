import ssl
import simplejson as json
import paho.mqtt.client as mqtt


class OmnipyCommunicator:
    def __init__(self,
                 host: str, port: int, client_id: str, tls: bool):
        self.client = mqtt.Client(client_id=client_id, clean_session=False)
        if tls:
            self.client.tls_set_context(ssl.create_default_context())
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.host = host
        self.port = port
        self.on_command_received = None
        self.on_response_received = None
        self.on_notification_received = None

    def start(self, on_command_received=None, on_response_received=None, on_notification_received=None):
        self.on_command_received = on_command_received
        self.on_response_received = on_response_received
        self.on_notification_received = on_notification_received
        self.client.connect_async(self.host, port=self.port, keepalive=120)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()

    def send_command(self, cmd: dict):
        self._send('omnipy/cmd', json.dumps(cmd))

    def send_response(self, rsp: dict):
        self._send('omnipy/rsp', json.dumps(rsp))

    def send_notification(self, msg: dict):
        self._send('omnipy/ntf', json.dumps(msg))

    def _send(self, topic: str, text: str):
        self.client.publish(topic, payload=text.encode(encoding='UTF-8'), qos=1)

    def _on_connect(self, client, userdata, flags, rc):
        #print("Connected with result code "+str(rc))
        if self.on_response_received is not None:
            client.subscribe("omnipy/rsp", qos=1)
        if self.on_command_received is not None:
            client.subscribe("omnipy/cmd", qos=1)
        if self.on_notification_received is not None:
            client.subscribe("omnipy/ntf", qos=1)

    def _on_message(self, client, userdata, msg):
        #print(msg.topic+" "+str(msg.payload))
        if msg.topic == 'omnipy/rsp':
            if self.on_response_received is not None:
                self.on_response_received(json.loads(bytes.decode(msg.payload, encoding='UTF-8')))
        elif msg.topic == 'omnipy/cmd':
            if self.on_command_received is not None:
                self.on_command_received(json.loads(bytes.decode(msg.payload, encoding='UTF-8')))
        elif msg.topic == 'omnipy/ntf':
            if self.on_notification_received is not None:
                self.on_notification_received(json.loads(bytes.decode(msg.payload, encoding='UTF-8')))


def main():
    import time

    def cmd_received(cmd: dict):
        print(f'cmd: {json.dumps(cmd)}')

    def rsp_received(rsp: dict):
        print(f'rsp: {json.dumps(rsp)}')

    def ntf_received(msg: dict):
        print(f'ntf: {json.dumps(msg)}')

    opc = OmnipyCommunicator('pamuk.balya.net', 7771, 'opa-test-cl1-f', tls=True)
    opc.start(on_command_received=cmd_received,
              on_response_received=rsp_received,
              on_notification_received=ntf_received)

    while True:
        # opc.send_command(dict(type='noop'))
        # opc.send_notification(dict(type='test'))
        time.sleep(1)


if __name__ == '__main__':
    main()
