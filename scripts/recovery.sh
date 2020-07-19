#!/bin/bash
#FW_UPDATE_FILE=/boot/omnipy-fwupdate
PW_RESET_FILE=/boot/omnipy-pwreset
BT_RESET_FILE=/boot/omnipy-btreset
UPGRADE_FILE=/boot/omnipy-upgrade
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
        /bin/rm ${PW_RESET_FILE}
        /sbin/shutdown -r now
fi

if [[ -f ${BT_RESET_FILE} ]]; then
        su -c "/bin/bash /home/pi/omnipy/scripts/bt-reset.sh &" pi
        /bin/rm ${BT_RESET_FILE}
        /sbin/shutdown -r now
fi

if [[ -f ${UPGRADE_FILE} ]]; then
        su -c "/bin/bash /home/pi/omnipy/scripts/update.sh &" pi
fi