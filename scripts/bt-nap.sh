#!/usr/bin/env bash

pair_bt_device() {
    echo "Enabling bluetooth discovery"
    sudo btmgmt power off
    sudo btmgmt ssp on
    sudo btmgmt connectable on
    sudo btmgmt pairable on
    sudo btmgmt discov on
    sudo btmgmt power on
    echo "Waiting for a connection"
    while : ; do
        sleep 2
        sudo bt-device -l > /dev/null 2>&1
        [[ ! $? -eq 0 ]] || break
    done

    echo "Pairing completed"
    sudo btmgmt discov off
    sleep 15
}

sudo btmgmt power off
sudo btmgmt power on
while true;
do
    paired_devices=`sudo bt-device -l | grep -e \(.*\) --color=never -o| cut -d'(' -f2 | cut -d')' -f1`
    if [[ ! -z "${paired_devices}" ]]; then
        while read -r mac_address;
        do
            echo "Connecting to ${mac_address}"
            sudo killall -9 bt-network > /dev/null 2>&1
            sudo /usr/bin/bt-network -c ${mac_address} nap
            echo "Disconnected from ${mac_address} (or connection failed)"
        done <<< "${paired_devices}"
        sleep 15
    else
        pair_bt_device
    fi
done
