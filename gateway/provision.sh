#!/usr/bin/env bash
set -euo pipefail

bash /tmp/ex200-lab-interface.sh 172.25.250.254

dnf install -y \
  chrony dnsmasq firewalld httpd-tools nginx nfs-utils podman \
  policycoreutils-python-utils curl

systemctl enable --now sshd
systemctl enable --now firewalld

if ! id student >/dev/null 2>&1; then
  useradd --create-home student
fi
printf '%s\n' 'student:redhat' | chpasswd
echo 'student ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/student
chmod 0440 /etc/sudoers.d/student

cat > /etc/systemd/system/ex200-dns-address.service <<'UNIT'
[Unit]
Description=EX200 lab DNS service address
After=network-online.target
Wants=network-online.target
Before=dnsmasq.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/ip address replace 172.25.254.254/32 dev lo
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now ex200-dns-address.service

cat > /etc/dnsmasq.d/ex200-lab.conf <<'DNS'
bind-dynamic
listen-address=127.0.0.1,172.25.250.254,172.25.254.254
domain-needed
bogus-priv
address=/gateway.lab.example.com/172.25.250.254
address=/node1.lab.example.com/172.25.250.10
address=/node2.lab.example.com/172.25.250.11
address=/classroom.example.com/172.25.250.254
address=/content.example.com/172.25.250.254
address=/registry.lab.example.com/172.25.250.254
DNS
systemctl enable --now dnsmasq
systemctl restart dnsmasq

cat > /etc/chrony.conf <<'CHRONY'
pool 2.pool.ntp.org iburst
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
allow 172.25.250.0/24
local stratum 10
CHRONY
systemctl enable --now chronyd
systemctl restart chronyd

install -d -m 0755 /srv/nfs/home/remoteuser6
if ! id remoteuser6 >/dev/null 2>&1; then
  useradd --uid 2006 --home-dir /srv/nfs/home/remoteuser6 --no-create-home remoteuser6
fi
chown remoteuser6:remoteuser6 /srv/nfs/home/remoteuser6
chmod 0700 /srv/nfs/home/remoteuser6
if [[ ! -e /srv/nfs/home/remoteuser6/README.txt ]]; then
  printf '%s\n' 'Welcome to the EX200 NFS home.' > /srv/nfs/home/remoteuser6/README.txt
fi
chown remoteuser6:remoteuser6 /srv/nfs/home/remoteuser6/README.txt
cat > /etc/exports <<'EXPORTS'
/srv/nfs 172.25.250.0/24(ro,fsid=0,crossmnt,no_subtree_check,sync)
/srv/nfs/home 172.25.250.0/24(rw,no_subtree_check,sync,root_squash)
EXPORTS
semanage fcontext -a -t public_content_rw_t '/srv/nfs(/.*)?' 2>/dev/null || \
  semanage fcontext -m -t public_content_rw_t '/srv/nfs(/.*)?'
restorecon -RF /srv/nfs
setsebool -P nfs_export_all_rw on
systemctl enable --now nfs-server
exportfs -rav

install -d -m 0755 /var/www/ex200/containers
install -m 0644 /tmp/ex200-Containerfile /var/www/ex200/containers/Containerfile
install -m 0644 /tmp/ex200-worker.py /var/www/ex200/containers/worker.py
restorecon -RF /var/www/ex200

rm -f /etc/nginx/conf.d/default.conf
install -d -o nginx -g nginx -m 0755 /var/cache/nginx/ex200
dns_resolver=$(awk '$1 == "nameserver" && $2 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ {print $2; exit}' /etc/resolv.conf)
if [[ -z "$dns_resolver" ]]; then
  echo "No IPv4 DNS resolver is configured for the repository proxy." >&2
  exit 1
fi
cat > /etc/nginx/conf.d/ex200-lab.conf <<'NGINX'
proxy_cache_path /var/cache/nginx/ex200 levels=1:2 keys_zone=ex200_repo:20m
                 max_size=2g inactive=7d use_temp_path=off;

server {
    listen 80 default_server;
    server_name content.example.com classroom.example.com registry.lab.example.com 172.25.250.254;
    resolver __EX200_DNS_RESOLVER__ ipv6=off valid=300s;
    resolver_timeout 10s;
    proxy_cache_key "ex200-almalinux10-v1:$scheme$request_method$host$request_uri";

    location = /health {
        alias /var/www/ex200/health;
    }

    location /containers/ {
        alias /var/www/ex200/containers/;
        autoindex off;
    }

    location = /repos/ex200.repo {
        default_type text/plain;
        return 200 "[BaseOS]\nname=AlmaLinux 10 BaseOS via EX200 gateway\nbaseurl=http://content.example.com/almalinux/10/BaseOS/x86_64/os\nenabled=1\ngpgcheck=1\ngpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux-10\n\n[AppStream]\nname=AlmaLinux 10 AppStream via EX200 gateway\nbaseurl=http://content.example.com/almalinux/10/AppStream/x86_64/os\nenabled=1\ngpgcheck=1\ngpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux-10\n";
    }

    location /almalinux/10/BaseOS/x86_64/os/ {
        set $almalinux_repository_host repo.almalinux.org;
        rewrite ^/almalinux/10/BaseOS/x86_64/os/(.*)$ /almalinux/10/BaseOS/x86_64/os/$1 break;
        proxy_cache ex200_repo;
        proxy_cache_lock on;
        proxy_cache_valid 200 302 7d;
        proxy_cache_valid 404 1m;
        proxy_set_header Host repo.almalinux.org;
        proxy_ssl_server_name on;
        proxy_ssl_name repo.almalinux.org;
        proxy_pass https://$almalinux_repository_host;
    }

    location /almalinux/10/AppStream/x86_64/os/ {
        set $almalinux_repository_host repo.almalinux.org;
        rewrite ^/almalinux/10/AppStream/x86_64/os/(.*)$ /almalinux/10/AppStream/x86_64/os/$1 break;
        proxy_cache ex200_repo;
        proxy_cache_lock on;
        proxy_cache_valid 200 302 7d;
        proxy_cache_valid 404 1m;
        proxy_set_header Host repo.almalinux.org;
        proxy_ssl_server_name on;
        proxy_ssl_name repo.almalinux.org;
        proxy_pass https://$almalinux_repository_host;
    }
}
NGINX
sed -i "s/__EX200_DNS_RESOLVER__/${dns_resolver}/" /etc/nginx/conf.d/ex200-lab.conf
nginx -t
systemctl enable --now nginx
systemctl restart nginx
setsebool -P httpd_can_network_connect on

