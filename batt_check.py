#!/usr/bin/env python3
# Dan Evans 23-29/4/19b, based on script by Alex Eames
# NB THIS VERSION FOR DEPLOYMENT

# nb at setup need : sudo apt-get install python3-rpi.gpio

import time
import RPi.GPIO as GPIO

# Hardware setup
adcs = [0] # voltage divider connected to channel 0 of mcp3002
cutoff = 3 # low battery cutoff (when LipoShim shuts dowwn)
maxvolts = 4.2 # max voltage for the battery, equivalent to 100% charge
vref = 3.3 # vref of the ADC
res1 = 180 # resistor connected to VBATT (/1000)
res2 = 100 # resistor connected to GND (/1000)
reps = 10 # how many times to take each measurement for averaging
pcround = 5 # round % battery to nearest

# Define Pins/Ports on ADC
SPICLK = 16
SPIMISO = 20
SPIMOSI = 21
SPICS = 13

#Set up set up GPIO & SPI interface pins
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(SPIMOSI, GPIO.OUT)
GPIO.setup(SPIMISO, GPIO.IN)
GPIO.setup(SPICLK, GPIO.OUT)
GPIO.setup(SPICS, GPIO.OUT)

# ADC code based on an adafruit example for mcp3008
def readadc(adcnum, clockpin, mosipin, misopin, cspin):
    if ((adcnum > 1) or (adcnum < 0)):
        return -1
    if (adcnum == 0):
        commandout = 0x6
    else:
        commandout = 0x7

    GPIO.output(cspin, True)
    GPIO.output(clockpin, False)  # start clock low
    GPIO.output(cspin, False)     # bring CS low

    commandout <<= 5    # we only need to send 3 bits here
    for i in range(3):
        if (commandout & 0x80):
            GPIO.output(mosipin, True)
        else:
            GPIO.output(mosipin, False)
        commandout <<= 1
        GPIO.output(clockpin, True)
        GPIO.output(clockpin, False)

    adcout = 0
    # read in one empty bit, one null bit and 10 ADC bits
    for i in range(12):
        GPIO.output(clockpin, True)
        GPIO.output(clockpin, False)
        adcout <<= 1
        if (GPIO.input(misopin)):
            adcout |= 0x1

    GPIO.output(cspin, True)

    adcout /= 2       # first bit is 'null' so drop it
    return adcout

def getbatt():
    for adcnum in adcs:
        # read the analogue pin
        adctot = 0
        for i in range(reps):
            read_adc = readadc(adcnum, SPICLK, SPIMOSI, SPIMISO, SPICS)
            adctot += read_adc
            time.sleep(0.05)
        read_adc = adctot / reps / 1.0

        #return a false if reading unavailable (eg no ADC installed, or faulty)
        if (read_adc == 0):
            return False

        # convert analogue reading to volts and %, accounting for vref and setup of resistor bridge
        volts = read_adc * ( vref / 1024 ) * (res1 + res2) / res2
        voltspc = int ( 100 * ( volts - cutoff ) / ( maxvolts - cutoff ) )
        voltspcround = pcround * round( voltspc / pcround )
        if (voltspcround > 100):
            voltspcround = 100
        if (voltspcround < 0):
            voltspcround = 0

    return voltspcround

#Test the battery reading % returned by getbatt() function
print("Battery is now " + str( getbatt() ) + "%")
