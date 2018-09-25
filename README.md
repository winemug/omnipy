# About omnipy
This is a set of python scripts for communicating with the OmniPod insulin pump using RfCat.

## Background
The code is based on the (seemingly abandoned) [openomni](https://github.com/openaps/openomni/) project and its findings respective to the OmniPod Sub-GHz communication protocol.

For sake of simplicity I kept the choice of language as Python but the code is highly experimental and needless to say dirty. The idea behind this is to provide a diagnostic/testing tool while trying to come up with a reference design for the implementation of the OmniPod protocol to integrate into artificial pancreas systems.

# What you need

* A supported USB device running [rfcat](https://github.com/atlas0fd00m/rfcat)

For example the [CC1111 USB Dongle](http://www.ti.com/tool/CC1111EMK868-915) by Texas Instruments and the [CC Debugger](https://www.ti.com/tool/CC-DEBUGGER) to flash the firmware.
* Python 2.7
* Linux (unless you can install rfcat on windows)
* Optional: An OmniPOD PDM (Personal Data Manager) and spare PODs for testing

# Building

* Follow instructions on [rfcat repository](https://github.com/atlas0fd00m/rfcat) relevant for your USB device.

If you're using the CC1111 Dongle, I have found that the latest version (as of 2018 Aug 23rd) of rfcat does have some issues. Clone [this branch](https://github.com/atlas0fd00m/rfcat/tree/651ce73864ebac97590a9cc294aa72f0451350a9) and install the python library using:

```
cd rfcat
sudo python setup.py install
```

On Linux, use [cc-tool](https://sourceforge.net/projects/cctool/) to install the pre-built firmware provided in this repository onto the CC1111 Dongle:

```
cc-tool -ew ~/omnipy/bin/cc1111emkRfCat-20180131.hex
```

Alternatively on Windows, you can use the [SmartRF Flash Programmer](http://www.ti.com/tool/flash-programmer) to install the firmware. (Make sure to download v1 of the software and not the Flash Programmer v2)

# How it works

There are various python scripts in the root folder

## Logger

This script continously logs the communication session between the POD and the PDM. It is protocol-aware and will log all packets to a file and at the same time will output constructed messages to the console (and another file). It will also print relevant errors if anything is amiss (such as lost packets)

Sample output:

```
$ python logger.py
Started press any key to exit
2018-09-25 21:23:21.091105 Msg PDM: 0e0100 (OK, ACK'd) (seq: 0x0a, unkn.: 0x00)
2018-09-25 21:23:21.493985 Msg POD: 1d28014620000009c7ff (OK, ACK'd) (seq: 0x0b, unkn.: 0x00)
2018-09-25 21:23:31.116113 Msg PDM: 1f0576d6e6ba62 (OK, ACK'd) (seq: 0x0c, unkn.: 0x00)
2018-09-25 21:23:31.493918 Msg POD: 1d18014660000009c7ff (OK, ACK'd) (seq: 0x0d, unkn.: 0x00)
Exiting
Done

$ cat omni_messages.log 
2018-09-25 21:23:21.091105 Msg PDM: 0e0100 (OK, ACK'd) (seq: 0x0a, unkn.: 0x00)
2018-09-25 21:23:21.493985 Msg POD: 1d28014620000009c7ff (OK, ACK'd) (seq: 0x0b, unkn.: 0x00)
2018-09-25 21:23:31.116113 Msg PDM: 1f0576d6e6ba62 (OK, ACK'd) (seq: 0x0c, unkn.: 0x00)
2018-09-25 21:23:31.493918 Msg POD: 1d18014660000009c7ff (OK, ACK'd) (seq: 0x0d, unkn.: 0x00)

$ cat omni_packets.log 
2018-09-25 21:23:21.091105 Pkt PDM Addr: 1f0e89f1 Addr2: 1f0e89f1 Seq: 0x04 Body: 28030e01000297
2018-09-25 21:23:21.389358 Pkt PDM Addr: 1f0e89f1 Addr2: 1f0e89f1 Seq: 0x04 Body: 28030e01000297
2018-09-25 21:23:21.493985 Pkt POD Addr: 1f0e89f1 Addr2: 1f0e89f1 Seq: 0x05 Body: 2c0a1d28014620000009c7ff03f4
2018-09-25 21:23:21.520231 Pkt ACK Addr: 1f0e89f1 Addr2: 00000000 Seq: 0x06
2018-09-25 21:23:31.116113 Pkt PDM Addr: 1f0e89f1 Addr2: 1f0e89f1 Seq: 0x07 Body: 30071f0576d6e6ba62831d
2018-09-25 21:23:31.418080 Pkt PDM Addr: 1f0e89f1 Addr2: 1f0e89f1 Seq: 0x07 Body: 30071f0576d6e6ba62831d
2018-09-25 21:23:31.493918 Pkt POD Addr: 1f0e89f1 Addr2: 1f0e89f1 Seq: 0x08 Body: 340a1d18014660000009c7ff00d8
2018-09-25 21:23:31.519708 Pkt ACK Addr: 1f0e89f1 Addr2: 00000000 Seq: 0x09
```

## MQTT Repeater
Status: Work in progress

Allows two CC1111 Dongles on two different computers to route messages between the PDM and the POD over internet/LAN.

## POD Emulator
Status: Work in progress

Allows to emulate a POD for use with an actual PDM

## PDM Emulator
Status: Not started

Allows to emulate a PDM to command an actual POD

## MITM
Status: Work in progress

A man, a PDM and a POD go to a bar.
