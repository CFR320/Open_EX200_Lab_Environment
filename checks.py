"""Trusted, read-only checks executed on the lab VMs as root."""

CHECKS = {
    "network": r"""
test "$(hostname -s)" = node1 &&
ip -4 -o addr show | grep -Fq '172.25.250.10/24' &&
ip -4 route show default | grep -Fq '172.25.250.254' &&
grep -Eq '^[[:space:]]*nameserver[[:space:]]+172\.25\.254\.254' /etc/resolv.conf
""",
    "repositories": r"""
grep -RihE '^\[(BaseOS|AppStream)\]' /etc/yum.repos.d --include='*.repo' | sort -u | grep -q BaseOS &&
grep -RihE '^\[(BaseOS|AppStream)\]' /etc/yum.repos.d --include='*.repo' | grep -q AppStream &&
dnf repolist --enabled -q 2>/dev/null | grep -Eiq 'BaseOS' &&
dnf repolist --enabled -q 2>/dev/null | grep -Eiq 'AppStream'
""",
    "selinux-web": r"""
systemctl is-enabled --quiet httpd &&
systemctl is-active --quiet httpd &&
semanage port -l | awk '$1 == "http_port_t" && $2 == "tcp" {for (i = 3; i <= NF; i++) {gsub(/,/, "", $i); if ($i == 82) found = 1}} END {exit !found}' &&
firewall-cmd --query-port=82/tcp &&
curl --fail --silent --show-error --max-time 4 http://127.0.0.1:82/ >/dev/null
""",
    "cron": r"""
cron=$(crontab -u natasha -l 2>/dev/null) &&
printf '%s\n' "$cron" | grep -Fq '*/1 * * * * logger "EX200 in progress"' &&
printf '%s\n' "$cron" | grep -Fq '23 14 * * * /usr/bin/echo "welcome"'
""",
    "users-groups": r"""
getent group sysadms >/dev/null &&
id -nG natasha | tr ' ' '\n' | grep -qx sysadms &&
id -nG harry | tr ' ' '\n' | grep -qx sysadms &&
getent passwd sarah | awk -F: '$7 ~ /\/(nologin|false)$/ {ok=1} END {exit !ok}'
""",
    "collaborative-directory": r"""
test "$(stat -c '%U:%G' /home/sysadms 2>/dev/null)" = root:sysadms &&
test "$(stat -c '%a' /home/sysadms 2>/dev/null)" = 2770
""",
    "chrony": r"""
systemctl is-enabled --quiet chronyd &&
grep -REq '^[[:space:]]*(server|pool)[[:space:]]+classroom\.example\.com([[:space:]]|$)' /etc/chrony.conf /etc/chrony.d 2>/dev/null &&
chronyc sources -n 2>/dev/null | grep -Fq 172.25.250.254
""",
    "autofs": r"""
systemctl is-enabled --quiet autofs &&
grep -REq '^[[:space:]]*/home/guests[[:space:]]+' /etc/auto.master /etc/auto.master.d 2>/dev/null &&
grep -Riq 'remoteuser6.*classroom\.example\.com:/home/remoteuser6\|remoteuser6.*classroom\.example\.com:/home' /etc/auto.* /etc/auto.master.d 2>/dev/null &&
timeout 10 stat /home/guests/remoteuser6 >/dev/null 2>&1 &&
findmnt -rn -t nfs,nfs4 -T /home/guests/remoteuser6 >/dev/null
""",
    "bob-uid": r"""test "$(id -u bob 2>/dev/null)" = 2112""",
    "tar-archive": r"""
test -s /root/test.tar.gz &&
tar -tzf /root/test.tar.gz >/dev/null &&
tar -tzf /root/test.tar.gz | grep -Eq '(^|/)var/tmp/?$'
""",
    "find-sarah-files": r"""
test -d /root/find_user &&
while IFS= read -r -d '' source_file; do
  name=${source_file##*/}
  find /root/find_user -type f -name "$name" -print -quit | grep -q . || exit 1
done < <(find / -xdev -path /root/find_user -prune -o -type f -user sarah -print0 2>/dev/null)
""",
    "grep-passwd": r"""
test -s /root/search.txt &&
grep -Fq home /root/search.txt &&
while IFS= read -r line; do grep -Fxq "$line" /etc/passwd || exit 1; done < /root/search.txt
""",
    "container-image": r"""
runuser -u student -- podman image exists monitor
""",
    "container-service": r"""
test -f /home/student/.config/systemd/user/container-asciipdf.service &&
test -L /home/student/.config/systemd/user/default.target.wants/container-asciipdf.service &&
loginctl show-user student -p Linger --value | grep -qx yes &&
grep -Fq asciipdf /home/student/.config/systemd/user/container-asciipdf.service &&
grep -Fq /opt/files /home/student/.config/systemd/user/container-asciipdf.service &&
grep -Fq /opt/incoming /home/student/.config/systemd/user/container-asciipdf.service &&
grep -Fq /opt/processed /home/student/.config/systemd/user/container-asciipdf.service &&
grep -Fq /opt/outgoing /home/student/.config/systemd/user/container-asciipdf.service
""",
    "root-password-recovery": r"""
passwd -S root | awk '$2 == "P" {ok=1} END {exit !ok}'
""",
    "repositories-node2": r"""
grep -RihE '^\[(BaseOS|AppStream)\]' /etc/yum.repos.d --include='*.repo' | sort -u | grep -q BaseOS &&
grep -RihE '^\[(BaseOS|AppStream)\]' /etc/yum.repos.d --include='*.repo' | grep -q AppStream &&
dnf repolist --enabled -q 2>/dev/null | grep -Eiq 'BaseOS' &&
dnf repolist --enabled -q 2>/dev/null | grep -Eiq 'AppStream'
""",
    "swap": r"""
swapon --show=SIZE --bytes --noheadings | awk '{total += $1} END {exit !(total >= 536854528)}' &&
grep -Eq '^[^#].*[[:space:]]swap[[:space:]]' /etc/fstab
""",
    "logical-volume": r"""
test -b /dev/groupname/lvname &&
test "$(findmnt -n -o FSTYPE /mnt/lvname 2>/dev/null)" = ext3 &&
grep -Eq '^[^#].*/mnt/lvname[[:space:]]+ext3[[:space:]]' /etc/fstab
""",
    "resize-lv": r"""
bytes=$(blockdev --getsize64 /dev/groupname/lvname 2>/dev/null) &&
test "$bytes" -ge 209715200 &&
test "$bytes" -le 314572800
""",
    "tuned": r"""
systemctl is-enabled --quiet tuned &&
active=$(tuned-adm active 2>/dev/null | sed 's/.*: *//') &&
recommended=$(tuned-adm recommend 2>/dev/null) &&
test -n "$recommended" &&
test "$active" = "$recommended"
""",
    "mysearch-script": r"""
script=/usr/local/bin/mysearch
test -x "$script" || script=/root/mysearch.sh
test -x "$script" &&
grep -Eq 'find[[:space:]]+/usr/share' "$script" &&
(grep -Fq -- '-size +10M' "$script" || grep -Fq -- '-size 10M' "$script") &&
grep -Fq /root/myfiles "$script" &&
test -d /root/myfiles
""",
    "password-expiry": r"""
awk '$1 == "PASS_MAX_DAYS" && $2 == 30 {ok=1} END {exit !ok}' /etc/login.defs &&
while IFS=: read -r username _ uid _; do
  [ "$username" = vagrant ] && continue
  if [ "$uid" -ge 1000 ] || [ "$username" = root ]; then
    awk -F: -v user="$username" '$1 == user {found=1; if ($5 != 30) exit 1} END {if (!found) exit 1}' /etc/shadow || exit 1
  fi
done < /etc/passwd &&
awk -F: '$1 == "harry" && $5 == 30 {ok=1} END {exit !ok}' /etc/shadow
""",
    "harry-login-message": r"""
grep -Fq 'welcome to advantage pro' /home/harry/.bash_profile &&
grep -Eq '(^|[[:space:]])(echo|printf)[[:space:]]' /home/harry/.bash_profile
""",
    "sudo-group": r"""
getent group elite >/dev/null &&
visudo -c -q &&
grep -REq '^[[:space:]]*%elite[[:space:]]+ALL=\(ALL\)[[:space:]]+NOPASSWD:[[:space:]]+ALL' /etc/sudoers /etc/sudoers.d
""",
    "acl-fstab": r"""
test "$(stat -c '%U:%G' /var/tmp/fstab 2>/dev/null)" = root:root &&
! find /var/tmp/fstab -perm /111 -print -quit | grep -q . &&
getfacl -cp /var/tmp/fstab 2>/dev/null | grep -Eq '^user:sarah:rw-' &&
getfacl -cp /var/tmp/fstab 2>/dev/null | grep -Eq '^user:harry:---' &&
getfacl -cp /var/tmp/fstab 2>/dev/null | grep -Eq '^other::r--'
""",
}
