#!/usr/bin/env bash
# apt-get install with a hang guard (10-23: the runner's package mirror hung for 25+ minutes twice and held the
# 20:30 Reel). Every request has a timeout; after a failed try the main Ubuntu archive replaces the runner's
# own mirror (that change stays for later apt calls, e.g. Playwright's browser libraries).
#   bash .github/apt_install.sh ffmpeg
set -u -o pipefail
# the man-db trigger after an install can take minutes on GitHub's runners; we never read man pages there
sudo rm -f /var/lib/man-db/auto-update 2>/dev/null || true
echo "man-db man-db/auto-update boolean false" | sudo debconf-set-selections 2>/dev/null || true
for i in 1 2 3; do
  if [ "$i" -ge 2 ]; then
    sudo sed -i 's#http://azure\.archive\.ubuntu\.com#http://archive.ubuntu.com#g' \
      /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list 2>/dev/null || true
  fi
  if timeout 120 sudo apt-get update -qq -o Acquire::Retries=2 -o Acquire::http::Timeout=20 \
     && timeout 300 sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
          -o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o DPkg::Lock::Timeout=60 "$@" | tail -n 25; then
    exit 0
  fi
  echo "apt try $i failed or hung; trying again"
  sleep 5
done
exit 1
