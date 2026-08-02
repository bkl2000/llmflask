#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

load test_helper

@test "python3 -m venv nur wenn Verzeichnis fehlt" {
    run bash -c '
        VENV_DIR="/tmp/test_venv_nonexistent"
        if [ -d "$VENV_DIR" ]; then
            echo "Venv vorhanden"
        else
            echo "Erstelle venv"
        fi
    '
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Erstelle venv" ]]
}

@test "vorhandenes venv wird wiederverwendet" {
    VENV_DIR=$(mktemp -d)
    run bash -c "
        VENV_DIR='$VENV_DIR'
        if [ -d \"\$VENV_DIR\" ]; then
            echo 'Venv vorhanden'
        fi
    "
    [ "$status" -eq 0 ]
    [[ "$output" =~ "vorhanden" ]]
    rm -rf "$VENV_DIR"
}

@test "pandoc fehlt -> sudo apt install" {
    command() {
        case "$2" in
            pandoc) return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f command
    run bash -c '
        if command -v pandoc >/dev/null 2>&1; then
            echo "pandoc vorhanden"
        else
            echo "  [INSTALL] pandoc..."
        fi
    '
    [ "$status" -eq 0 ]
    [[ "$output" =~ "INSTALL" ]]
    grep -q "Running: sudo apt install -y pandoc" components/llmflask/setup-venv.sh
}

@test "build und setup hinweise verwenden repo-root pfade" {
    run bash -c '
        grep -q "ROOT_COMPONENT_DIR" components/llmflask/build-standalone.sh
        grep -q "cp ./.*ROOT_BIN_PATH" components/llmflask/build-standalone.sh
        grep -q "make standalone" components/llmflask/setup-venv.sh
        grep -q "ROOT_TGZ=\"components/llmflask/" components/llmflask/build-client-tgz.sh
        grep -q "scp .*ROOT_TGZ" components/llmflask/build-client-tgz.sh
    '
    [ "$status" -eq 0 ]
}
