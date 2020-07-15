#!/usr/bin/env bash
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find /usr/local -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo find /home/pi -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;

sudo btmgmt power off
sudo btmgmt power on

sudo bt-device -l | grep -e \(.*\) --color=never -o| cut -d'(' -f2 | cut -d')' -f1 | while read -r mac
do
        if [[ ! -z "${mac}" ]]; then
                sudo bt-device -d ${mac}
                sudo bt-device -r ${mac}
        fi
done
