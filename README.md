# About
omnipy is a PDM (personal diabetes manager) emulator for the OmniPod insulin pump and it can be used to command the pump to perform various functions over a network. ~~It is designed to be used over sub-optimal networking conditions (such as the internet) therefore uses the MQTT protocol to listen for commands and forward responses.~~ It exposes a basic HTTP API to be utilized by APS systems, such as Android APS.

# Project status update

As of February 13th:
* Changes implemented that allow for omnipy to work without internet & mqtt
* Work started for necessary changes to AndroidAPS / Omnipod branch
* Public beta release target date: **February 17th, Sunday**

# Important Background Information
This used to be a pet project, where I investigated the radio communication between the OmniPod and the PDM. Whilst still studying the OmniPod, I have decided that there was enough information available to let it execute basic commands which would make it usable in an artifical pancreas system. I've put together a prototype and integrated it into AndroidAPS for my own use, which became what it is today.

As a father of a child with Type I diabetes, I desperately needed something until there was a "proper" solution, so this piece of software became indispensible, albeit its design issues and lack of user-friendliness.

You are welcome to test it and report issues, but be aware you are doing this on your **own risk** and so far it has been tested by **only two people**.

# Requirements
* RileyLink with firmware v2
* A linux computer with bluetooth (e.g. Raspberry Pi)
* An android phone capable of running AndroidAPS

i.e., these:
![rileylink android raspberrypi](https://i.imgur.com/5eJU85Z.jpg)

# How it works and how to set it up
Please click on the [wiki link](https://github.com/winemug/omnipy/wiki) for information on how it works and how to set it up.
  
# What's next?

This was intended to be a throw-away prototype and I want to keep it that way. Python is not my language of choice and the raspberry pi and android are redundant, as both have enough processing power to perform the operations. My focus on Omnipod related development is on the [OmniCore](https://github.com/winemug/OmniCore) project, which will be ready for public testing by end of February 2019.

In the mean time, please do report any issues you find and I will do my best to get it fixed.

