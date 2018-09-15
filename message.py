
from enum import Enum

class MessageOrigin(Enum):
    PDM = 0,
    POD = 1

class Message:
    def __init__(self, address, origin, length, data = ""):
        self.address = address
        self.origin = origin
        self.data = data
        self.length = length

    
    