#!/bin/bash
GATEWAY=$(ip route | grep default | awk '{print $3}')
sudo ip route del default 2>/dev/null
sudo ip route add default via $GATEWAY dev eth0
sudo rm /etc/resolv.conf
sudo bash -c 'echo -e "nameserver 8.8.8.8\nnameserver 1.1.1.1" > /etc/resolv.conf'
echo "WSL network reset complete"
