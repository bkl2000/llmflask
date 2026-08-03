#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

# setup-venv.sh
#
# Erstellt/aktualisiert die virtuelle Umgebung fuer llmflask.
# Idempotent — mehrfach ausfuehrbar.

show_help() {
    cat <<'EOF'
Usage: setup-venv.sh [--help]

Erstellt/aktualisiert die lokale LLMFlask-Entwicklungsumgebung und baut
anschliessend das Offline-Client-Paket.

Umgebung:
  VENV_DIR=~/.venvs/llmflask  Ziel-venv

Beispiele:
  ./components/llmflask/setup-venv.sh
  VENV_DIR=~/.venvs/llmflask-dev ./components/llmflask/setup-venv.sh
  make llmflask-venv
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="${VENV_DIR:-$HOME/.venvs/llmflask}"

echo "== llmflask Venv Setup =="

command -v python3 >/dev/null || { echo "FEHLER: python3 fehlt"; exit 1; }

if [ -d "$VENV_DIR" ]; then
    echo "Venv vorhanden: $VENV_DIR"
else
    echo "Erstelle venv: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

echo "Checking pandoc..."
if pandoc_version=$(pandoc --version 2>/dev/null | head -1); then
    echo "  pandoc found: $pandoc_version"
else
    echo "  WARNING: pandoc not found (PDF export disabled)"
    echo "           Install with: sudo apt install pandoc"
fi

echo "Installiere Abhaengigkeiten..."
"$VENV_DIR/bin/pip" install -q -e '.[dev]' 2>&1

echo "Baue Wheelhouse + Client-TGZ..."
./build-client-tgz.sh 2>&1

echo
echo "=== Fertig ==="
echo "Start:      $VENV_DIR/bin/llmflask"
echo "TUI:        $VENV_DIR/bin/llmflask --tui --host SERVER_IP --user alice"
echo "Tests:      make test"
echo "Client:     components/llmflask/llmflask-client-*.tgz (siehe oben)"
echo "Standalone: make standalone"
echo "Venv:       source $VENV_DIR/bin/activate"
