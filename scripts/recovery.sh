#!/bin/bash
RECOVERY_FILE=/boot/omnipy-recovery
WLAN_INTERFACE=wlan0

startHotSpot()
{
        ifconfig $WLAN_INTERFACE down
        ifconfig $WLAN_INTERFACE up

        ip link set dev $WLAN_INTERFACE down
        ip a add 10.0.34.1/24 brd + dev $WLAN_INTERFACE
        ip link set dev $WLAN_INTERFACE up
        dhcpcd -k $WLAN_INTERFACE > /dev/null 2>&1
        systemctl start hostapd
        systemctl start dnsmasq
}

if [ -f $RECOVERY_FILE ]; then

        sudo systemctl stop omnipy.service
        sudo systemctl stop omnipy-pan.service

        echo "pi:omnipy" | chpasswd

    	mkdir -p /home/pi/omnipy/data
        #rm /home/pi/omnipy/data/key
        #cp /home/pi/omnipy/scripts/recovery.key /home/pi/omnipy/data/
        chown -R pi.pi /home/pi

        startHotSpot

	    shellinaboxd -t --service /:pi:pi:/home/pi/omnipy:/home/pi/omnipy/scripts/console-ui.sh -p 80 -b

        /bin/rm $RECOVERY_FILE
fi
