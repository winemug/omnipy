#!/usr/bin/env bash
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find / -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;

sudo systemctl stop omnipy-pan.service
sudo systemctl disable omnipy-pan.service

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

echo "addr=$mac" > /home/pi/omnipy/scripts/btnap-custom.sh
cat /home/pi/omnipy/scripts/btnap.sh >> /home/pi/omnipy/scripts/btnap-custom.sh
sudo cp /home/pi/omnipy/scripts/omnipy-pan.service /etc/systemd/system/
sudo systemctl enable omnipy-pan.service
sudo systemctl start omnipy-pan.service

