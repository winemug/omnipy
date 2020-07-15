#!/bin/bash
#FW_UPDATE_FILE=/boot/omnipy-fwupdate
PW_RESET_FILE=/boot/omnipy-pwreset
BT_RESET_FILE=/boot/omnipy-btreset
EXPAND_FS=/boot/omnipy-expandfs
WLAN_INTERFACE=wlan0

if [[ -f ${EXPAND_FS} ]]; then
    /bin/rm ${EXPAND_FS}
    raspi-config --expand-rootfs
    shutdown -r now
fi

#if [[ -f ${FW_UPDATE_FILE} ]]; then
#    /bin/rm ${FW_UPDATE_FILE}
#    /bin/rm /boot/.firmware_revision
#    cp /home/pi/omnipy/scripts/image/rpiupdate.sh /usr/bin/rpiupdate
#    ROOT_PATH=/ BOOT_PATH=/boot SKIP_DOWNLOAD=1 SKIP_REPODELETE=1 SKIP_BACKUP=1 UPDATE_SELF=0 RPI_REBOOT=1 rpi-update
#    shutdown -r now
#fi

if [[ -f ${PW_RESET_FILE} ]]; then

        echo "pi:omnipy" | chpasswd
      	mkdir -p /home/pi/omnipy/data
        rm /home/pi/omnipy/data/key
        cp /home/pi/omnipy/scripts/recovery.key /home/pi/omnipy/data/key
        chown -R pi.pi /home/pi
        systemctl stop omnipy.service > /dev/null 2>&1
        systemctl start omnipy.service > /dev/null 2>&1
        /bin/rm ${PW_RESET_FILE}
fi

if [[ -f ${BT_RESET_FILE} ]]; then
        su -c "/bin/bash /home/pi/omnipy/scripts/bt-reset.sh &" pi
        /bin/rm ${BT_RESET_FILE}
fi

#if [[ -f ${HOT_SPOT_FILE} ]]; then
#
#    	mkdir -p /home/pi/omnipy/data
#        chown -R pi.pi /home/pi
#
#        wpa_cli terminate >/dev/null 2>&1
#        ip addr flush dev ${WLAN_INTERFACE}
#        ip link set dev ${WLAN_INTERFACE} down
#        rm -r /var/run/wpa_supplicant >/dev/null 2>&1
#
#        ifconfig ${WLAN_INTERFACE} down
#        ifconfig ${WLAN_INTERFACE} up
#        ip link set dev ${WLAN_INTERFACE} down
#        ip a add 10.0.34.1/24 brd + dev ${WLAN_INTERFACE}
#        ip link set dev ${WLAN_INTERFACE} up
#        dhcpcd -k ${WLAN_INTERFACE} > /dev/null 2>&1
#        systemctl start hostapd
#        systemctl start dnsmasq
#
#	    #shellinaboxd -t --service /:pi:pi:/home/pi/omnipy:/home/pi/omnipy/scripts/console-ui.sh -p 80 -b
#
#        #/bin/rm ${HOT_SPOT_FILE}
#else
#        ip link set dev ${WLAN_INTERFACE} down
#        ifconfig ${WLAN_INTERFACE} down
#        ifconfig ${WLAN_INTERFACE} up
#        systemctl stop hostapd
#        systemctl stop dnsmasq
#        ip addr flush dev ${WLAN_INTERFACE}
#        ip link set dev ${WLAN_INTERFACE} up
#        dhcpcd  -n ${WLAN_INTERFACE} >/dev/null 2>&1
#        wpa_supplicant -B -i ${WLAN_INTERFACE} -c /etc/wpa_supplicant/wpa_supplicant.conf >/dev/null 2>&1
#fi
