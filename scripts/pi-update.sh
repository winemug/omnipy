#!/bin/bash

if [[ ! -d /home/pi/omnipy ]]
then

echo
echo "You don't seem to have omnipy installed, please run the pi-setup.sh script first"
exit

fi

bold=$(tput bold)
normal=$(tput sgr0)
echo
echo "Welcome to ${bold}omnipy${normal} update script"
echo "This script will let you reconfigure omnipy as in the setup script"


read -p "Do you want update to the latest version in the github repository? " -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]
then
echo "Updating omnipy"
cd /home/pi/omnipy
git config --global user.email "omnipy@balya.net"
git config --global user.name "Omnipy Setup"
git stash
git pull
fi

read -p "Do you want reinstall the dependencies? " -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
echo Installing dependencies
cd /home/pi/omnipy
sudo apt install -y bluez-tools python3 python3-pip git build-essential libglib2.0-dev vim
sudo pip3 install simplejson
sudo pip3 install Flask
sudo pip3 install cryptography
sudo pip3 install requests
echo
echo Configuring and installing bluepy
cd /home/pi
git clone https://github.com/IanHarvey/bluepy.git
cd bluepy
python3 ./setup.py build
sudo python3 ./setup.py install
fi


read -p "Do you want reconfigure the API password? " -r
if [[ $REPLY =~ ^[Yy]$ ]]
then
cd /home/pi/omnipy
/usr/bin/python3 /home/pi/omnipy/set_api_password.py
fi

read -p "Do you want test the RileyLink? " -r
if [[ $REPLY =~ ^[Yy]$ ]]
then
cd /home/pi/omnipy
/usr/bin/python3 /home/pi/omnipy/verify_rl.py
fi

read -p "Do you want reconfigure bluetooth personal area network? " -r
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo
    echo "Removing existing bluetooth devices"
    sudo btmgmt power on
    sudo bt-device -l | grep -e \(.*\) --color=never -o| cut -d'(' -f2 | cut -d')' -f1 | while read -r mac
    do
            if [ !mac ]; then
                    sudo bt-device -d $mac
                    sudo bt-device -r $mac
            fi
    done
    echo
    echo "Activating bluetooth pairing mode"
    sudo btmgmt connectable yes
    sudo btmgmt discov yes
    sudo btmgmt pairable yes
    sudo killall bt-agent
    sudo bt-agent -c NoInputNoOutput -d
    echo "Bluetooth device is now discoverable"
    echo
    echo "Open ${bold}bluetooth settings${normal} on your phone to search for and ${bold}pair${normal} with this device"
    echo "If you have already paired it on your phone, please unpair it first, then pair again"
    echo
    printf "Waiting for connection.."

    btdevice=
    while [[ -z "$btdevice" ]]
    do
            printf "."
            sleep 1
            btdevice=`sudo bt-device -l | grep -e \(.*\)`
    done

    sudo btmgmt discov no

    echo

    echo "${bold}Paired with $btdevice.${normal}"
    mac=`echo $btdevice | cut -d'(' -f2 | cut -d')' -f1`

    echo
    echo
    echo "Please ${bold}enable bluetooth tethering${normal} on your phone if it's not already enabled"
    echo "Waiting for connection."
    echo "addr=$mac" > /home/pi/omnipy/scripts/btnap-custom.sh
    cat /home/pi/omnipy/scripts/btnap.sh >> /home/pi/omnipy/scripts/btnap-custom.sh
    sudo cp /home/pi/omnipy/scripts/omnipy-pan.service /etc/systemd/system/
    sudo systemctl enable omnipy-pan.service
    sudo systemctl start omnipy-pan.service
    ipaddr=
    while [[ -z "$ipaddr" ]]
    do
            printf "."
            sleep 1
            ipaddr=`sudo ip -o -4 address | grep bnep0 | grep -e inet.*/ -o | cut -d' ' -f2 | cut -d'/' -f1`
    done
    echo
    echo
    echo "${bold}Connection test succeeeded${normal}. IP address: $ipaddr"
fi

echo
echo Updating service scripts and restarting services

if [[ -d /etc/systemd/system/omnipy-pan.service ]]
then
    sudo systemctl stop omnipy-pan.service
    sudo cp /home/pi/omnipy/scripts/omnipy-pan.service /etc/systemd/system/
    sudo systemctl enable omnipy-pan.service
    sudo systemctl start omnipy-pan.service
fi

sudo cp /home/pi/omnipy/scripts/omnipy.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy-beacon.service /etc/systemd/system/
sudo chown -R pi.pi /home/pi/bluepy
sudo chown -R pi.pi /home/pi/omnipy
sudo systemctl stop omnipy.service
sudo systemctl stop omnipy-beacon.service
sudo systemctl enable omnipy.service
sudo systemctl enable omnipy-beacon.service
sudo systemctl start omnipy.service
sudo systemctl start omnipy-beacon.service
sudo systemctl daemon-reload
echo
echo ${bold}Configuration updated.${normal}
