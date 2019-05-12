#!/usr/bin/env bash
echo "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev" > /home/pi/omnipy/wpa_temp
echo "update_config=1" >> /home/pi/omnipy/wpa_temp
echo "country=NO" >> /home/pi/omnipy/wpa_temp
echo "network {" >> /home/pi/omnipy/wpa_temp
echo "ssid=\"$1\"" >> /home/pi/omnipy/wpa_temp
echo "psk=\"$2\" }" >> /home/pi/omnipy/wpa_temp
sudo chown root.root /home/pi/omnipy/wpa_temp
sudo mv /home/pi/omnipy/wpa_temp /boot/wpa_supplicant.conf
sudo reboot
