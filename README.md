# Project status March 8th

* New features: No more hurting your fingers with clunky PDM buttons! Pod activation and basal schedule settings.
* [Wiki](https://github.com/winemug/omnipy/wiki) is constantly being updated, many thanks to [@dexdan](https://github.com/dexdan), [@scudrunner](https://github.com/scudrunner), [@Kywalh](https://github.com/Kywalh) and [@badgerpapa](https://github.com/badgerpapa)!
* Fixed an issue when a BLE connection to RileyLink were to be dropped in the middle of executing a command, it could cause the pod to fail. (It still can, but omnipy will prevent failure if it can reestablish BT connection within the next few minutes)
* Watch out on this page for release announcement and links. Join us in the [slack space](https://join.slack.com/t/omnicore-pdm/) for questions, updates and support via this [invite link](https://join.slack.com/t/omnicore-pdm/shared_invite/enQtNTY0ODcyOTA0ODcwLTNiMDc2OTE5MDk4Yjk0MDZlNDY1MmViMDkyZGYxZmQ2NWIwNDVhMmM0NTM1ZTM4MDdlYjFjNjBmZTRlYzllMmY).

# Wiki Links

[Setup](https://github.com/winemug/omnipy/wiki/Setup-and-Configuration) documentation for omnipy

[Requirements](https://github.com/winemug/omnipy/wiki/Requirements)

[Setup](https://github.com/winemug/omnipy/wiki/Setup-and-Configuration)

[F.A.Q.](https://github.com/winemug/omnipy/wiki/Frequently-Asked-Questions)

[Support](https://github.com/winemug/omnipy/wiki/Support)

# About
omnipy is a PDM (personal diabetes manager) emulator for the OmniPod insulin pump and it can be used to command the pump to perform various functions over a Raspberry Pi on a local network. It exposes a basic HTTP API to be utilized by APS systems, and currently integrates with Android APS via a [custom fork](https://github.com/winemug/omnipy/wiki/AndroidAPS-Setup) of Android APS v2.x

![rileylink android raspberrypi](https://github.com/winemug/omnipy/raw/master/img/droidrlpi.jpg)

# Important Background Information
This used to be a pet project, where I investigated the radio communication between the OmniPod and the PDM. Whilst still studying the OmniPod, I have decided that there was enough information available to let it execute basic commands which would make it usable in an artifical pancreas system. I've put together a prototype and integrated it into AndroidAPS for our own use, which became what it is today.

As a father of a child with Type I diabetes, I desperately needed something until there was a "proper" solution, so this piece of software became indispensible, albeit its design issues and lack of user-friendliness.

You are welcome to test it and report issues, but be aware you are doing this on your **own risk** ~~and so far it has been tested by **only two people**.~~ Initially tested off-body and on non-t1d volunteers, my son has been using this as a closed loop since November 2018. Since then it has evolved from a raspberry pi with a usb stick (rfcat) to raspberry pi with the RileyLink and Android APS and made gradually available for testing to the general public earlier in March 2019. It's now being tested by more and more people and core functionality has so far shown itself to be stable for a looping setup.

# What's next?

This was intended to be a throw-away prototype and I ~~want~~try to keep it that way. The raspberry pi and android are redundant, as both have enough processing power to perform the operations. My focus on Omnipod related development will shift on to the [OmniCore](https://github.com/winemug/OmniCore) project, which will be ready for public testing by ~~mid~~late March 2019.

In the mean time, please do report any issues you find so they can be addressed.

# Information on RileyLink "433"
It seems that the release announcement of [RileyLink433](https://getrileylink.org/product/rileylink433/) got people excited about OmniPod loopability. For clarification: RL 433 is **not** an absolute requirement. If you have the old RileyLink, it will still work - however in a _very_ limited range. It's strongly suggested to change the antenna, for which purpose RileyLink also provides an antenna upgrade kit. Please see the [requirements](https://github.com/winemug/omnipy/wiki/Requirements) section in the wiki and [Increasing Radio Range](https://github.com/winemug/omnipy/wiki/Increasing-Radio-Range) for what you can further do with your RileyLink.
