#!/usr/bin/env bash
set -euo pipefail

install -d -m 0755 /etc/ssh/sshd_config.d
if [[ "$(hostname -s)" == "node2" ]]; then
  if id student >/dev/null 2>&1; then
    password_status=$(passwd -S student | awk '{print $2}')
    if [[ "$password_status" != "L" ]]; then
      passwd --lock student
    fi
    usermod --shell /sbin/nologin student
  fi
  rm -f /etc/sudoers.d/student /etc/ssh/sshd_config.d/60-ex200-lab.conf
else
  if ! id student >/dev/null 2>&1; then
    useradd --create-home student
  fi

  password_status=$(passwd -S student | awk '{print $2}')
  if [[ "$password_status" != "P" ]]; then
    printf '%s\n' 'student:redhat' | chpasswd
  fi

  cat > /etc/ssh/sshd_config.d/60-ex200-lab.conf <<'SSH'
Match Address 172.25.250.0/24
    PasswordAuthentication yes
SSH
fi

sshd -t
systemctl enable --now sshd
systemctl reload sshd
