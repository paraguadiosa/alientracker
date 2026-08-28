#!/usr/bin/env bash
#
# provision.sh
#
# Migrates two services from the Win Mini (mini) to the Raspberry Pi 3B+
# (jacinto, LAN 192.168.100.33, tailnet 100.99.112.42, Pi OS Lite trixie arm64):
#   1. Alien Tracker (beaverhabits)  -> systemd USER unit, port 8081
#   2. mermaid-live-editor           -> docker container, port 9000
#
# This script runs ON the mini and reaches the Pi through the ssh alias
# 'jacinto' (key ~/.ssh/mini, passwordless). Passwordless sudo on the Pi is
# required. Services on the mini are never stopped, restarted, or modified;
# the mini only provides data via scp.
#
# Usage: ./provision.sh

set -euo pipefail

# ---------------------------------------------------------------- config

PI_HOST="jacinto"
PI_USER="pi"

MINI_REPO_DIR="/home/eve/repos/alientracker"

# Private repo over SSH: jacinto has its own GitHub key (jacinto-pi),
# and the rule is: clone everything from GitHub over SSH, sync both ways.
REPO_URL="git@github.com:paraguadiosa/alientracker.git"

PI_REPO_DIR="/home/pi/repos/alientracker"
PI_VENV_DIR="$PI_REPO_DIR/.venv"
PI_GUNICORN_BIN="$PI_VENV_DIR/bin/gunicorn"

HABITS_PORT=8081
MERMAID_PORT=9000
MERMAID_IMAGE="ghcr.io/mermaid-js/mermaid-live-editor"

# TASKS_URL is a plain env var (Settings.TASKS_URL in beaverhabits/configs.py).
# Radicale (CalDAV) stays on the mini at 127.0.0.1:5232; from the Pi it is
# reachable through the mini tailnet address below.
TASKS_URL="http://100.95.188.29:5232"
# Mirrors the mini unit override so the migrated account can log in.
TRUSTED_LOCAL_EMAIL="xixiponxi@gmail.com"
TIME_ZONE="America/Asuncion"

# ---------------------------------------------------------------- helpers

pi_ssh() {
    ssh -o BatchMode=yes -o ConnectTimeout=10 "$PI_HOST" "$@"
}

# Run systemctl for the pi user session; linger keeps it alive after logout.
pi_userctl() {
    pi_ssh "XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user $*"
}

# Write stdin to a file on the Pi.
pi_write_file() {
    local remote_path="$1"
    pi_ssh "tee '$remote_path' >/dev/null"
}

wait_for_http() {
    local url="$1"
    local attempts="$2"
    local code=""
    local i
    for ((i = 1; i <= attempts; i++)); do
        code="$(pi_ssh "curl -s -o /dev/null -w '%{http_code}' --max-time 5 '$url'" 2>/dev/null || true)"
        if [ -n "$code" ] && [ "$code" != "000" ]; then
            echo "    $url -> HTTP $code"
            return 0
        fi
        sleep 2
    done
    echo "error: $url did not respond after $((attempts * 2)) seconds" >&2
    return 1
}

# ---------------------------------------------------------------- steps

check_preflight() {
    [ -d "$MINI_REPO_DIR/.git" ] || {
        echo "error: local repo missing at $MINI_REPO_DIR" >&2
        exit 1
    }
    echo "==> checking ssh access to $PI_HOST"
    pi_ssh "true"
    echo "==> checking passwordless sudo on the Pi"
    if ! pi_ssh "sudo -n true"; then
        echo "error: passwordless sudo is required on the Pi" >&2
        exit 1
    fi
}

prepare_pi() {
    echo "==> [1/7] updating the Pi and installing base packages"
    pi_ssh "DEBIAN_FRONTEND=noninteractive sudo apt-get update"
    pi_ssh "DEBIAN_FRONTEND=noninteractive sudo apt-get -y upgrade"
    pi_ssh "DEBIAN_FRONTEND=noninteractive sudo apt-get install -y git python3-venv docker.io"
    pi_ssh "sudo systemctl enable --now docker"
    # Let the pi user drive docker without sudo for manual debugging.
    pi_ssh "sudo usermod -aG docker $PI_USER"
    echo "==> enabling linger for $PI_USER (keeps user units running after logout)"
    pi_ssh "sudo loginctl enable-linger $PI_USER"
}

clone_repo() {
    echo "==> [2/7] cloning alientracker (--recursive) on the Pi"
    pi_ssh "mkdir -p /home/pi/repos"
    if pi_ssh "[ -d '$PI_REPO_DIR/.git' ]"; then
        echo "    repo already cloned, pulling instead"
        pi_ssh "git -C '$PI_REPO_DIR' pull --recurse-submodules"
    else
        pi_ssh "git clone --recursive '$REPO_URL' '$PI_REPO_DIR'"
    fi
}

