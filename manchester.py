class ManchesterCodec:

    def __init__(self):
        self.initializeLookupTable()

    def Decode(self, data):
        decoded = ""
        for i in range(0, len(data), 2):
            word = data[i:i+2]
            if self.lookupdict.has_key(word):
                decoded += self.lookupdict[word]
            else:
                break
        return decoded
    
    def Encode(self, data):
        pass

    def initializeLookupTable(self):
        self.lookupdict = dict()
        for i in range(0, 256):
            enc = self.manchesterEncodeSingleByte(i)
            self.lookupdict[enc] = chr(i)

    def manchesterEncodeSingleByte(self, d):
        e = 0
        for b in range (0,15, 2):
            if d & 0x01 == 0:
                e |= (2 << b)
            else:
                e |= (1 << b)
            d = d >> 1
        return chr(e >> 8) + chr(e & 0xff)
