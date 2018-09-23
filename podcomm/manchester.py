import random

class ManchesterCodec:

    def __init__(self):
        self.initializeLookupTable()
        self.generateNonManchesterNoise()

    def decode(self, data):
        decoded = ""
        for i in range(0, len(data), 2):
            word = data[i:i+2]
            if self.lookupdict.has_key(word):
                decoded += self.lookupdict[word]
            else:
                break
        return decoded
    
    def encode(self, data):
        encoded = ""
        for i in data:
            encoded += lookupdict[i]
        encoded += self.noiseLines[self.noiseSeq]
        self.noiseSeq += 1
        self.noiseSeq %= 32
        return encoded[:80]

    def initializeLookupTable(self):
        self.lookupdict = dict()
        for i in range(0, 256):
            enc = self.encodeSingleByte(i)
            self.lookupdict[enc] = chr(i)
        
    def encodeSingleByte(self, d):
        e = 0
        for b in range (0,15, 2):
            if d & 0x01 == 0:
                e |= (2 << b)
            else:
                e |= (1 << b)
            d = d >> 1
        return chr(e >> 8) + chr(e & 0xff)

    def generateNonManchesterNoise():
        self.noiseSeq = 0
        noiseNibbles = '0123478bcdef'
        self.noiseLines = []
        for x in range(0, 32):
            noiseLine = "f"
            for i in range(0, 79):
                noiseLine += random.choice(noiseNibbles)
            self.noiseLines.apppend(noiseLine.decode("hex"))