#!/usr/bin/env bash
echo
echo Omnipy updater started

echo Updating raspbian packages
sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y

echo Updating python environment
python3 -m pip install --user pip --upgrade
python3 -m pip install --user virtualenv --upgrade
python3 -m venv --upgrade /home/pi/v

source /home/pi/v/bin/activate
python3 -m pip install pip setuptools --upgrade

echo Installing and updating libraries for omnipy
python3 -m pip install -r /home/pi/omnipy/requirements.txt

#echo Updating omnipy customized bluepy library
#cd /home/pi/bluepy
#git stash
#git pull
#python3 setup.py build
#python3 setup.py install

deactivate

sudo cp /home/pi/omnipy/scripts/image/rc.local /etc/
sudo cp /home/pi/omnipy/scripts/image/omnipy-pan.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-rest.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-beacon.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-mq.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-sync.service /etc/systemd/system/

sudo rm /boot/omnipy-upgrade
echo
echo Configuration updated.
echo
echo Rebooting
echo
sleep 3
sudo reboot
