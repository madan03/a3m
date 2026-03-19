# Running a3m in an LXC Ubuntu 22.04 Container (without Docker)

This guide explains how to run the a3m application inside an LXC Ubuntu 22.04 container, using the same dependencies as the Dockerfile but without Docker.

## Prerequisites

- A host with LXC/LXD installed
- An Ubuntu 22.04 (Jammy) LXC container already created, or ability to create one

---

## Step 1: Create and start the LXC container (if you don’t have one)

On your host (outside the container):

```bash
# Create an Ubuntu 22.04 container named a3m (adjust name as needed)
lxc launch ubuntu:22.04 a3m

# Enter the container
lxc exec a3m -- bash
```

If you already have a container:

```bash
lxc start <container-name>
lxc exec <container-name> -- bash
```

All following steps run **inside** the container unless noted.

---

## Step 2: Update the system and install base tools

```bash
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    apt-transport-https \
    curl \
    git \
    gpg-agent \
    locales \
    locales-all \
    software-properties-common
```

---

## Step 3: Set locale

```bash
sudo locale-gen en_US.UTF-8
export LANG=en_US.UTF-8
export LANGUAGE=en_US:en
export LC_ALL=en_US.UTF-8
# Make persistent for your user (add to ~/.bashrc or /etc/environment if needed)
```

---

## Step 4: Add Archivematica and MediaArea repositories and install system dependencies

These are the same packages the Dockerfile installs (ffmpeg, ImageMagick, Java, etc.):

```bash
# Archivematica GPG and repo
curl -s https://packages.archivematica.org/GPG-KEY-archivematica | sudo apt-key add -
sudo add-apt-repository --no-update --yes "deb [arch=amd64] http://packages.archivematica.org/1.15.x/ubuntu-externals jammy main"

# Ubuntu multiverse/universe/security
sudo add-apt-repository --no-update --yes "deb http://archive.ubuntu.com/ubuntu/ jammy multiverse"
sudo add-apt-repository --no-update --yes "deb http://archive.ubuntu.com/ubuntu/ jammy-security universe"
sudo add-apt-repository --no-update --yes "deb http://archive.ubuntu.com/ubuntu/ jammy-updates multiverse"

# MediaArea repo (for mediaconch, mediainfo)
curl -so /tmp/repo-mediaarea_1.0-25_all.deb -L https://mediaarea.net/repo/deb/repo-mediaarea_1.0-25_all.deb
sudo dpkg -i /tmp/repo-mediaarea_1.0-25_all.deb

# Install all runtime dependencies
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
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
```

---

## Step 5: Install Python 3.12

Ubuntu 22.04 ships with Python 3.10; a3m requires Python ≥3.12. Use the deadsnakes PPA:

```bash
sudo add-apt-repository --yes ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
```

---

## Step 6: Install uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Then either log out and back in, or run:
export PATH="$HOME/.local/bin:$PATH"
```

Verify:

```bash
uv --version
```

---

## Step 7: Get the a3m source code

Either clone the repo or copy your project into the container.

**Option A – Clone from Git:**

```bash
cd /opt   # or use $HOME, e.g. /home/ubuntu
sudo mkdir -p /opt/a3m
sudo chown "$USER:$USER" /opt/a3m
git clone https://github.com/artefactual-labs/a3m.git /opt/a3m
cd /opt/a3m
```

**Option B – Copy from host into container:**

On the host:

```bash
# Copy project into the container (replace 'a3m' with your container name)
lxc file push -r /home/ermadan/Downloads/a3m a3m/opt/a3m
```

Inside the container:

```bash
cd /opt/a3m
```

---

## Step 8: Create virtual environment and install a3m with uv

```bash
cd /opt/a3m   # or wherever you put the project

