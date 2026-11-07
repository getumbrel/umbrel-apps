#!/usr/bin/env bash
# Runs on every container start of the plain Debian image.
# umbrelOS does not copy this file on app updates: existing installs keep the
# version they were installed with, so changes here reach fresh installs only.
set -eu
log() { echo "[devbox] $*"; }

# Packages live in the container layer: installed once per container, again after recreate/update
if [ ! -x /usr/sbin/sshd ] || [ ! -x /usr/local/bin/ttyd ]; then
  log "Installing base packages"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    openssh-server openssh-sftp-server sudo \
    ca-certificates curl git less nano procps
  rm -rf /var/lib/apt/lists/*

  # ttyd is not packaged for Debian trixie; use the pinned upstream static build
  arch=$(uname -m)
  case "$arch" in
    x86_64) sum=8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55 ;;
    aarch64) sum=b38acadd89d1d396a0f5649aa52c539edbad07f4bc7348b27b4f4b7219dd4165 ;;
    *) log "Unsupported architecture: $arch"; exit 1 ;;
  esac
  curl -fsSL -o /tmp/ttyd "https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.$arch"
  echo "$sum  /tmp/ttyd" | sha256sum -c -
  install -m 0755 /tmp/ttyd /usr/local/bin/ttyd
  rm /tmp/ttyd
fi

id dev >/dev/null 2>&1 || useradd -u 1000 -U -M -d /home/dev -s /bin/bash dev
echo 'dev ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/dev
chmod 0440 /etc/sudoers.d/dev
echo "dev:$PASSWORD" | chpasswd

chown dev:dev /home/dev
[ -f /home/dev/.bashrc ] || runuser -u dev -- cp -rn /etc/skel/. /home/dev/
install -d -o dev -g dev -m 0700 /home/dev/.ssh
install -d -o dev -g dev /home/dev/.devbox

# Persistent host key, so clients see the same fingerprint after updates
key=/data/hostkeys/ssh_host_ed25519_key
[ -f "$key" ] || ssh-keygen -q -t ed25519 -N '' -f "$key"
fingerprint=$(ssh-keygen -lf "$key.pub" | cut -d' ' -f2)

cat > /etc/ssh/sshd_config.d/devbox.conf <<EOF
HostKey $key
PermitRootLogin no
AllowUsers dev
PasswordAuthentication yes
KbdInteractiveAuthentication no
PrintMotd no
EOF
mkdir -p /run/sshd

cat > /etc/devbox-welcome <<EOF

  Devbox - isolated Debian environment

  SSH / SFTP   ssh -p $SSH_PORT dev@$SSH_HOST
  Password     the app password shown in umbrelOS, or use an SSH key
  Host key     $fingerprint

  Add an SSH key    echo 'ssh-ed25519 AAAA...' >> ~/.ssh/authorized_keys
  Umbrel folder     ~/umbrel (choose a folder in the app settings)
  sudo              passwordless

  Only /home/dev is kept across app updates. Put system setup such as
  "apt-get install -y ..." in ~/.devbox/setup.sh: it runs as root on every start.

EOF
cat > /etc/profile.d/devbox-welcome.sh <<'EOF'
case $- in *i*) cat /etc/devbox-welcome ;; esac
EOF

if [ -f /home/dev/.devbox/setup.sh ]; then
  log "Running ~/.devbox/setup.sh"
  bash /home/dev/.devbox/setup.sh || log "setup.sh failed with exit code $?, continuing"
fi

trap 'kill $(jobs -p) 2>/dev/null; exit 0' TERM INT
ttyd -W -p 7681 -t titleFixed=Devbox runuser -l dev &
/usr/sbin/sshd -D -e &
log "Ready: web terminal on 7681, SSH on $SSH_PORT"
wait -n
log "A service exited, restarting container"
exit 1
