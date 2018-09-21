import binascii

class Packet():
    def __init__(self, timestamp, data):
        self.timestamp = timestamp
        self.data = data
        self.valid = False
        self.error = None
        if len(data) < 5:
            self.error = "Packet length too small"
            return

        self.address = binascii.hexlify(data[0:4])

        t = ord(data[4]) >> 5
        self.sequence = ord(data[4]) & 0b00011111

        if t == 5:
            self.type = "PDM"
        elif t == 7:
            self.type = "POD"
        elif t == 2:
            self.type = "ACK"
        elif t == 4:
            self.type = "CON"
        else:
            self.error = "Unknown packet type: 0b" + bin(t)
            return

        if self.type == "PDM" or self.type == "POD":
            if len(data) < 12:
                self.error = "Packet length too small for type " + self.type
                return
            self.body = data[9:]
            self.address2 = binascii.hexlify(data[5:9])
            if self.address2 == self.address:
                self.ackFinal = False
            elif self.address2 == "00000000":
                self.ackFinal = True
            else:
                self.error = "Address mismatch in packet"
                return
            self.valid = True
        elif self.type == "ACK":
            if len(data) != 9:
                self.error = "Incorrect packet length for type ACK"
                return
            self.address2 = binascii.hexlify(data[5:9])
            if self.address2 == self.address:
                self.ackFinal = False
            elif self.address2 == "00000000":
                self.ackFinal = True
            else:
                self.error = "Address mismatch in packet"
                return
            self.valid = True
        elif self.type == "CON":
            if len(data) < 6:
                self.error = "Packet length too small for type CON"
                return
            self.body = data[5:]
            self.valid = True

    def __str__(self):
        if self.valid:
            if self.type == "CON":
                return "%s Packet Type: %s Addr: %s                 Seq: 0x%02x Body: %s" % (self.timestamp, self.type, self.address, self.sequence, binascii.hexlify(self.body))
            elif self.type == "ACK":
                return "%s Packet Type: ACK Addr: %s Addr2: %s Seq: 0x%02x" % (self.timestamp, self.address, self.address2, self.sequence)
            else:
                return "%s Packet Type: %s Addr: %s Addr2: %s Seq: 0x%02x Body: %s" % (self.timestamp, self.type, self.address, self.address2, self.sequence, binascii.hexlify(self.body))
        else:
            return "%s Invalid packet. Error: %s Body: %s" % (self.timestamp, self.error, binascii.hexlify(self.data))