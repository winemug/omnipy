from crc import crc16_table

class Nonce:
    def __init__(self, lot, tid, lastNonce = None):
        self.lot = lot
        self.tid = tid
        self.lastNonce = lastNonce
        self._initialize()

    def getNext(self):
        nonce = self.table[self.ptr]
        self.table[self.ptr] = self._generate()
        self.ptr = (nonce & 0xF) + 2
        self.lastNonce = nonce
        return nonce

    def sync(self, syncWord, msgSequence):
        print("nonce syncing with word 0x%4X and sequence 0x%2X" % (syncWord, msgSequence))
        sum = (self.lastNonce & 0xFFFF) + (crc16_table[msgSequence] & 0xFFFF) + (self.lot & 0xFFFF) + (self.tid & 0xFFFF)
        seed = (sum & 0xFFFF) ^ syncWord
        self._initialize(seed)

    # def sync(self, nonceToSync):
    #     nonce = None
    #     i = 0
    #     while nonce != nonceToSync:
    #         nonce = self.getNext()
    #         i += 1
    #         if i > 30000:
    #             print("nonce not found, sure about lot and tid?")
    #             break
    #     else:
    #         print("found! index: %d" % i)

    def _generate(self):
        self.table[0] = ((self.table[0] >> 16) + (self.table[0] & 0xFFFF) * 0x5D7F) & 0xFFFFFFFF
        self.table[1] = ((self.table[1] >> 16) + (self.table[1] & 0xFFFF) * 0x8CA0) & 0xFFFFFFFF
        return (self.table[1] + (self.table[0] << 16)) & 0xFFFFFFFF

    def _initialize(self, seed = 0):
        self.table = [0]*18
        self.table[0] = ((self.lot & 0xFFFF) + 0x55543DC3 + (self.lot >> 16) + (seed & 0xFF)) & 0xFFFFFFFF
        self.table[1] = ((self.tid & 0xFFFF) + 0xAAAAE44E + (self.tid >> 16) + (seed >> 8)) & 0xFFFFFFFF

        for i in range(2, 18):
            self.table[i] = self._generate()

        self.ptr = ((self.table[0] + self.table[1]) & 0xF) + 2
