#!/usr/bin/env bash
set -euo pipefail

case "$(hostname -s)" in
  node1) bash /tmp/ex200-lab-interface.sh 172.25.250.10 ;;
  node2) bash /tmp/ex200-lab-interface.sh 172.25.250.11 ;;
  *)
    echo "Unexpected node hostname: $(hostname -s)" >&2
    exit 1
    ;;
esac

for attempt in $(seq 1 180); do
  if curl --fail --silent --max-time 2 http://172.25.250.254/health >/dev/null; then
    break
  fi
  if [[ "$attempt" == 180 ]]; then
    echo "The EX200 gateway did not become ready at 172.25.250.254." >&2
    exit 1
  fi
  sleep 2
done

lab_connection=""
nat_connection=""
while IFS=: read -r connection device; do
  [[ -n "$device" && "$device" != "lo" ]] || continue
  addresses=$(nmcli -g IP4.ADDRESS connection show "$connection")
  if grep -q '^172\.25\.250\.' <<< "$addresses"; then
    lab_connection=$connection
  fi
  if [[ "$connection" != "$lab_connection" && "$device" != "lo" ]]; then
    nat_connection=$connection
  fi
done < <(nmcli -t -f NAME,DEVICE connection show --active)

if [[ -z "$lab_connection" || -z "$nat_connection" || "$lab_connection" == "$nat_connection" ]]; then
  echo "Unable to identify both the lab and NAT NetworkManager connections." >&2
  exit 1
fi

echo "Configuring lab connection '$lab_connection' and NAT connection '$nat_connection'."
restorecon -RF /etc/NetworkManager/system-connections
nmcli connection modify "$lab_connection" \
  ipv4.gateway 172.25.250.254 \
  ipv4.dns 172.25.254.254 \
  ipv4.never-default no \
  ipv4.route-metric 50
nmcli connection modify "$nat_connection" ipv4.never-default yes
nmcli connection up "$lab_connection"

network_ready=false
for attempt in $(seq 1 10); do
  if ip -4 route show default | grep -Fq '172.25.250.254' &&
    grep -Eq '^[[:space:]]*nameserver[[:space:]]+172\.25\.254\.254' /etc/resolv.conf; then
    network_ready=true
    break
  fi
  sleep 1
done
if [[ "$network_ready" != true ]]; then
  echo "The lab connection did not install the gateway default route and DNS resolver." >&2
  ip -4 route show default >&2
  cat /etc/resolv.conf >&2
  exit 1
fi
