#!/usr/bin/env bash
sudo apt update
sudo apt upgrade

sudo raspi-config

sudo apt install -y hostapd dnsmasq bluez-tools python3 python3-pip git build-essential libglib2.0-dev vim jq
#sudo apt install $(cat /home/omnipy/scripts/image/pkglist.txt | awk '{print $1}')

sudo systemctl disable hostapd
sudo systemctl unmask hostapd
sudo systemctl disable dnsmasq

cd /home/pi

git config --global user.email "omnipy@balya.net"
git config --global user.name "Omnipy Setup"

sudo pip3 install simplejson Flask cryptography requests

git clone https://github.com/winemug/omnipy.git
git clone https://github.com/winemug/bluepy.git

cd bluepy
python3 ./setup.py build
sudo python3 ./setup.py install

chown -R pi.pi /home/pi

sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find / -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;

sudo apt autoremove

sudo cp /home/pi/omnipy/scripts/image/default.dnsmasq /etc/default/dnsmasq
sudo cp /home/pi/omnipy/scripts/image/default.hostapd /etc/default/hostapd
sudo cp /home/pi/omnipy/scripts/image/hostapd.conf /etc/hostapd/
sudo cp /home/pi/omnipy/scripts/image/dnsmasq.conf /etc/dnsmasq.d/
sudo cp /home/pi/omnipy/scripts/image/dhcpcd.conf /etc/
sudo cp /home/pi/omnipy/scripts/image/rc.local /etc/

sudo cp /home/pi/omnipy/scripts/omnipy-beacon.service /etc/systemd/system/
sudo systemctl enable omnipy-beacon.service

sudo touch /boot/omnipy-recovery
rm /home/pi/.bash_history
sudo halt
