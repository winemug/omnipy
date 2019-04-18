#!/usr/bin/env bash
echo
echo Updating service scripts and restarting services

sudo chown -R pi.pi /home/pi

if [[ -f /home/pi/omnipy/scripts/btnap-custom.sh ]]
then
    sudo cp /home/pi/omnipy/scripts/omnipy-pan.service /etc/systemd/system/
    sudo systemctl enable omnipy-pan.service
    sudo systemctl start omnipy-pan.service
fi

sudo cp /home/pi/omnipy/scripts/omnipy.service /etc/systemd/system/
sudo cp /home/pi/omnipy/scripts/omnipy-beacon.service /etc/systemd/system/

sudo systemctl enable omnipy.service
sudo systemctl enable omnipy-beacon.service
sudo systemctl start omnipy.service
sudo systemctl start omnipy-beacon.service
sudo systemctl daemon-reload

echo
echo ${bold}Configuration updated.${normal}
