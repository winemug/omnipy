#!/usr/bin/expect -f

set timeout 900

set prompt "#"

spawn sudo bluetoothctl
expect -re $prompt
send "power on\r"
sleep 1

expect -re $prompt
send "agent NoInputNoOutput\r"
sleep 1

expect -re $prompt
send "default-agent\r"
sleep 1

expect -re $prompt
send "agent DisplayOnly\r"
sleep 1

expect -re $prompt
send "default-agent\r"
sleep 1

expect -re $prompt
send "discoverable on\r"
sleep 1

expect -re $prompt
send "pairable on\r"
sleep 1

expect -re "Enter PIN code: "
sleep 3
send "3434\r"

expect -re "Connected: yes"
sleep 10
expect -re $prompt
send "discoverable off\r"
sleep 1

expect -re $prompt
send "pairable off\r"

send "quit\r"
expect eof