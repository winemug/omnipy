import uuid
from pydantic import BaseModel


class PodModel(BaseModel):
    id: uuid
    active: bool
    radio_address: int
    message_sequence: int = 0
    packet_sequence: int = 0
    nonce: int
    seed: int


class PodMessage(BaseModel):
    id: int
    request_ts: float
    request_text: str
    request_data: bytearray
    response_ts: float
    response_text: str
    response_data: bytearray

