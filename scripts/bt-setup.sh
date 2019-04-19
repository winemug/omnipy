#!/usr/bin/env bash
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find /usr/local -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo find /home/pi -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;

sudo systemctl stop omnipy-pan.service
sudo systemctl disable omnipy-pan.service
sudo rm -f /etc/systemd/system/omnipy-pan.service
sudo systemctl reset-failed
rm -f /home/pi/omnipy/scripts/btnap-custom.sh

sudo btmgmt power on
sudo bt-device -l | grep -e \(.*\) --color=never -o| cut -d'(' -f2 | cut -d')' -f1 | while read -r mac
do
        if [ !mac ]; then
                sudo bt-device -d $mac
                sudo bt-device -r $mac
        fi
done

sudo hciconfig hci0 sspmode 0
sudo btmgmt connectable on

/usr/bin/expect -f /home/pi/omnipy/scripts/bt-expect.sh

sudo hciconfig hci0 sspmode 1

btdevice=`sudo bt-device -l | grep -e \(.*\)`
mac=`echo $btdevice | cut -d'(' -f2 | cut -d')' -f1`

if [[ ! -z "$mac" ]]; then
	echo "Paired with $btdevice"
	echo "addr=$mac" > /home/pi/omnipy/scripts/btnap-custom.sh
	cat /home/pi/omnipy/scripts/btnap.sh >> /home/pi/omnipy/scripts/btnap-custom.sh
	sudo cp /home/pi/omnipy/scripts/omnipy-pan.service /etc/systemd/system/
	sudo systemctl enable omnipy-pan.service
	sudo systemctl start omnipy-pan.service
else
	echo "bt pairing failed"
fi