#!/usr/bin/env bash
# Installs the dsh-web systemd user unit so the DeepSeek Harness GUI runs as a daemon.
# Run from your terminal (NOT through the agent sandbox):
#   bash deploy/install-dsh-daemon.sh
set -euo pipefail

UNIT_DIR="$HOME/.config/systemd/user"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dsh-web.service"

mkdir -p "$UNIT_DIR"
cp "$SRC" "$UNIT_DIR/dsh-web.service"
systemctl --user daemon-reload

echo "Unit installed at $UNIT_DIR/dsh-web.service"
echo
echo "Next steps:"
echo "  1. Swap to the daemon (kills the old foreground server):"
echo "       kill 101896 101934 101947 2>/dev/null; sleep 3; systemctl --user start dsh-web"
echo "  2. Enable autostart at boot (with Linger already on, survives logout):"
echo "       systemctl --user enable dsh-web"
echo "  3. Check it:"
echo "       systemctl --user status dsh-web"
