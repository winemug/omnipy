# What is omnipy?

![rileylink android raspberrypi](https://github.com/winemug/omnipy/raw/master/img/droidrlpi.jpg)

Omnipy is a set of hardware and software components that allows users of the Omnipod insulin pump to automate insulin delivery using [Android APS](https://androidaps.readthedocs.io/en/latest/EN/). Android APS is a long established artificial pancreas system with support for many different insulin pumps, but does not (yet) officially feature Omnipod support. Omnipy bridges this gap and brings Omnipod to Android APS.

Omnipy evolved from my initial efforts on working with OmniPod and is released to public as of February 2019. It has grown over time with support and feedback from the community.

Read the [introduction](https://github.com/winemug/omnipy/wiki) page on the wiki for more information.

### May 6th, Update v1.4.2

https://github.com/winemug/omnipy/releases/tag/v1.4.2

This update fixes an issue introduced with the latest update, which again due to flaky communications could result in pod failures. Please update as soon as possible, especially if coming from v1.4.1.

### May 4th, Update v1.4.1

This update fixes an issue in the communication recovery process and is _strongly suggested if you are experiencing frequent disconnection issues_ either between Pod-RileyLink or RileyLink-Raspberry Pi. Note that this does NOT fix connection issues. Instead it fixes one of the several workarounds in omnipy, which try to prevent pod failures due to connection issues.

See [Release Notes](https://github.com/winemug/omnipy/wiki/Release-Notes) for more information on what's new and what's changed in this release.

It has also come to my attention that many users are having _serious_ connectivity problems; but are simply _not realizing_ it due to the workarounds mentioned above. Please consider the following points for stable communications:

* Make sure your RileyLink is not on running on low battery, whether the leds are blinking or it seems to be working, is not good enough.
* Make sure your Raspberry Pi and RileyLink are not farther away from each other. Try to keep them as close as possible. Some raspberry pi's apparently have BLE range issues and the RileyLink does not have the best BLE reception either.
* Make sure your RileyLink's 433 MHz antenna is performing. One way to measure that is to look into the packet logs and omnipy.log to check if there is a significant number of repeats during message exchange.
* If you suspect that the communication between the Pod and RileyLink is not optimal, have a look at the wire antenna option. I cannot overstate the amazing range of the simple wire antenna.
* If you cannot afford to build the custom antenna, don't let the RL sit far away from the Pod. If you're frequently going away from the RL, put it on a high place. 


[Download](https://github.com/winemug/omnipy/releases/tag/v1.4.1) the latest version here.

Please refer to the [Setup documentation](https://github.com/winemug/omnipy/wiki/Setup-and-Configuration) on the wiki for information on how to set up the latest version of omnipy.

## Important information from the author

As of omnipy v1.4 release, **all development activities on omnipy is stopped**. The project is considered feature-complete and stable enough for general use.

Unless a major issue is encountered, there will be no fixes or updates to the current release. Support will still be available in the same form as it has been until today. If anyone is interested in taking the project further in its current form, [get in touch](mailto:barisk@gmail.com).

## Next up: OmniCore

I will focus all development efforts related to Omnipod and Omnipod Dash on [**OmniCore**](https://github.com/winemug/OmniCore), an OmniPod focused software product with a broader scope involving multiple platforms, hardware components and surprise features.

Today, I'm excited to announce that the very first milestone of OmniCore is going to _replace omnipy completely_ to address one particular complaint all omnipy users (including myself) have had so far: Having to carry a raspberry pi and a power supply.

**All of the omnipy functionality has already been ported** and the first release is scheduled to arrive _very_ soon. Keep an eye on the [OmniCore](https://github.com/winemug/OmniCore) github page for a status update in the coming days.

## Join us

For questions, updates and support join us in the [omnicore-pdm slack](https://join.slack.com/t/omnicore-pdm/shared_invite/enQtNTk2MzYxOTAwNDUyLWNkZTBlYjk0ZWU1YTA1ZjA4OGVlOWQ3YWZkNmNkNzk0YjdhMWM0NmQ3ZTRiM2I3ZDVkNGYyYWJiYTM5Yjc2YjM).

# Wiki Links

[Requirements](https://github.com/winemug/omnipy/wiki/Requirements)

[Setup](https://github.com/winemug/omnipy/wiki/Setup-and-Configuration)

[F.A.Q.](https://github.com/winemug/omnipy/wiki/Frequently-Asked-Questions)

[Support](https://github.com/winemug/omnipy/wiki/Support)