install -d -m 0700 /var/lib/ex200-registry/auth
install -d -m 0755 /var/lib/ex200-registry/data
htpasswd -Bbn student redhat > /var/lib/ex200-registry/auth/htpasswd
chmod 0600 /var/lib/ex200-registry/auth/htpasswd

cat > /etc/containers/registries.conf.d/050-ex200-lab.conf <<'REGISTRY'
[[registry]]
location = "registry.lab.example.com:5000"
insecure = true
REGISTRY

podman pull docker.io/library/registry:2
podman pull docker.io/library/python:3.13-alpine
if podman container exists ex200-registry; then
  systemctl stop ex200-registry.service
  podman rm -f ex200-registry
fi
podman create \
  --name ex200-registry \
  -p 5000:5000 \
  -e REGISTRY_AUTH=htpasswd \
  -e REGISTRY_AUTH_HTPASSWD_REALM='EX200 Practice Registry' \
  -e REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd \
  -v /var/lib/ex200-registry/data:/var/lib/registry:Z \
  -v /var/lib/ex200-registry/auth:/auth:ro,Z \
  docker.io/library/registry:2

cat > /etc/systemd/system/ex200-registry.service <<'UNIT'
[Unit]
Description=EX200 local container registry
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/podman start --attach ex200-registry
ExecStop=/usr/bin/podman stop --time 10 ex200-registry
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now ex200-registry

for attempt in $(seq 1 60); do
  if curl --fail --silent --user student:redhat http://127.0.0.1:5000/v2/ >/dev/null; then
    break
  fi
  if [[ "$attempt" == 60 ]]; then
    echo "The local container registry did not become ready." >&2
    exit 1
  fi
  sleep 2
done

podman tag docker.io/library/python:3.13-alpine localhost:5000/python:3.13-alpine
podman login --tls-verify=false --username student --password redhat localhost:5000
podman push --tls-verify=false localhost:5000/python:3.13-alpine

nat_device=$(ip -4 route show default | awk 'NR == 1 {for (i = 1; i <= NF; i++) if ($i == "dev") print $(i + 1)}')
lab_device=$(ip -o -4 address show | awk '$4 ~ /^172\.25\.250\.254\// {print $2; exit}')
if [[ -z "$nat_device" || -z "$lab_device" ]]; then
  echo "Unable to identify gateway NAT and lab network interfaces." >&2
  exit 1
fi

nat_zone=$(firewall-cmd --get-default-zone)
firewall-cmd --permanent --zone="$nat_zone" --add-service=ssh >/dev/null
firewall-cmd --permanent --zone="$nat_zone" --add-masquerade >/dev/null
firewall-cmd --permanent --zone=trusted --add-source=172.25.250.0/24 >/dev/null
if ! firewall-cmd --permanent --get-policies | grep -qw ex200-trusted-to-external; then
  firewall-cmd --permanent --new-policy=ex200-trusted-to-external >/dev/null
fi
firewall-cmd --permanent --policy=ex200-trusted-to-external --add-ingress-zone=trusted >/dev/null
if firewall-cmd --permanent --policy=ex200-trusted-to-external --query-egress-zone=external >/dev/null; then
  firewall-cmd --permanent --policy=ex200-trusted-to-external --remove-egress-zone=external >/dev/null
fi
firewall-cmd --permanent --policy=ex200-trusted-to-external --add-egress-zone="$nat_zone" >/dev/null
firewall-cmd --permanent --policy=ex200-trusted-to-external --set-target=ACCEPT >/dev/null
firewall-cmd --reload

cat > /etc/sysctl.d/90-ex200-gateway.conf <<'SYSCTL'
net.ipv4.ip_forward = 1
SYSCTL
sysctl --system >/dev/null

mkdir -p /home/student/.ssh
cat > /home/student/.ssh/config <<'SSH'
Host node1
    HostName 172.25.250.10
    User student
    StrictHostKeyChecking accept-new

Host node2
    HostName 172.25.250.11
    User student
    StrictHostKeyChecking accept-new
SSH
chown -R student:student /home/student/.ssh
chmod 0700 /home/student/.ssh
chmod 0600 /home/student/.ssh/config

printf '%s\n' 'ok' > /var/www/ex200/health
restorecon /var/www/ex200/health

rm -f /tmp/ex200-Containerfile /tmp/ex200-worker.py
dnf clean all
