from podcomm.protocol_radio import RadioPacketType, RadioPacket
from podcomm.packet_radio import PacketRadio
from podcomm.pr_rileylink import RileyLink
from queue import Queue

class MockPacketRadio(PacketRadio):
    def __init__(self, send_callback=None, allow_connect=False, allow_listen=False):
        self.radio = RileyLink()
        self.response_packets = Queue()
        self.responses = Queue()
        self.last_pdm_message_sequence = 0
        self.last_pdm_packet_sequence = 0
        self.send_callback = send_callback
        self.allow_listen = allow_listen
        self.allow_connect = allow_connect

    def add_response(self, response, msg_address, pkt_address, critical):
        self.responses.put((response, msg_address, pkt_address, critical))

    def add_response_packet(self, response_packet):
        self.response_packets.put(response_packet)


    def connect(self, force_initialize=False):
        if self.allow_connect:
            return self.radio.connect(force_initialize=force_initialize)

    def disconnect(self, ignore_errors=True):
        if self.allow_connect:
            return self.radio.disconnect(ignore_errors=ignore_errors)

    def get_info(self):
        if self.allow_connect:
            return self.radio.get_info()

    def init_radio(self, force_init=False):
        if self.allow_connect:
            return self.radio.init_radio(force_init=force_init)

    def tx_up(self):
        if self.allow_connect:
            return self.radio.tx_up()

    def tx_down(self):
        if self.allow_connect:
            return self.radio.tx_down()

    def set_tx_power(self, tx_power):
        if self.allow_connect:
            return self.radio.set_tx_power(tx_power=tx_power)

    def _translate_responses(self):
        if self.response_packets.empty():
            if not self.responses.empty():
                msg, msg_address, pkt_address, critical = self.responses.get()
                packets = msg.get_radio_packets(msg_address, (self.last_pdm_message_sequence + 1) % 16,
                                          pkt_address, (self.last_pdm_packet_sequence + 1) % 32,
                                          critical)
                for packet in packets:
                    self.response_packets.put(packet)

    def get_packet(self, timeout=5.0):
        self._translate_responses()

        if not self.response_packets.empty():
            p = self.response_packets.get()
            if p is not None:
                return bytes([0xff, 0xff]) + p.get_data()

        if self.allow_listen:
            return self.radio.get_packet(timeout=timeout)
        else:
            return None

    def send_and_receive_packet(self, packet, repeat_count, delay_ms, timeout_ms, retry_count, preamble_ext_ms):
        send_packet = RadioPacket.parse(packet)
        self.last_pdm_packet_sequence = send_packet.sequence
        if send_packet.type == RadioPacketType.PDM:
            self.last_pdm_message_sequence = (send_packet.body[4] >> 2) & 0x0f
        self._translate_responses()
        if not self.response_packets.empty():
            p = self.response_packets.get()
            if p is not None:
                return bytes([0xff, 0xff]) + p.get_data()

        if self.allow_listen:
            packet = self.send_callback(packet)
            if packet is None:
                return None
            return self.radio.send_and_receive_packet(packet=packet,
                                                      repeat_count=repeat_count,
                                                      delay_ms=delay_ms,
                                                      timeout_ms=timeout_ms,
                                                      retry_count=retry_count,
                                                      preamble_ext_ms=preamble_ext_ms)
        else:
            return None

    def send_packet(self, packet, repeat_count, delay_ms, preamble_extension_ms):
        if self.allow_listen:
            packet = self.send_callback(packet)
            if packet is None:
                return None
            return self.radio.send_packet(packet=packet,
                                          repeat_count=repeat_count,
                                          delay_ms=delay_ms,
                                          preamble_extension_ms=preamble_extension_ms)
        else:
            return

