#!/usr/bin/env bash

get_paired_devices() {
        paired_devices=`sudo bt-device -l | grep -e \(.*\) --color=never -o| cut -d'(' -f2 | cut -d')' -f1`
}

try_pair()
{
        sudo btmgmt ssp on
        sudo btmgmt connectable on
        sudo btmgmt pairable on
        sudo btmgmt discov on

        echo "Waiting for remote request"
        counter=1
        while [ $counter -le 19 ]
        do
                ((counter++))
                sleep 10
                sudo bt-device -l > /dev/null 2>&1
                if [[ $? -eq 0 ]]; then
                        echo "paired with a device, exiting pairing mode"
                        sleep 20
                        break
                fi
        done
        sudo btmgmt discov off
        sudo btmgmt pairable off
        sudo btmgmt connectable off
        sudo btmgmt ssp off
}

sudo btmgmt power off
sudo btmgmt power on

get_paired_devices
if [[ -z "${paired_devices}" ]]; then
        echo "no paired bluetooth devices, starting remote initiated pairing procedure"
        try_pair
fi

get_paired_devices

if [[ -z "${paired_devices}" ]]; then
        echo "Timed out waiting for connection, registration attempt will resume after restart"
        exit 0
fi

ever_connected=false
connection_retries=0
while true;
do
        while read -r mac_address;
        do
            echo "Connecting to ${mac_address}"
            sudo killall -9 bt-network > /dev/null 2>&1
            sudo /usr/bin/bt-network -c ${mac_address} nap > /home/pi/omnipy/data/bt-nap.log
            if grep -q "connected" /home/pi/omnipy/data/bt-nap.log; then
                    echo "Disconnected"
                    connection_retries=0
            else
                    echo "Connection failed"
                    ((connection_retries++))
            fi
        done <<< "${paired_devices}"

        if [ $connection_retries -ge 19 ]; then
                echo "too many unsuccessful connection attempts, looking to pair additional devices"
                try_pair
        else
                sleep 10
        fi
done
