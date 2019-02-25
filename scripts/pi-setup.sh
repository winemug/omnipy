#!/bin/bash

bold=$(tput bold)
normal=$(tput sgr0)
echo
echo Welcome to ${bold}omnipy${normal} installation script
echo This script will aid you in configuring your raspberry pi to run omnipy
echo
read -p "Press Enter to continue..."

echo
echo ${bold}Step 1/10: ${normal}Updating package repositories
sudo apt update

echo
echo ${bold}Step 2/10: ${normal}Upgrading existing packages
sudo apt upgrade -y

if [[ ! -d /home/pi/omnipy ]]
then
echo
echo ${bold}Step 3/10: ${normal}Downloading and installing omnipy
cd /home/pi
git clone https://github.com/winemug/omnipy.git
cd /home/pi/omnipy
else
echo
echo ${bold}Step 3/10: ${normal}Updating omnipy
cd /home/pi/omnipy
git config --global user.email "omnipy@balya.net"
git config --global user.name "Omnipy Setup"
git stash
git pull
fi
mkdir /home/pi/omnipy/data > /dev/null 2>&1
chmod 755 /home/pi/omnipy/omni.py

echo
echo ${bold}Step 4/10: ${normal}Installing dependencies
sudo apt install -y bluez-tools python3 python3-pip git build-essential libglib2.0-dev vim
sudo pip3 install simplejson
sudo pip3 install Flask
sudo pip3 install cryptography
sudo pip3 install requests

echo
echo ${bold}Step 5/10: ${normal}Configuring and installing bluepy
cd /home/pi
git clone https://github.com/IanHarvey/bluepy.git
cd bluepy
python3 ./setup.py build
sudo python3 ./setup.py install
cd /home/pi/omnipy

echo
echo ${bold}Step 6/10: ${normal}Enabling bluetooth management for users
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find / -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;

echo
echo ${bold}Step 7/10: ${normal}Omnipy HTTP API Password configuration
/usr/bin/python3 /home/pi/omnipy/set_api_password.py

echo
echo ${bold}Step 8/10: ${normal}RileyLink test
echo
echo This step will test if your RileyLink device is connectable and has the
echo correct firmware version installed.
echo
read -p "Do you want to test the Rileylink now? (y/n) " -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    /usr/bin/python3 /home/pi/omnipy/verify_rl.py
fi

echo ${bold}Step 9/10: ${normal}Setting up bluetooth personal area network
echo
read -p "Do you want to set up a bluetooth personal area network? (y/n) " -r
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
    sudo /bin/bash /home/pi/omnipy/scripts/btnap-custom.sh & > /dev/null 2>&1
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
    sudo killall -9 btnap-custom.sh > /dev/null 2>&1
    sudo killall -9 bt-network > /dev/null 2>&1
    sudo cp /home/pi/omnipy/scripts/omnipy-pan.service /etc/systemd/system/
    sudo systemctl enable omnipy-pan.service
    sudo systemctl stop omnipy-pan.service
    sudo systemctl start omnipy-pan.service
fi

echo
echo ${bold}Step 10/10: ${normal}Creating and starting omnipy services
sudo cp /home/pi/omnipy/scripts/omnipy.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy-beacon.service /etc/systemd/system/
sudo chown -R pi.pi /home/pi/bluepy
sudo chown -R pi.pi /home/pi/omnipy
sudo systemctl enable omnipy.service
sudo systemctl enable omnipy-beacon.service
sudo systemctl stop omnipy.service
sudo systemctl stop omnipy-beacon.service
sudo systemctl start omnipy.service
sudo systemctl start omnipy-beacon.service

echo
echo ${bold}Setup completed.${normal}

