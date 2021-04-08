import time

from podcomm.definitions import configureLogging, getLogger, get_packet_logger
from podcomm.pdm import Pdm
from podcomm.pr_dongle import TIDongle
from podcomm.protocol_radio import PdmRadio

configureLogging()
logger = getLogger(with_console=True)
get_packet_logger(with_console=True)

radio = PdmRadio(0x0)
while True:
    pkt = radio.get_packet(10.0)
    if pkt is not None:
        print(pkt)

