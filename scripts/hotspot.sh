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

IsWifiDisconnected()
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
     echo ${SSID_REPLY} | grep ${SSID_CLEAN} > /dev/null 2>&1
     if [[ $? ]]
     then
        return 0
     fi
done
return 1
}

WLAN_INTERFACE=wlan0
iw dev ${WLAN_INTERFACE} set power_save off
ACTIVE_MODE=
while true;
do
    if [[ ${ACTIVE_MODE} == "ap" ]]; then
        echo "Running in access point mode, next check in 300 seconds"
        sleep 300
        if [[ areKnownNetworksNearBy ]]; then
              systemctl stop omnipy.service
              KillHotSpot
              echo "Hotspot Deactivated, Bringing Wifi Up"
              CreateWifiClient
              if [[ IsWifiDisconnected ]]; then
                    echo "Failed to connect to wifi, going back into hotspot mode"
                    CreateHotSpot
                    ACTIVE_MODE="ap"
              else
                    ACTIVE_MODE="client"
              fi
              systemctl start omnipy.service
        fi
    elif [[ ${ACTIVE_MODE} == "client" ]]; then
        echo "Running in wi-fi client mode, next check in 60 seconds"
        sleep 60
        if [[ IsWifiDisconnected ]]; then
            systemctl stop omnipy.service
            echo "Wi-fi disconnected, retrying"
            CreateWifiClient
            if [[ IsWifiDisconnected ]]; then
                    echo "No wi-fi connection, creating hot-spot"
                    CreateHotSpot
                    ACTIVE_MODE="ap"
            else
                echo "Wi-fi connection re-established"
            fi
            systemctl start omnipy.service
        fi
    else
        echo "Checking current network state"
        if [[ IsWifiDisconnected ]]; then
            echo "Wi-fi not connected, scanning"
            if [[ areKnownNetworksNearBy ]]; then
                echo "Found known networks, will try to connect"
                KillHotSpot
                CreateWifiClient
            fi
        fi

        if [[ IsWifiDisconnected ]]; then
            echo "No wi-fi connection, creating hotspot"
            CreateHotSpot
            ACTIVE_MODE="ap"
        else
            ACTIVE_MODE="client"
        fi
    fi
done