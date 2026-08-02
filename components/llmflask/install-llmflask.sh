#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

# install-llmflask.sh
#
# Installiert llmflask CLI auf beliebigem Rechner (Client oder Server).
# Idempotent — mehrfach ausfuehrbar.

show_help() {
    cat <<'EOF'
Usage: install-llmflask.sh [--help]

Installiert LLMFlask aus dem lokalen Quellbaum in eine venv.

Umgebung:
  VENV_DIR=~/.venvs/llmflask  Ziel-venv

Beispiele:
  ./components/llmflask/install-llmflask.sh
  VENV_DIR=~/.venvs/llmflask-test ./components/llmflask/install-llmflask.sh
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="${VENV_DIR:-$HOME/.venvs/llmflask}"

echo "== llmflask Install =="
echo "Venv: $VENV_DIR"

command -v python3 >/dev/null || { echo "FEHLER: python3 fehlt"; exit 1; }

if [ ! -d "$VENV_DIR" ]; then
    echo "Erstelle venv..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installiere llmflask..."
"$VENV_DIR/bin/pip" install -q -e .

echo
echo "=== Fertig ==="
echo "Server:      $VENV_DIR/bin/llmflask"
echo "Client TUI:  $VENV_DIR/bin/llmflask --tui --host SERVER_IP"
echo "Aktivieren:  source $VENV_DIR/bin/activate"
