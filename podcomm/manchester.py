import random

class ManchesterCodec:

    def __init__(self):
        self.initializeLookupTables()
        self.generateNonManchesterNoise()

    def decode(self, data):
        decoded = ""
        for i in range(0, len(data), 2):
            word = data[i:i+2]
            if self.decodeDict.has_key(word):
                decoded += self.decodeDict[word]
            else:
                break
        return decoded
    
    def encode(self, data):
        encoded = ""
        for i in data:
            encoded += self.encodeDict[i]
        encoded += self.noiseLines[self.noiseSeq]
        self.noiseSeq += 1
        self.noiseSeq %= 32
        return encoded[:200]

    def initializeLookupTables(self):
        self.decodeDict = dict()
        self.encodeDict = dict()
        for i in range(0, 256):
            enc = self.encodeSingleByte(i)
            self.decodeDict[enc] = chr(i)
            self.encodeDict[chr(i)] = enc
        
    def encodeSingleByte(self, d):
        e = 0
        for b in range (0,15, 2):
            if d & 0x01 == 0:
                e |= (2 << b)
            else:
                e |= (1 << b)
            d = d >> 1
        return chr(e >> 8) + chr(e & 0xff)

    def generateNonManchesterNoise(self):
        self.noiseSeq = 0
        noiseNibbles = '0123478bcdef'
        self.noiseLines = []
        for x in range(0, 32):
            noiseLine = "f"
            for i in range(0, 159):
                noiseLine += random.choice(noiseNibbles)
            self.noiseLines.append(noiseLine.decode("hex"))