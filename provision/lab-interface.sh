#!/usr/bin/env bash
set -euo pipefail

lab_ip=${1:?A static lab IPv4 address is required}
if ip -o -4 address show | grep -Fq " $lab_ip/"; then
  exit 0
fi

nat_device=$(ip -4 route show default | awk 'NR == 1 {for (i = 1; i <= NF; i++) if ($i == "dev") print $(i + 1)}')
if [[ -z "$nat_device" ]]; then
  echo "Unable to identify the NAT interface before configuring the lab interface." >&2
  exit 1
fi

lab_device=""
while IFS=: read -r device type state; do
  if [[ "$type" == "ethernet" && "$state" != "unmanaged" && "$device" != "$nat_device" ]]; then
    if [[ -n "$lab_device" ]]; then
      echo "Unable to identify a unique lab interface; found '$lab_device' and '$device'." >&2
      exit 1
    fi
    lab_device=$device
  fi
done < <(nmcli -t -f DEVICE,TYPE,STATE device status)

if [[ -z "$lab_device" ]]; then
  echo "No secondary Ethernet interface is available for lab address $lab_ip." >&2
  exit 1
fi

connection=$(nmcli -t -f NAME,DEVICE connection show | awk -F: -v device="$lab_device" '$2 == device {print $1; exit}')
if [[ -z "$connection" ]]; then
  connection="ex200-lab"
  nmcli connection add type ethernet ifname "$lab_device" con-name "$connection" \
    ipv4.method manual ipv4.addresses "$lab_ip/24" ipv4.never-default yes \
    ipv6.method disabled
else
  nmcli connection modify "$connection" \
    ipv4.method manual ipv4.addresses "$lab_ip/24" \
    ipv4.gateway "" ipv4.dns "" ipv4.never-default yes \
    ipv6.method disabled
fi

nmcli connection up "$connection"
