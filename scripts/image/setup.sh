#!/usr/bin/env bash
sudo passwd pi
sudo apt update
sudo apt upgrade

sudo raspi-config
# hostname: omnipy
# wifi: NO, noway, omnipyway
# adv, memory split, 16
#sudo reboot

sudo apt install -y bluez-tools python3 python3-pip git build-essential libglib2.0-dev vim jq libdbus-1-dev libudev-dev libical-dev libreadline-dev rpi-update expect
#sudo apt install -y hostapd dnsmasq

sudo systemctl disable hostapd
sudo systemctl unmask hostapd
sudo systemctl disable dnsmasq

/bin/rm /boot/.firmware_revision
sudo cp /home/pi/omnipy/scripts/image/rpiupdate.sh /usr/bin/rpiupdate
sudo ROOT_PATH=/ BOOT_PATH=/boot SKIP_DOWNLOAD=0 SKIP_REPODELETE=1 SKIP_BACKUP=1 UPDATE_SELF=0 RPI_REBOOT=1 BRANCH=next rpi-update 502a515156eebbfd3cc199de8f38a975c321f20d

cd /home/pi

#https://raspberrypi.stackexchange.com/questions/66540/installing-bluez-5-44-onto-raspbian
wget https://mirrors.edge.kernel.org/pub/linux/bluetooth/bluez-5.50.tar.gz
tar xzf bluez-5.50.tar.gz
cd bluez-5.50
./configure --prefix=/usr --mandir=/usr/share/man --sysconfdir=/etc --localstatedir=/var --enable-experimental
make
sudo make install

cd /usr/lib/bluetooth/
sudo mv bluetoothd bluetoothd.old
sudo mv obexd obexd.old

sudo ln -s /usr/libexec/bluetooth/bluetoothd /usr/lib/bluetooth/bluetoothd
sudo ln -s /usr/libexec/bluetooth/obexd /usr/lib/bluetooth/obexd

sudo systemctl daemon-reload


git config --global user.email "omnipy@balya.net"
git config --global user.name "Omnipy Setup"

sudo pip3 install simplejson Flask cryptography requests

git clone https://github.com/winemug/omnipy.git
git clone https://github.com/winemug/bluepy.git

cd bluepy
python3 ./setup.py build
sudo python3 ./setup.py install

sudo chown -R pi.pi /home/pi

sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find /usr/lib -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo find /home/pi -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;

sudo apt autoremove

#sudo cp /home/pi/omnipy/scripts/image/default.dnsmasq /etc/default/dnsmasq
#sudo cp /home/pi/omnipy/scripts/image/default.hostapd /etc/default/hostapd
#sudo cp /home/pi/omnipy/scripts/image/hostapd.conf /etc/hostapd/
#sudo cp /home/pi/omnipy/scripts/image/dnsmasq.conf /etc/dnsmasq.d/
#sudo cp /home/pi/omnipy/scripts/image/dhcpcd.conf /etc/
sudo cp /home/pi/omnipy/scripts/image/rc.local /etc/

mkdir -p /home/pi/omnipy/data
rm /home/pi/omnipy/data/key
cp /home/pi/omnipy/scripts/recovery.key /home/pi/omnipy/data/key

sudo cp /home/pi/omnipy/scripts/omnipy.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy-beacon.service /etc/systemd/system/
sudo rm /etc/systemd/system/omnipy-pan.service

sudo systemctl enable omnipy.service
sudo systemctl enable omnipy-beacon.service
sudo systemctl start omnipy.service
sudo systemctl start omnipy-beacon.service

sudo touch /boot/omnipy-btsetup
sudo touch /boot/omnipy-pwreset
sudo touch /boot/omnipy-fwupdate

rm /home/pi/.bash_history
sudo halt

######

sudo umount /dev/sdh1
sudo umount /dev/sdh2
#shrink with /g/parted
sudo dcfldd if=/dev/sdh of=omnipy.img
#abort as appropriate
sudo ~/pishrink.sh omnipy.img omnipy2.img
rm omnipy.img
mv omnipy2.img omnipy.img
zip -9 omnipy.zip omnipy.img
