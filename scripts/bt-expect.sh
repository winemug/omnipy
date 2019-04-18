#!/usr/bin/expect -f

set prompt "#"
set address [lindex $argv 0]

spawn sudo bluetoothctl -a
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

expect -re $prompt
send "pairable on\r"
sleep 1

expect -re "Enter PIN code: "
send "3434\r"

expect -re "Connected: yes"
expect -re $prompt
send "trust $address\r"
sleep 2

expect -re "trust succeeded"
sleep 3

send_user "\nShould be paired now.\r"
send "quit\r"
expect eof