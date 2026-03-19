#!/usr/bin/env bash
# Setup a3m on LXC Ubuntu 22.04 (without Docker)
# Run this script inside the LXC container with sudo or as root.
# Usage: sudo ./scripts/setup-lxc-ubuntu22.sh

set -e

export DEBIAN_FRONTEND=noninteractive

echo "==> Updating system and installing base packages..."
apt-get update
apt-get install -y --no-install-recommends \
    apt-transport-https \
    curl \
    git \
    gpg-agent \
    locales \
    locales-all \
    software-properties-common

echo "==> Setting locale..."
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

echo "==> Adding Archivematica and Ubuntu repos..."
curl -s https://packages.archivematica.org/GPG-KEY-archivematica | apt-key add -
add-apt-repository --no-update --yes "deb [arch=amd64] http://packages.archivematica.org/1.15.x/ubuntu-externals jammy main"
add-apt-repository --no-update --yes "deb http://archive.ubuntu.com/ubuntu/ jammy multiverse"
add-apt-repository --no-update --yes "deb http://archive.ubuntu.com/ubuntu/ jammy-security universe"
add-apt-repository --no-update --yes "deb http://archive.ubuntu.com/ubuntu/ jammy-updates multiverse"

echo "==> Adding MediaArea repo..."
curl -so /tmp/repo-mediaarea_1.0-25_all.deb -L https://mediaarea.net/repo/deb/repo-mediaarea_1.0-25_all.deb
dpkg -i /tmp/repo-mediaarea_1.0-25_all.deb || true

echo "==> Installing system dependencies (ffmpeg, ImageMagick, Java, etc.)..."
apt-get update
apt-get install -y --no-install-recommends \
    atool \
    bulk-extractor \
    ffmpeg \
    ghostscript \
    coreutils \
    libavcodec-extra \
    imagemagick \
    inkscape \
    jhove \
    libimage-exiftool-perl \
    libevent-dev \
    libjansson4 \
    mediaconch \
    mediainfo \
    openjdk-8-jre-headless \
    p7zip-full \
    pbzip2 \
    pst-utils \
    rsync \
    sleuthkit \
    sqlite3 \
    tesseract-ocr \
    tree \
    unar \
    unrar-free \
    uuid

echo "==> Adding deadsnakes PPA and installing Python 3.12..."
add-apt-repository --yes ppa:deadsnakes/ppa
apt-get update
apt-get install -y python3.12 python3.12-venv python3.12-dev

echo "==> Installing uv for the current user (run as the user who will run a3m)..."
if [[ -n "${SUDO_USER:-}" ]]; then
    su - "$SUDO_USER" -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    echo "Add to your shell profile: export PATH=\"\$HOME/.local/bin:\$PATH\""
else
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo ""
echo "==> Setup complete. Next steps (as the user who will run a3m):"
echo "    1. Ensure uv is in PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "    2. cd to the a3m project directory"
echo "    3. Run: uv sync --frozen --no-dev --python 3.12"
echo "    4. Run the server: ./.venv/bin/a3md"
echo ""
