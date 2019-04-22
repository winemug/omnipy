#!/usr/bin/env bash

pair_bt_device() {
    sudo btmgmt power off
    sudo btmgmt ssp on
    sudo btmgmt connectable on
    sudo btmgmt pairable on
    sudo btmgmt discov on
    sudo btmgmt power on
    bt_device=
    while [[ -z "${bt_device}" ]]
    do
            sleep 1
            bt_device=`sudo bt-device -l | grep -e \(.*\)`
    done

    sudo btmgmt discov off
    echo "Paired with ${bt_device}"
}

while true;
do
    killall -9 bt-network > /dev/null 2>&1
    sudo btmgmt power off
    sudo btmgmt power on
    paired_devices=`bt-device -l | grep -e \(.*\) --color=never -o| cut -d'(' -f2 | cut -d')' -f1`
    if [[ ! -z ${paired_devices} ]]; then
        while read -r mac_address;
        do
            /usr/bin/bt-network -c ${mac_address} nap > /dev/null 2>&1
        done <<< "${paired_devices}"
        sleep 15
    else
        pair_bt_device
    fi
done