setup_venv() {
    echo "==> [3/7] creating venv and installing dependencies on the Pi"
    pi_ssh "python3 -m venv '$PI_VENV_DIR'"
    pi_ssh "'$PI_VENV_DIR/bin/pip' install --upgrade pip"
    if pi_ssh "[ -f '$PI_REPO_DIR/requirements.txt' ]"; then
        pi_ssh "'$PI_VENV_DIR/bin/pip' install -r '$PI_REPO_DIR/requirements.txt'"
    else
        # This fork has no requirements.txt. pyproject requires-python is
        # >=3.12,<4.0 and every dependency ships cp313 arm64 wheels
        # (asyncpg, uvloop, psutil), so no pin needs adjusting for the
        # trixie Python 3.13.
        pi_ssh "'$PI_VENV_DIR/bin/pip' install -e '$PI_REPO_DIR'"
    fi
}

copy_user_data() {
    echo "==> [4/7] copying .user/ (habits.db + .nicegui) from the mini"
    # The mini is the source of truth: drop any stale copy, then re-copy.
    pi_ssh "rm -rf '$PI_REPO_DIR/.user'"
    scp -o BatchMode=yes -p -r "$MINI_REPO_DIR/.user" "$PI_HOST:$PI_REPO_DIR/"
    if ! pi_ssh "[ -f '$PI_REPO_DIR/.user/habits.db' ]"; then
        echo "error: habits.db missing after copy" >&2
        exit 1
    fi
}

install_units() {
    echo "==> [5/7] installing systemd units on the Pi"

    pi_ssh "mkdir -p /home/pi/.config/systemd/user"
    pi_write_file "/home/pi/.config/systemd/user/beaverhabits.service" <<UNIT
[Unit]
Description=Alien Tracker (beaverhabits) - port $HABITS_PORT
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PI_REPO_DIR
Environment=HABITS_STORAGE=DATABASE
Environment=MAX_USER_COUNT=1
Environment=TIME_ZONE=$TIME_ZONE
Environment=NICEGUI_STORAGE_PATH=$PI_REPO_DIR/.user/.nicegui
Environment=TRUSTED_LOCAL_EMAIL=$TRUSTED_LOCAL_EMAIL
Environment=TASKS_URL=$TASKS_URL
ExecStart=$PI_GUNICORN_BIN beaverhabits.main:app --bind 0.0.0.0:$HABITS_PORT -w 1 -k uvicorn_worker.UvicornWorker --max-requests 10000 --log-level info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT

    pi_ssh "sudo tee /etc/systemd/system/mermaid-live-editor.service >/dev/null" <<UNIT
[Unit]
Description=Mermaid Live Editor (docker container, port $MERMAID_PORT)
After=docker.service
Requires=docker.service

[Service]
Restart=always
RestartSec=5
ExecStartPre=-/usr/bin/docker rm -f mermaid-live-editor
ExecStart=/usr/bin/docker run --name mermaid-live-editor --rm -p 0.0.0.0:$MERMAID_PORT:8080 $MERMAID_IMAGE
ExecStop=/usr/bin/docker stop -t 10 mermaid-live-editor

[Install]
WantedBy=multi-user.target
UNIT
}

start_services() {
    echo "==> [6/7] starting services on the Pi"
    # Pull first so the unit does not restart in a loop while pulling.
    pi_ssh "sudo docker pull '$MERMAID_IMAGE'"
    pi_userctl "daemon-reload"
    pi_userctl "enable --now beaverhabits.service"
    pi_ssh "sudo systemctl daemon-reload"
    pi_ssh "sudo systemctl enable --now mermaid-live-editor.service"
}

verify() {
    echo "==> [7/7] verifying services with curl on the Pi"
    wait_for_http "http://localhost:8081" 30
    wait_for_http "http://localhost:9000" 30
    pi_userctl "is-active beaverhabits.service"
    pi_ssh "systemctl is-active mermaid-live-editor.service"
}

print_summary() {
    echo
    echo "Provisioning finished. Mini services were not touched."
    echo "  Alien Tracker: http://192.168.100.33:$HABITS_PORT (LAN) / http://100.99.112.42:$HABITS_PORT (tailnet)"
    echo "  Mermaid:       http://192.168.100.33:$MERMAID_PORT (LAN) / http://100.99.112.42:$MERMAID_PORT (tailnet)"
    echo "  TASKS_URL:     $TASKS_URL (Radicale on the mini, unchanged)"
    if pi_ssh "[ -f /var/run/reboot-required ]"; then
        echo "  NOTE: the Pi has pending updates and should be rebooted."
    fi
}

main() {
    check_preflight
    prepare_pi
    clone_repo
    setup_venv
    copy_user_data
    install_units
    start_services
    verify
    print_summary
}

main "$@"
