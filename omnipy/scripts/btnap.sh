#!/bin/bash
sudo killall bt-network > /dev/null 2>&1
while true
do
    sudo bt-network -c $1 nap > /dev/null 2>&1
    sleep 5
done
