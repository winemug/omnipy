#!/usr/bin/env bash
echo
echo Updating service scripts and restarting services
# remnants of hotspot
sudo systemctl stop omnipy-hotspot.service > /dev/null 2>&1
sudo systemctl disable omnipy-hotspot.service > /dev/null 2>&1
sudo rm /etc/systemd/system/omnipy-hotspot.service > /dev/null 2>&1
sudo apt remove hostapd dnsmasq -y > /dev/null 2>&1

echo Ensure installation of packages needed in v1.4.1+
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-rpi.gpio ntp fake-hwclock bluez-tools python3-pip python3-venv

sudo cp /home/pi/omnipy/scripts/image/rc.local /etc/

# bluepy cleanup
sudo pip uninstall bluepy -y
sudo pip2 uninstall bluepy -y
sudo pip3 uninstall bluepy -y
sudo rm /usr/local/bin/blescan
sudo rm /usr/local/bin/sensortag
sudo rm /usr/local/bin/thingy52
sudo rm /home/pi/bluepy/bluepy/bluepy-helper
sudo rm -rf /usr/local/lib/python3.5/dist-packages/bluepy-1.3.0-py3.5.egg
sudo rm -rf /usr/local/lib/python2.7/dist-packages/bluepy-1.3.0-py2.7.egg


cd /home/pi/omnipy
python3 -m pip install --user pip --upgrade
python3 -m pip install --user virtualenv
if [[ -d "/home/pi/v" ]]; then
  python3 -m venv --upgrade /home/pi/v
else
  python3 -m venv /home/pi/v
fi

source /home/pi/v/bin/activate
python3 -m pip install --user pip --upgrade
python3 -m pip install -r /home/pi/omnipy/requirements.txt

cd /home/pi/bluepy
git stash
git pull
python3 setup.py install



sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find /home/pi -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo chown -R pi.pi /home/pi
chmod -R 755 /home/pi/omnipy/scripts/*.sh

sudo systemctl disable omnipy-mq.service
sudo systemctl disable omnipy.service
sudo systemctl disable omnipy-beacon.service
sudo systemctl disable omnipy-pan.service

sudo cp /home/pi/omnipy/scripts/omnipy-pan.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy-beacon.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy-mq.service /etc/systemd/system/

sudo systemctl enable omnipy.service
sudo systemctl enable omnipy-beacon.service
sudo systemctl enable omnipy-pan.service

echo
echo Configuration updated.
echo
echo Rebooting
echo
sleep 3
sudo reboot
