#!/usr/bin/env bash
set -euo pipefail

dnf install -y \
  autofs chrony cronie curl firewalld httpd lvm2 nfs-utils \
  policycoreutils-python-utils podman acl tar tuned

install -d -m 0755 /etc/containers/registries.conf.d
cat > /etc/containers/registries.conf.d/050-ex200-lab.conf <<'REGISTRY'
[[registry]]
location = "registry.lab.example.com:5000"
insecure = true
REGISTRY

systemctl enable --now chronyd
systemctl enable --now crond
systemctl enable --now firewalld
systemctl enable --now tuned

if [[ "$(hostname -s)" == "node1" ]]; then
  if ! id remoteuser6 >/dev/null 2>&1; then
    useradd --uid 2006 --create-home --home-dir /home/guests/remoteuser6 remoteuser6
  fi
  printf '%s\n' 'remoteuser6:redhat' | chpasswd
fi

mkdir -p /var/www/html
printf '%s\n' 'EX200 practice web server' > /var/www/html/index.html

if [[ "$(hostname -s)" == "node2" ]]; then
  passwd --lock root
  tuned-adm profile balanced
else
  if ! id student >/dev/null 2>&1; then
    useradd --create-home student
  fi
  printf '%s\n' 'student:redhat' | chpasswd
  echo 'student ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/student
  chmod 0440 /etc/sudoers.d/student
fi

dnf clean all
