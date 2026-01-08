#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="prolific-agent"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

systemctl --user disable --now "${UNIT_NAME}.timer" || true
rm -f "$SYSTEMD_USER_DIR/${UNIT_NAME}.timer" "$SYSTEMD_USER_DIR/${UNIT_NAME}.service"
systemctl --user daemon-reload

echo "Uninstalled ${UNIT_NAME} user units."


