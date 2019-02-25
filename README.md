# Project status February 25th

* omnipy implementation is ready for beta testing. [Project link](https://github.com/winemug/omnipy/projects/1)
* Android APS integration is functional and is in internal testing, UI features not related to looping are still in development. [Project link](https://github.com/winemug/AndroidAPS/projects/1)
* [Setup](https://github.com/winemug/omnipy/wiki/Setup-and-Configuration) documentation for omnipy is completed, AndroidAPS and Raspberry Pi OS still pending.

# Wiki Links

[Requirements](https://github.com/winemug/omnipy/wiki/Requirements)

[Setup](https://github.com/winemug/omnipy/wiki/Setup-and-Configuration)

[F.A.Q.](https://github.com/winemug/omnipy/wiki/Frequently-Asked-Questions)


# About
omnipy is a PDM (personal diabetes manager) emulator for the OmniPod insulin pump and it can be used to command the pump to perform various functions over a Raspberry Pi on a local network. It exposes a basic HTTP API to be utilized by APS systems, and currently integrates with Android APS.

![rileylink android raspberrypi](https://github.com/winemug/omnipy/raw/master/img/droidrlpi.jpg)

# Important Background Information
This used to be a pet project, where I investigated the radio communication between the OmniPod and the PDM. Whilst still studying the OmniPod, I have decided that there was enough information available to let it execute basic commands which would make it usable in an artifical pancreas system. I've put together a prototype and integrated it into AndroidAPS for my own use, which became what it is today.

As a father of a child with Type I diabetes, I desperately needed something until there was a "proper" solution, so this piece of software became indispensible, albeit its design issues and lack of user-friendliness.

You are welcome to test it and report issues, but be aware you are doing this on your **own risk** and so far it has been tested by **only two people**.

# What's next?

This was intended to be a throw-away prototype and I want to keep it that way. Python is not my language of choice and the raspberry pi and android are redundant, as both have enough processing power to perform the operations. My focus on Omnipod related development is on the [OmniCore](https://github.com/winemug/OmniCore) project, which will be ready for public testing by mid March 2019.

In the mean time, please do report any issues you find and I will do my best to get it fixed.

# Information on RileyLink "433"
It seems that the release announcement of [RileyLink433](https://getrileylink.org/product/rileylink433/) got people excited about OmniPod loopability. For clarification: RL 433 is **not** an absolute requirement. If you have the old RileyLink, it will still work. Please see the [requirements](https://github.com/winemug/omnipy/wiki/Requirements) section in the wiki and [Increasing Radio Range](https://github.com/winemug/omnipy/wiki/Increasing-Radio-Range) for what you can further do with your RileyLink.
