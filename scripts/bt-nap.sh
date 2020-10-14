#!/usr/bin/env bash


get_wlan_connection() {
  wlan_config=`iwconfig 2>&1 | grep ESSID:off/any`
}

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

try_connect_bt() {
  get_paired_devices

#  if [[ -z "${paired_devices}" ]] || [[ $bt_connection_retries -ge 6 ]]; then
#    echo "starting remote initiated pairing procedure"
#    bt_connection_retries=0
#    try_pair
#  fi
#
#  get_paired_devices

  if [[ -z "${paired_devices}" ]]; then
    echo "no paired devices"
  else
    while read -r mac_address;
    do
      echo "Connecting to ${mac_address}"
      sudo killall -9 bt-network > /dev/null 2>&1
      sudo /usr/bin/bt-network -c ${mac_address} nap > /home/pi/omnipy/data/bt-nap.log
      if grep -q "connected" /home/pi/omnipy/data/bt-nap.log; then
              echo "Disconnected"
              bt_connection_retries=0
      else
              echo "Connection failed"
              ((bt_connection_retries++))
      fi
    done <<< "${paired_devices}"
  fi
}

sudo btmgmt power on
sleep 10
bt_connection_retries=0
wlan_config=
while true;
do
  get_wlan_connection
  if [[ ! -z "${wlan_config}" ]]; then
    echo "no wlan connection, trying bt"
    try_connect_bt
  else
    echo "wlan connection active, bt-nap postponed"
    sleep 120
  fi
done
