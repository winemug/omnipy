#!/usr/bin/env bash
echo
echo Updating service scripts and restarting services
# remnants of hotspot
sudo apt remove hostapd dnsmasq -y > /dev/null 2>&1
sudo apt update && sudo apt upgrade -y

echo Ensure installation of packages needed in v1.4.1
sudo apt install -y python3-rpi.gpio

# remnants of hotspot
sudo systemctl stop omnipy-hotspot.service > /dev/null 2>&1
sudo systemctl disable omnipy-hotspot.service > /dev/null 2>&1
sudo rm /etc/systemd/system/omnipy-hotspot.service > /dev/null 2>&1

# sudo cp /home/pi/omnipy/scripts/image/default.dnsmasq /etc/default/dnsmasq
# sudo cp /home/pi/omnipy/scripts/image/default.hostapd /etc/default/hostapd
# sudo cp /home/pi/omnipy/scripts/image/hostapd.conf /etc/hostapd/
# sudo cp /home/pi/omnipy/scripts/image/dnsmasq.conf /etc/dnsmasq.d/
# sudo cp /home/pi/omnipy/scripts/image/dhcpcd.conf /etc/
sudo cp /home/pi/omnipy/scripts/image/rc.local /etc/


sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find /usr/local/lib -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo find /home/pi -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo chown -R pi.pi /home/pi

sudo cp /home/pi/omnipy/scripts/omnipy-pan.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy-beacon.service /etc/systemd/system/

sudo systemctl enable omnipy.service
sudo systemctl enable omnipy-beacon.service
sudo systemctl enable omnipy-pan.service
sudo systemctl start omnipy.service
sudo systemctl start omnipy-beacon.service
sudo systemctl start omnipy-pan.service

echo
echo Configuration updated.
echo
echo Rebooting
echo
sleep 3
sudo reboot
