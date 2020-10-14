#qemu-system-arm -kernel c:\dev\qemu-rpi-kernel\kernel-qemu-4.19.50-buster -cpu arm1176 -m 256 -M versatilepb -dtb c:\dev\qemu-rpi-kernel\versatile-pb-buster.dtb -no-reboot -serial stdio -append "root=/dev/sda2 panic=1 rootfstype=ext4 rw" -drive "file=c:\dev\omnipy.img,index=0,media=disk,format=raw" -net user,hostfwd=tcp::5022-:22 -net nic

#!/usr/bin/env bash
sudo touch /boot/ssh

sudo passwd pi
sudo raspi-config

# hostname: omnipy-dev
#? adv, memory split, 16
# enable predictive intf names
# timezone other/utc
# adv resize fs
# reboot


sudo apt update && sudo apt upgrade -y
sudo apt autoremove

### omnipy-bare image end

### omnipy-base image start

sudo apt install -y screen git python3 python3-pip vim jq bluez-tools libglib2.0-dev python3-rpi.gpio ntp fake-hwclock \
bluez-tools python3-pip python3-venv gobject-introspection libgirepository1.0-dev libcairo2-dev expect build-essential \
libdbus-1-dev libudev-dev libical-dev libreadline-dev rpi-update

git config --global user.email "omnipy@balya.net"
git config --global user.name "Omnipy Setup"
git clone https://github.com/winemug/omnipy.git
git clone https://github.com/winemug/bluepy.git

mkdir -p /home/pi/omnipy/data
rm /home/pi/omnipy/data/key
cp /home/pi/omnipy/scripts/image/recovery.key /home/pi/omnipy/data/key

### omnipy-base image end


### omnipy-sw image start
python3 -m pip install --user pip --upgrade
python3 -m pip install --user virtualenv --upgrade

python3 -m venv /home/pi/v
source /home/pi/v/bin/activate
python3 -m pip install pip --upgrade
python3 -m pip install setuptools --upgrade

cd /home/pi/bluepy
python3 setup.py build
python3 setup.py install

#creating /home/pi/v/lib/python3.7/site-packages/bluepy-1.3.0-py3.7.egg
#Extracting bluepy-1.3.0-py3.7.egg to /home/pi/v/lib/python3.7/site-packages
#Adding bluepy 1.3.0 to easy-install.pth file
#Installing blescan script to /home/pi/v/bin
#Installing sensortag script to /home/pi/v/bin
#Installing thingy52 script to /home/pi/v/bin

sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hciconfig`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which hcitool`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which btmgmt`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-agent`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-network`
sudo setcap 'cap_net_raw,cap_net_admin+eip' `which bt-device`
sudo find /home/pi -name bluepy-helper -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo find /home/pi -name blescan -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo find /home/pi -name sensortag -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;
sudo find /home/pi -name thingy52 -exec setcap 'cap_net_raw,cap_net_admin+eip' {} \;

python3 -m pip install rpi-gpio simplejson paho-mqtt requests crypto flask pycrypto


# services

cd /home/pi/omnipy
git stash
git pull

chmod -R 755 /home/pi/omnipy/scripts/*.sh
chmod -R 755 /home/pi/omnipy/*.py
sudo cp /home/pi/omnipy/scripts/image/rc.local /etc/
sudo cp /home/pi/omnipy/scripts/image/omnipy-rest.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-mq.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-beacon.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-pan.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-sync.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/image/omnipy-messenger.service /etc/systemd/system/

sudo systemctl enable omnipy-rest.service
sudo systemctl enable omnipy-beacon.service
sudo systemctl enable omnipy-pan.service

#sudo systemctl start omnipy-rest.service
#sudo systemctl start omnipy-beacon.service
#sudo systemctl start omnipy-pan.service

#sudo touch /boot/omnipy-pwreset
#sudo touch /boot/omnipy-expandfs
#sudo touch /boot/omnipy-btreset

sudo raspi-config
# hostname omnipy
exit

# version update
# halt

### clean-up via scp

#fin


sudo umount /dev/sdh1
sudo umount /dev/sdh2

#sudo gparted /dev/sdh
#shrink with /g/parted 3192MiB

sudo e2fsck -f /dev/sdh2
sudo resize2fs /dev/sdh2 3G

sudo fdisk /dev/sdh

-p

#Device     Boot  Start       End   Sectors  Size Id Type
#/dev/sdh1         8192    532479    524288  256M  c W95 FAT32 (LBA)
#/dev/sdh2       532480 124735487 124203008 59.2G 83 Linux

-d 2
-n p 2 532480 +3145728K -N
-p

#Device     Boot  Start     End Sectors  Size Id Type
#/dev/sdh1         8192  532479  524288  256M  c W95 FAT32 (LBA)
#/dev/sdh2       532480 6823935 6291456    3G 83 Linux

-w

sudo e2fsck -f /dev/sdh2

sudo mount /dev/sdh2 /mnt
sudo dcfldd if=/dev/zero of=/mnt/zero.txt
sudo rm /mnt/zero.txt
sudo sync
sudo umount /dev/sdh2
sudo sync

sudo dcfldd if=/dev/sdh of=omnipy.img bs=512 count=6389760
zip -9 omnipy.img.zip omnipy.img
