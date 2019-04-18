while true
do
    killall -9 bt-agent > /dev/null 2>&1
    /usr/bin/bt-agent -c NoInputNoOutput -d
    killall -9 bt-network > /dev/null 2>&1
    /usr/bin/bt-network -c $addr nap > /dev/null 2>&1
    sleep 30
done
