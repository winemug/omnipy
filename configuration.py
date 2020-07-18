class OmnipyConfiguration(object):
    def __init__(self):
        self.mqtt_host = ""
        self.mqtt_port = 1883
        self.mqtt_clientid = ""
        self.mqtt_command_topic = ""
        self.mqtt_response_topic = ""
        self.mqtt_json_topic = ""
        self.mqtt_sync_request_topic = ""
        self.mongo_url = ""
        self.mongo_collection = ""