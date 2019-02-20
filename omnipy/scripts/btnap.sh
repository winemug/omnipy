#!/bin/bash
killall bt-network > /dev/null 2>&1
while true
do
    bt-network -c $1 nap > /dev/null 2>&1
    sleep 5
done
