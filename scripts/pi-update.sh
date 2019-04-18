#!/bin/bash

if [[ ! -d /home/pi/omnipy ]]
then

echo
echo "You don't seem to have omnipy installed, please run the pi-setup.sh script first"
exit

fi

echo
echo "Stopping omnipy services"
sudo systemctl stop omnipy.service
sudo systemctl stop omnipy-beacon.service
sudo systemctl stop omnipy-pan.service
sudo systemctl disable omnipy.service
sudo systemctl disable omnipy-beacon.service
sudo systemctl disable omnipy-pan.service


echo "Updating omnipy"
cd /home/pi/omnipy
git fetch
git checkout master
git config --global user.email "omnipy@balya.net"
git config --global user.name "Omnipy Setup"
git stash
git pull

/bin/bash /home/pi/omnipy/scripts/pi-update-finalize.sh
