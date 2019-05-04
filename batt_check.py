#!/usr/bin/env python3
# Dan Evans 23-29/4/19b, based on script by Alex Eames
# NB THIS VERSION FOR DEPLOYMENT

# nb at setup need : sudo apt-get install python3-rpi.gpio

import time
import RPi.GPIO as GPIO
from threading import Thread, RLock


class SpiBatteryVoltageChecker:
    def __init__(self):
        # Hardware setup
        self.adcs = [0]  # voltage divider connected to channel 0 of mcp3002
        self.cutoff = 3  # low battery cutoff (when LipoShim shuts dowwn)
        self.maxvolts = 4.2  # max voltage for the battery, equivalent to 100% charge
        self.vref = 3.3  # vref of the ADC
        self.res1 = 180  # resistor connected to VBATT (/1000)
        self.res2 = 100  # resistor connected to GND (/1000)
        self.reps = 10  # how many times to take each measurement for averaging
        self.pcround = 5  # round % battery to nearest

        # Define Pins/Ports on ADC
        self.SPICLK = 16
        self.SPIMISO = 20
        self.SPIMOSI = 21
        self.SPICS = 13

        self.battery_level = -1
        self.adc_readings = []
        self.sync_lock = RLock()

        try:
            # Set up set up GPIO & SPI interface pins
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.SPIMOSI, GPIO.OUT)
            GPIO.setup(self.SPIMISO, GPIO.IN)
            GPIO.setup(self.SPICLK, GPIO.OUT)
            GPIO.setup(self.SPICS, GPIO.OUT)

            # initial reading to determine availability
            average = 0
            for i in range(0, 10):
                average = self._get_moving_average()

            bp = self._get_percentage(average)
            if bp <= 0.01:
                print("spi reader not detected")
            else:
                self.service_thread = Thread(target=self._service_loop)
                self.service_thread.setDaemon(True)
                self.service_thread.start()
        except:
            print("Failed to set up GPIO pins for battery level reading")

    def get_measurement(self):
        with self.sync_lock:
            return self.battery_level

    def _service_loop(self):
        while True:
            time.sleep(60000)
            try:
                with self.sync_lock:
                    self.battery_level = self._get_percentage(self._get_moving_average())
            except:
                pass

    # ADC code based on an adafruit example for mcp3008
    def _readadc(self, adcnum, clockpin, mosipin, misopin, cspin):
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

    def _get_moving_average(self):
        self.adc_readings.append(self._get_adc_reading())
        reading_count = len(self.adc_readings)
        if reading_count > self.reps:
            self.adc_readings = self.adc_readings[reading_count-self.reps:reading_count]
        return float(sum(self.adc_readings) / len(self.adc_readings))

    def _get_adc_reading(self):
        adc_sum = 0
        for adcnum in self.adcs:
            try:
                adc_sum += self.readadc(adcnum, self.SPICLK, self.SPIMOSI, self.SPIMISO, self.SPICS)
            except:
                print("Error reading adc value")
            time.sleep(0.05)
        return float(adc_sum / len(self.adcs))

    def _get_battery_level(self):
        avg = self._get_moving_average()

    def _get_percentage(self, adc_reading):
        # convert analogue reading to volts and %, accounting for vref and setup of resistor bridge
        volts = adc_reading * ( self.vref / 1024 ) * (self.res1 + self.res2) / self.res2
        voltspc = int ( 100 * ( volts - self.cutoff ) / ( self.maxvolts - self.cutoff ) )
        voltspcround = self.pcround * round( voltspc / self.pcround )
        if (voltspcround > 100):
            voltspcround = 100
        if (voltspcround < 0):
            voltspcround = 0
        return voltspcround


sbc = SpiBatteryVoltageChecker()
while True:
    try:
        print("Battery is now at %d percent" % sbc.get_measurement())
        time.sleep(10)
    except KeyboardInterrupt:
        break
