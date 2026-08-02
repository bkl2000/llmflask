#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$SCRIPT_DIR"

show_help() {
    cat <<'EOF'
Usage: run-tests.sh [--help]

Fuehrt die komplette Projekttest-Suite aus:
  - bash -n fuer Shell-Skripte
  - BATS
  - JavaScript Syntax- und Unit-Tests
  - pytest

Beispiele:
  ./tools/test/run-tests.sh
  ./scripts/run_tests.sh
  make test
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

FAILED=0

echo "=== bash -n Syntax-Check ==="
while IFS= read -r script; do
    [ -f "$script" ] || continue
    printf "  %-35s " "$script"
    if bash -n "$script"; then
        echo "OK"
    else
        echo "FEHLER"
        FAILED=1
    fi
done < <(git ls-files "*.sh")

echo
echo "=== BATS Tests ==="
if command -v bats >/dev/null 2>&1; then
    for test_file in tests/test_*.bats; do
        printf "\n  %s\n" "$test_file"
        bats "$test_file" || FAILED=1
    done
else
    echo "FEHLER: bats nicht installiert"
    echo "Bitte: make setup-test-env"
    FAILED=1
fi

echo
echo "=== JavaScript Syntax-Check ==="
if command -v node >/dev/null 2>&1; then
    if node --check components/llmflask/src/llmflask/static/chat_helpers.js &&
        node --check components/llmflask/src/llmflask/static/chat.js; then
        echo "node --check OK"
    else
        echo "node --check FEHLER"
        FAILED=1
    fi

    if node --test tests/llmflask_js/*.test.js; then
        echo "JS Tests OK"
    else
        echo "JS Tests FEHLER"
        FAILED=1
    fi
else
    echo "FEHLER: nodejs nicht installiert"
    echo "Bitte: make setup-test-env"
    FAILED=1
fi

echo
echo "=== pytest ==="
VENV_DIR="${VENV_DIR:-$HOME/.venvs/llmflask}"
PYTEST_CMD=()
if [ -x "$VENV_DIR/bin/python" ]; then
    PYTEST_CMD=("$VENV_DIR/bin/python" -m pytest)
elif command -v pytest >/dev/null 2>&1; then
    PYTEST_CMD=(pytest)
fi

if [ "${#PYTEST_CMD[@]}" -gt 0 ]; then
    if "${PYTEST_CMD[@]}" \
        tests/test_placeholder.py \
        tests/test_help_output.py \
        tests/test_github_publish.py \
        tests/test_publication_tools.py \
        tests/llmflask/ -q 2>&1; then
        echo "pytest OK"
    else
        echo "pytest FEHLER"
        FAILED=1
    fi
else
    echo "FEHLER: pytest nicht installiert"
    echo "Bitte: make setup-test-env"
    FAILED=1
fi

echo
if [ "$FAILED" -eq 0 ]; then
    echo "=== ALLE TESTS OK ==="
else
    echo "=== TESTS MIT FEHLERN ==="
    exit 1
fi