# Use Python 3.12 and install dependencies + project (same as Dockerfile)
uv sync --frozen --no-dev --python 3.12
```

This creates `.venv` and installs the project. The `a3md` and `a3m` executables will be in `.venv/bin/`.

---

## Step 9: Run the a3m server (a3md)

**One-off run (foreground):**

```bash
cd /opt/a3m
. .venv/bin/activate
a3md
```

Or without activating the venv:

```bash
/opt/a3m/.venv/bin/a3md
```

**Optional – run as a dedicated user (like the Dockerfile):**

```bash
sudo groupadd --system a3m
sudo useradd --system --gid a3m --home-dir /home/a3m a3m
sudo mkdir -p /home/a3m/.local/share/a3m/share
sudo chown -R a3m:a3m /home/a3m
# Run as a3m (ensure a3m user can read /opt/a3m or copy app to /home/a3m)
sudo -u a3m /opt/a3m/.venv/bin/a3md
```

---

## Step 10: Use the client (a3m)

From another terminal (or same container, different shell), talk to the server:

```bash
cd /opt/a3m
. .venv/bin/activate
# If a3md is on the same machine (e.g. localhost:7000):
a3m --address=127.0.0.1:7000 /path/to/transfer/directory
```

---

## Optional: Run a3md as a systemd service (inside the container)

Create a user or system service so a3md starts on boot and restarts on failure.

Example system unit:

```bash
sudo tee /etc/systemd/system/a3md.service << 'EOF'
[Unit]
Description=a3m server (a3md)
After=network.target

[Service]
Type=simple
User=a3m
Group=a3m
WorkingDirectory=/opt/a3m
ExecStart=/opt/a3m/.venv/bin/a3md
Restart=on-failure
Environment="PATH=/opt/a3m/.venv/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable a3md
sudo systemctl start a3md
sudo systemctl status a3md
```

Adjust `User`/`Group` and paths if you run as your own user.

---

## Transfer input formats (what you can pass to a3m)

a3m accepts a **URI** as the transfer source. Supported schemes and types:

| Input type | Scheme | Example |
|------------|--------|--------|
| **Local directory** | `file://` | `file:///home/user/Downloads/transfers/mptest_01` |
| **Local file** (single file) | `file://` | `file:///home/user/transfers/document.pdf` |
| **Local archive** (ZIP, 7z, etc.) | `file://` | `file:///home/user/Downloads/transfers/mptest_01.zip` — will be extracted automatically |
| **Remote URL** | `http://` or `https://` | `https://example.com/transfer.zip` — downloaded then processed (single file) |

- For **local paths you must use the `file://` scheme** and an absolute path (e.g. `file:///home/ermadan/Downloads/transfers/mptest_01`). A bare path like `~/Downloads/transfers/mptest_01` is not supported.
- **Directories**: any folder with files and subfolders (e.g. `mptest_01` containing `JPG/Grants_025_....jpg`) is valid; the whole tree is copied.
- **Archives**: ZIP and other supported formats are detected and extracted; the resulting contents are then processed.
- **Symlinks** in the source are not supported.

Example with your layout:

```bash
# Directory (e.g. mptest_01 with JPG/ and a .jpg inside)
a3m --name="MyTransfer" file:///home/ermadan/Downloads/transfers/mptest_01

# ZIP file (will be extracted)
a3m --name="MyTransfer" file:///home/ermadan/Downloads/transfers/mptest_01.zip
```

---

## Summary checklist

| Step | Action |
|------|--------|
| 1 | Create/start LXC Ubuntu 22.04 container and shell into it |
| 2 | `apt-get update` and install base packages (curl, git, etc.) |
| 3 | Set locale to `en_US.UTF-8` |
| 4 | Add Archivematica/MediaArea repos and install all system deps (ffmpeg, ImageMagick, Java, etc.) |
| 5 | Install Python 3.12 (deadsnakes PPA) |
| 6 | Install uv and add it to `PATH` |
| 7 | Clone or copy a3m source to `/opt/a3m` (or chosen path) |
| 8 | Run `uv sync --frozen --no-dev --python 3.12` in the project directory |
| 9 | Run `a3md` (directly or via systemd) |
| 10 | Use `a3m --address=127.0.0.1:7000 <path>` to submit transfers |

After this, the application runs inside the LXC Ubuntu 22.04 container without Docker, with the same dependencies and behavior as in the Dockerfile.
