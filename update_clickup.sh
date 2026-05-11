#!/bin/bash
# Wrapper para ejecutar clickup_tasks.py y freshdesk_tickets.py desde launchd/cron.
# Carga variables desde .env si existe, fija el cwd al directorio del script
# y loguea stdout/stderr en update.log con timestamp.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$SCRIPT_DIR/.env"
    set +a
fi

# launchd no hereda el entorno del shell interactivo, así que rescatamos los
# `export KEY="..."` definidos en ~/.zshrc (CLICKUP_TOKEN, etc).
if [ -z "${CLICKUP_TOKEN:-}" ] && [ -f "$HOME/.zshrc" ]; then
    eval "$(grep -E '^[[:space:]]*export[[:space:]]+[A-Z_][A-Z0-9_]*=' "$HOME/.zshrc" 2>/dev/null || true)"
fi

PYTHON_BIN="${PYTHON_BIN:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}"
LOG_FILE="$SCRIPT_DIR/update.log"

{
    echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') · iniciando actualización ====="

    echo "----- clickup_tasks.py -----"
    "$PYTHON_BIN" "$SCRIPT_DIR/clickup_tasks.py"
    rc_clickup=$?
    echo "----- clickup_tasks.py · rc=$rc_clickup -----"

    echo "----- freshdesk_tickets.py -----"
    "$PYTHON_BIN" "$SCRIPT_DIR/freshdesk_tickets.py"
    rc_freshdesk=$?
    echo "----- freshdesk_tickets.py · rc=$rc_freshdesk -----"

    rc=$(( rc_clickup | rc_freshdesk ))
    echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') · fin (clickup=$rc_clickup, freshdesk=$rc_freshdesk) ====="
    exit $rc
} >> "$LOG_FILE" 2>&1
