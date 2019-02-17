#!/bin/bash
#/bin/bash $HOME/omnipy/btnap.sh >/dev/null &2>1 &
/usr/bin/python3 -u $HOME/omnipy/omnipy_beacon.py &
/usr/bin/python3 -u $HOME/omnipy/restapi.py
