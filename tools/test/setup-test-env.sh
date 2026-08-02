#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

# setup-test-env.sh
#
# Installiert Test-Abhaengigkeiten via apt.
# Idempotent — mehrfach ausfuehrbar.

show_help() {
    cat <<'EOF'
Usage: setup-test-env.sh [--help]

Installiert die Test-Abhaengigkeiten per apt:
  bats, pytest, Flask, httpx, nodejs, git

Beispiele:
  ./tools/test/setup-test-env.sh
  ./scripts/setup-test-env.sh
  make setup-test-env
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

FAILED=0

install_pkg() {
    local pkg="$1"
    local check_cmd="${2:-$pkg}"

    if command -v "$check_cmd" >/dev/null 2>&1; then
        echo "  [OK] $pkg bereits installiert"
        return 0
    fi

    if dpkg -s "$pkg" >/dev/null 2>&1; then
        echo "  [OK] $pkg (dpkg)"
        return 0
    fi

    echo "  [INSTALL] $pkg ..."
    if sudo apt install -y "$pkg" 2>/dev/null; then
        echo "  [OK] $pkg installiert"
    else
        echo "  [FEHLER] sudo apt install -y $pkg fehlgeschlagen"
        echo "  Bitte manuell ausfuehren:"
        echo "    sudo apt install -y $pkg"
        FAILED=1
    fi
}

echo "== Test-Env Setup =="
echo

install_pkg "bats"
install_pkg "python3-pytest" "pytest"
install_pkg "python3-flask"
install_pkg "python3-httpx"
install_pkg "nodejs" "node"
install_pkg "git"

echo
if [ "$FAILED" -eq 0 ]; then
    echo "== Fertig — make test ausfuehrbar =="
else
    echo "== FEHLER — manuelle Installation noetig =="
    exit 1
fi
