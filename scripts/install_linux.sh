#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${1:-$HOME/.prolific/config.toml}"
INTERVAL_HOURS="${2:-2}"
APP_ROOT="${3:-$(cd "$(dirname "$0")/.." && pwd)}"
UNIT_NAME="prolific-agent"

if [[ "$INTERVAL_HOURS" -lt 1 || "$INTERVAL_HOURS" -gt 4 ]]; then
  echo "INTERVAL_HOURS must be 1-4" >&2
  exit 2
fi

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

SERVICE_PATH="$SYSTEMD_USER_DIR/${UNIT_NAME}.service"
TIMER_PATH="$SYSTEMD_USER_DIR/${UNIT_NAME}.timer"

VENV_PY="$APP_ROOT/.venv/bin/python"
if [[ -x "$VENV_PY" ]]; then
  EXEC_START="$VENV_PY -m prolific_agent.cli run --config ${CONFIG_PATH}"
else
  EXEC_START="prolific-agent run --config ${CONFIG_PATH}"
fi

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=Prolific: Git Active (metadata-only)

[Service]
Type=oneshot
WorkingDirectory=${APP_ROOT}
ExecStart=${EXEC_START}
EOF

cat > "$TIMER_PATH" <<EOF
[Unit]
Description=Run Prolific: Git Active every ${INTERVAL_HOURS} hours

[Timer]
OnBootSec=5m
OnUnitActiveSec=${INTERVAL_HOURS}h
Persistent=true

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "${UNIT_NAME}.timer"

echo "Installed user systemd units:"
echo "  ${SERVICE_PATH}"
echo "  ${TIMER_PATH}"
echo "App root: ${APP_ROOT}"
echo "Check status with:"
echo "  systemctl --user status ${UNIT_NAME}.timer"


