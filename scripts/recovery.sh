#!/bin/bash
RECOVERY_FILE=/boot/omnipy-recovery
BT_RECOVERY_FILE=/boot/omnipy-btrecovery
PW_RECOVERY_FILE=/boot/omnipy-pwrecovery
WLAN_INTERFACE=wlan0

iw dev ${WLAN_INTERFACE} set power_save off

if [[ -f ${PW_RECOVERY_FILE} ]]; then
        echo "pi:omnipy" | chpasswd
        rm /home/pi/omnipy/data/key
        cp /home/pi/omnipy/scripts/recovery.key /home/pi/omnipy/data/
        chown -R pi.pi /home/pi
        /bin/rm ${PW_RECOVERY_FILE}
fi

if [[ -f ${BT_RECOVERY_FILE} ]]; then
        su -c "/bin/bash /home/pi/omnipy/scripts/bt-setup.sh" pi &
        /bin/rm ${BT_RECOVERY_FILE}
fi

if [[ -f ${RECOVERY_FILE} ]]; then
    	mkdir -p /home/pi/omnipy/data
        chown -R pi.pi /home/pi

        ifconfig ${WLAN_INTERFACE} down
        ifconfig ${WLAN_INTERFACE} up

        ip link set dev ${WLAN_INTERFACE} down
        ip a add 10.0.34.1/24 brd + dev ${WLAN_INTERFACE}
        ip link set dev ${WLAN_INTERFACE} up
        systemctl enable hostapd
        systemctl enable dnsmasq
        systemctl start hostapd
        systemctl start dnsmasq
        dhcpcd -k ${WLAN_INTERFACE} > /dev/null 2>&1

	    shellinaboxd -t --service /:pi:pi:/home/pi/omnipy:/home/pi/omnipy/scripts/console-ui.sh -p 80 -b

        /bin/rm ${RECOVERY_FILE}
else
        systemctl stop hostapd
        systemctl stop dnsmasq
        systemctl disable hostapd
        systemctl disable dnsmasq
        ip link set dev ${WLAN_INTERFACE} down
        ifconfig ${WLAN_INTERFACE} down
        ifconfig ${WLAN_INTERFACE} up
fi
