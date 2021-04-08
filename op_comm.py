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

    def start(self, on_command_received=None, on_response_received=None):
        self.on_command_received = on_command_received
        self.on_response_received = on_response_received
        self.client.connect_async(self.host, port=self.port)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()

    def send_command(self, cmd: dict):
        self._send('omnipy/cmd', json.dumps(cmd))

    def send_response(self, rsp: dict):
        self._send('omnipy/rsp', json.dumps(rsp))

    def _send(self, topic: str, text: str):
        self.client.publish(topic, payload=text.encode(encoding='UTF-8'), qos=2)

    def _on_connect(self, client, userdata, flags, rc):
        print("OPC Connected with result code "+str(rc))
        if self.on_response_received is not None:
            client.subscribe("omnipy/rsp", qos=2)
        if self.on_command_received is not None:
            client.subscribe("omnipy/cmd", qos=2)

    def _on_message(self, client, userdata, msg):
        print('OPC Message received: ' + msg.topic + " " +str(msg.payload))
        if msg.topic == 'omnipy/rsp':
            if self.on_response_received is not None:
                self.on_response_received(json.loads(bytes.decode(msg.payload, encoding='UTF-8')))
        elif msg.topic == 'omnipy/cmd':
            if self.on_command_received is not None:
                self.on_command_received(json.loads(bytes.decode(msg.payload, encoding='UTF-8')))



