killall bt-network > /dev/null 2>&1
while true
do
    bt-network -c $addr nap > /dev/null 2>&1
    sleep 5
done
