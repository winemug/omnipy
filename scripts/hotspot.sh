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

CleanUp()
{
    systemctl stop hostapd
    systemctl stop dnsmasq
    wpa_cli terminate ${WLAN_INTERFACE} >/dev/null 2>&1
    ip addr flush ${WLAN_INTERFACE}
    ifconfig ${WLAN_INTERFACE} down
    ip link set dev ${WLAN_INTERFACE} down
    rm -r /var/run/wpa_supplicant >/dev/null 2>&1
}

CreateHotSpot()
{
    CleanUp
    echo "Creating HotSpot"
    ip a add 10.0.34.1/24 brd + dev ${WLAN_INTERFACE}
    ip link set dev ${WLAN_INTERFACE} up
    dhcpcd -k ${WLAN_INTERFACE} >/dev/null 2>&1
    systemctl start dnsmasq
    systemctl start hostapd
}

ConnectToWifi()
{
    CleanUp
    echo "Starting WiFi connection"
    ifconfig ${WLAN_INTERFACE} up
    ip link set dev ${WLAN_INTERFACE} up
    dhcpcd  -n ${WLAN_INTERFACE} >/dev/null 2>&1
    wpa_supplicant -B -i ${WLAN_INTERFACE} -c /etc/wpa_supplicant/wpa_supplicant.conf >/dev/null 2>&1
	echo "Waiting 20 seconds"
    sleep 20 #give time for connection to be completed to router
    return IsWifiConnected
}

IsWifiConnected()
{
	wpa_cli -i ${WLAN_INTERFACE} status | grep 'ip_address' >/dev/null 2>&1
	return $?
}

areKnownNetworksNearBy()
{
SSID_REGISTERED=$(awk '/ssid="/{ print $0 }' /etc/wpa_supplicant/wpa_supplicant.conf | awk -F'ssid=' '{ print $2 }' ORS=',' | sed 's/\"/''/g' | sed 's/,$//')

SSID_AVAILABLE=`iw dev ${WLAN_INTERFACE} scan ap-force | grep "SSID:" | cut -d ' ' -f 2`

for SSID in ${SSID_REGISTERED};
do
     [[ $SSID_AVAILABLE =~ (^|[[:space:]])$SSID($|[[:space:]]) ]] && return 0
done

return 1
}

HOT_SPOT_FILE=/boot/omnipy-hotspot
WLAN_INTERFACE=wlan0
iw dev ${WLAN_INTERFACE} set power_save off

if [[ -z "${SSID_REGISTERED}" ]]; then
    echo "No SSIDs registered"
    if [[ -f ${HOT_SPOT_FILE} ]]; then
        echo "Hot spot is enabled permanently"
        ACTIVE_MODE="ap-only"
    else
        echo "Wireless networking is disabled"
        ACTIVE_MODE="none"
    fi
else
    echo "Found SSID entries in wpa-config"
    if [[ -f ${HOT_SPOT_FILE} ]]; then
        echo "Hot spot is enabled permanently"
        ACTIVE_MODE=
    else
        echo "Hotspot is disabled"
        ACTIVE_MODE="client-only"
    fi
fi

if [[ ${ACTIVE_MODE} == "none" ]]; then
    exit 0
fi

if [[ ${ACTIVE_MODE} == "ap-only" ]]; then
    CreateHotSpot
    exit 0
fi

while true;
do
    if [[ ${ACTIVE_MODE} == "ap" ]]; then
        sleep 300
        if areKnownNetworksNearBy; then
              systemctl stop omnipy-beacon.service
              systemctl stop omnipy.service
              echo "Known networks are nearby, deactivating hotspot and connecting to wi-fi"
              CreateWifiClient
              if ! IsWifiConnected; then
                    echo "Failed to connect to wifi, going back into hotspot mode"
                    CreateHotSpot
                    ACTIVE_MODE="ap"
              else
                    ACTIVE_MODE="client"
              fi
              systemctl restart omnipy-beacon.service
              systemctl stop omnipy.service
              systemctl start omnipy.service

        fi
    elif [[ ${ACTIVE_MODE} == "client" ]]; then
        sleep 60
        if ! IsWifiConnected; then
            echo "Wi-fi disconnected, retrying"
            CreateWifiClient
            if ! IsWifiConnected; then
                    echo "No wi-fi connection, creating hot-spot"
                    CreateHotSpot
                    ACTIVE_MODE="ap"
            else
                echo "Wi-fi connection re-established"
            fi
            systemctl restart omnipy-beacon.service
            systemctl stop omnipy.service
            systemctl start omnipy.service

        fi
    elif [[ ${ACTIVE_MODE} == "client-only" ]]; then
        if ! IsWifiConnected; then
            echo "Wi-fi disconnected, retrying"
            CreateWifiClient
            if ! IsWifiConnected; then
                    echo "Wi-fi connection failed, waiting to retry"
                    sleep 120
            fi
        fi
    else
        echo "Checking current network state"
        if ! IsWifiConnected; then
            echo "Wi-fi not connected, scanning"
            if areKnownNetworksNearBy; then
                echo "Found known networks, will try to connect"
                CreateWifiClient
            fi
        fi

        if ! IsWifiConnected; then
            echo "No wi-fi connection, creating hotspot"
            CreateHotSpot
            systemctl restart omnipy-beacon.service
            systemctl stop omnipy.service
            systemctl start omnipy.service
            ACTIVE_MODE="ap"
        else
            echo "Wi-fi is connected"
            ACTIVE_MODE="client"
        fi
    fi
done
