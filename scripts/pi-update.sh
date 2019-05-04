#!/bin/bash

if [[ ! -d /home/pi/omnipy ]]
then

echo
echo "Omnipy is not installed"
exit

fi

echo "Updating omnipy"
cd /home/pi/omnipy
git config --global user.email "omnipy@balya.net"
git config --global user.name "Omnipy Setup"
git stash
git pull

echo
echo "Stopping omnipy services"
sudo systemctl stop omnipy.service
sudo systemctl stop omnipy-beacon.service
sudo systemctl stop omnipy-pan.service
sudo systemctl stop omnipy-hotspot.service


/bin/bash /home/pi/omnipy/scripts/pi-update-finalize.sh
