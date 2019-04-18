#!/bin/bash
PW_RESET_FILE=/boot/omnipy-pwreset
BT_SETUP_FILE=/boot/omnipy-btsetup
RECOVERY_FILE=/boot/omnipy-recovery
WLAN_INTERFACE=wlan0

iw dev ${WLAN_INTERFACE} set power_save off

systemctl stop hostapd
systemctl stop dnsmasq
systemctl disable hostapd
systemctl disable dnsmasq
ip link set dev ${WLAN_INTERFACE} down
ifconfig ${WLAN_INTERFACE} down
ifconfig ${WLAN_INTERFACE} up

if [[ -f ${PW_RESET_FILE} ]]; then

        echo "pi:omnipy" | chpasswd
        systemctl stop omnipy.service > /dev/null 2>&1
    	mkdir -p /home/pi/omnipy/data
        rm /home/pi/omnipy/data/key
        cp /home/pi/omnipy/scripts/recovery.key /home/pi/omnipy/data/key
        chown -R pi.pi /home/pi
        sudo systemctl start omnipy.service > /dev/null 2>&1

        /bin/rm ${PW_RESET_FILE}
fi

if [[ -f ${BT_SETUP_FILE} ]]; then

        su -c "/bin/bash /home/pi/omnipy/scripts/bt-setup.sh" pi
        /bin/rm ${BT_SETUP_FILE}
fi

if [[ -f ${RECOVERY_FILE} ]]; then

    	mkdir -p /home/pi/omnipy/data
        chown -R pi.pi /home/pi

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
fi
btw