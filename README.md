# What is omnipy?

![rileylink android raspberrypi](https://github.com/winemug/omnipy/raw/master/img/droidrlpi.jpg)

Omnipy is a set of hardware and software components that allows users of the Omnipod insulin pump to automate insulin delivery using [Android APS](https://androidaps.readthedocs.io/en/latest/EN/). Android APS is a long established artificial pancreas system with support for many different insulin pumps, but does not (yet) officially feature Omnipod support. Omnipy bridges this gap and brings Omnipod to Android APS.

Omnipy evolved from my initial efforts on working with OmniPod and is released to public as of February 2019. It has grown over time with support and feedback from the community.

Read the [introduction](https://github.com/winemug/omnipy/wiki) page on the wiki for more information.

## November 25th, 2019
## Important update regarding Android APS version updates
As of today, omnipy users of Android APS have started receiving a warning message in the application about a grace period for certain features shutting down - unless the application is upgraded.

Since omnipy is no longer receiving feature updates, the current Android APS version 2.3 for omnipy will not be upgraded as long as there is no critical issue that affects omnipy users.

Omnipy users are strongly encouraged to follow announcements of the [OmniCore](https://github.com/winemug/OmniCore) project and switch to the first public release as soon as it is made available.

If you are unable to make the transition to OmniCore before January 1st 2020, please build and compile [this release of Android APS for omnipy](https://github.com/winemug/AndroidAPS/releases/tag/omnipy_v1.4.3_aaps_v2.3.0_build_3) in order to prevent being shut off.

### May 12th, Update v1.4.3 available (while stocks last!)

https://github.com/winemug/omnipy/releases/tag/v1.4.3

This update fixes various issues from previous 1.4.x releases. Upgrading via image installation is strongly recommended.

See [Release Notes](https://github.com/winemug/omnipy/wiki/Release-Notes) for more information on what's new and what's changed in this release.

See also [Tips & Tricks](https://github.com/winemug/omnipy/wiki/Tips-and-Tricks) with respect to communication stability.

Please refer to the [Setup documentation](https://github.com/winemug/omnipy/wiki/Setup-and-Configuration) on the wiki for information on how to set up the latest version of omnipy.

## Important information from the author

As of omnipy v1.4 release, **all development activities on omnipy is stopped**. The project is considered feature-complete and stable enough for general use.

Unless a major issue is encountered, there will be no fixes or updates to the current release. Support will still be available in the same form as it has been until today. If anyone is interested in taking the project further in its current form, [get in touch](mailto:barisk@gmail.com).

## Next up: OmniCore

I will focus all development efforts related to Omnipod and Omnipod Dash on [**OmniCore**](https://github.com/winemug/OmniCore), an OmniPod focused software product with a broader scope involving multiple platforms, hardware components and surprise features.

Today, I'm excited to announce that the very first milestone of OmniCore is going to _replace omnipy completely_ to address one particular complaint all omnipy users (including myself) have had so far: Having to carry a raspberry pi and a power supply.

Keep an eye on the [OmniCore](https://github.com/winemug/OmniCore) github page.

## Join us

For questions, updates and support join us in the [omnicore-pdm slack](https://join.slack.com/t/omnicore-pdm/shared_invite/enQtODM0MzAxMDkzNzI5LWQ5MjEwNWNhOGNlZDI1YTcxNDhmYmNjNDE3YTU2MWY3OGNkMzZlMTc5MTFhYmI5MDBjNTk5YmQ1NGRhZGNlZDM).

# Wiki Links

[Requirements](https://github.com/winemug/omnipy/wiki/Requirements)

[Setup](https://github.com/winemug/omnipy/wiki/Setup-and-Configuration)

[F.A.Q.](https://github.com/winemug/omnipy/wiki/Frequently-Asked-Questions)

[Support](https://github.com/winemug/omnipy/wiki/Support)

