#!/usr/bin/env bash
#version 0.95-4-N/HS-I
#heavily revised: 2019-05-04 by Baris Kurtlutepe

#You may share this script on the condition a reference to RaspberryConnect.com
#must be included in copies or derivatives of this script.

#Network Wifi & Hotspot with Internet
#A script to switch between a wifi network and an Internet routed Hotspot
#A Raspberry Pi with a network port required for Internet in hotspot mode.
#Works at startup or with a seperate timer or manually without a reboot
#Other setup required find out more at
#http://www.raspberryconnect.com

CreateHotSpot()
{
    echo "Killing wifi client"
    wpa_cli terminate ${WLAN_INTERFACE} >/dev/null 2>&1
    echo "Creating HotSpot"
    systemctl stop dnsmasq > /dev/null 2>&1
    systemctl stop hostapd  > /dev/null 2>&1
    ifconfig ${WLAN_INTERFACE} down
    ifconfig ${WLAN_INTERFACE} up
    ip link set dev ${WLAN_INTERFACE} down
    ip a add 10.0.34.1/24 brd + dev ${WLAN_INTERFACE}
    ip link set dev ${WLAN_INTERFACE} up
    dhcpcd -k ${WLAN_INTERFACE} >/dev/null 2>&1
    systemctl start dnsmasq
    systemctl start hostapd
}

KillHotSpot()
{
    echo "Shutting Down HotSpot"
    ip link set dev ${WLAN_INTERFACE} down
    ifconfig ${WLAN_INTERFACE} down
    ifconfig ${WLAN_INTERFACE} up

    systemctl stop hostapd
    systemctl stop dnsmasq
    ip addr flush dev ${WLAN_INTERFACE}
    ip link set dev ${WLAN_INTERFACE} up
    dhcpcd  -n ${WLAN_INTERFACE} >/dev/null 2>&1
}

CreateWifiClient()
{
    echo "Starting WiFi connection"
    wpa_supplicant -B -i ${WLAN_INTERFACE} -c /etc/wpa_supplicant/wpa_supplicant.conf >/dev/null 2>&1
	echo "Waiting 20 seconds"
    sleep 20 #give time for connection to be completed to router
}

IsWifiConnected()
{
	wpa_cli -i ${WLAN_INTERFACE} status | grep 'ip_address' >/dev/null 2>&1
	return $?
}

areKnownNetworksNearBy()
{
SSID_LIST=$(awk '/ssid="/{ print $0 }' /etc/wpa_supplicant/wpa_supplicant.conf | awk -F'ssid=' '{ print $2 }' ORS=',' | sed 's/\"/''/g' | sed 's/,$//')
IFS=","

SSID_REPLY=`iw dev "$wifidev" scan ap-force | egrep "^BSS|SSID:"`

for SSID in ${SSID_LIST}
do
     SSID_CLEAN=$(echo ${SSID} | tr -d '\r')
     if [[ -z `echo ${SSID_REPLY} | grep ${SSID_CLEAN}` ]]
     then
        return 1
     fi
done
return 0
}

WLAN_INTERFACE=wlan0
iw dev ${WLAN_INTERFACE} set power_save off
ACTIVE_MODE=

while true;
do
    if [[ ${ACTIVE_MODE} eq "ap" ]]; then
        sleep 300
        if [[ areKnownNetworksNearBy ]]; then
              systemctl stop omnipy.service
              KillHotspot
              echo "Hotspot Deactivated, Bringing Wifi Up"
              CreateWifiClient
              if [[ ! IsWifiConnected ]]; then
                    echo "Failed to connect to wifi, going back into hotspot mode"
                    CreateHotSpot
                    ACTIVE_MODE="ap"
              else
                    ACTIVE_MODE="client"
              fi
              systemctl start omnipy.service
        fi
    elif [[ ${ACTIVE_MODE} eq "client" ]]; then
        sleep 60
        if [[ ! IsWifiConnected ]]; then
            systemctl stop omnipy.service
            echo "Wi-fi disconnected, retrying"
            CreateWifiClient
            if [[ ! IsWifiConnected ]]; then
                    echo "No wi-fi connection, creating hot-spot"
                    CreateHotSpot
                    ACTIVE_MODE="ap"
            else
                echo "Wi-fi connection re-established"
            fi
            systemctl start omnipy.service
        fi
    else
        if [[ areKnownNetworksNearBy ]]; then
            CreateWifiClient
        fi

        if [[ ! IsWifiConnected ]]; then
            echo "No wi-fi connection, creating hotspot"
            CreateHotSpot
            ACTIVE_MODE="ap"
        else
            ACTIVE_MODE="client"
        fi
    fi
done