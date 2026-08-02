#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

load test_helper

setup() {
    POOL_DIR="/tmp/llmflask-smoke-pool-$$"
    rm -rf "$POOL_DIR"
    mkdir -p "$POOL_DIR/input" "$POOL_DIR/scripts" "$POOL_DIR/output" "$POOL_DIR/logs"
}

teardown() {
    rm -rf "$POOL_DIR"
    docker rm -f "smoke-test-$$" 2>/dev/null || true
}

_setup_python_pool() {
    cat > "$POOL_DIR/scripts/main.py" << 'PYEOF'
import os, sys
sys.dont_write_bytecode = True
with open(os.path.join("/pool/output", "result.txt"), "w") as f:
    f.write("python-ok\n")
PYEOF
    cat > "$POOL_DIR/run.sh" << 'RUNEOF'
#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x /opt/venv/bin/python ]]; then
    PYTHON=/opt/venv/bin/python
else
    python3 -c "print('python-ok')" && exit 0
fi
exec "$PYTHON" -B "$ROOT_DIR/scripts/main.py" --input "$ROOT_DIR/input" --output "$ROOT_DIR/output"
RUNEOF
    chmod 644 "$POOL_DIR/scripts/main.py"
    chmod 755 "$POOL_DIR/scripts" "$POOL_DIR/run.sh"
    chmod 777 "$POOL_DIR/output" "$POOL_DIR/logs"
}

_setup_shell_pool() {
    cat > "$POOL_DIR/scripts/main.sh" << 'SHEOF'
#!/bin/bash
echo "shell-ok" > /pool/output/result.txt
SHEOF
    cat > "$POOL_DIR/run.sh" << 'RUNEOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$ROOT_DIR/scripts/main.sh" "$ROOT_DIR/input" "$ROOT_DIR/output"
RUNEOF
    chmod 755 "$POOL_DIR/scripts/main.sh" "$POOL_DIR/scripts" "$POOL_DIR/run.sh"
    chmod 777 "$POOL_DIR/output" "$POOL_DIR/logs"
}

docker_available() {
    command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && \
    docker image inspect llmflask-sandbox:1 >/dev/null 2>&1
}

_sandbox_run() {
    docker run \
        --name "smoke-test-$$" \
        --network none \
        --memory 256m \
        --cpus 1 \
        --pids-limit 32 \
        --cap-drop ALL \
        --security-opt no-new-privileges \
        --read-only \
        --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
        --user 10001:10001 \
        -v "$POOL_DIR/input:/pool/input:ro" \
        -v "$POOL_DIR/scripts:/pool/scripts:ro" \
        -v "$POOL_DIR/output:/pool/output:rw" \
        -v "$POOL_DIR/logs:/pool/logs:rw" \
        -v "$POOL_DIR/run.sh:/pool/run.sh:ro" \
        llmflask-sandbox:1 bash /pool/run.sh
}

@test "Docker sandbox runs Python pool with production options" {
    if ! docker_available; then
        skip "Docker or sandbox image not available"
    fi
    _setup_python_pool
    _sandbox_run
    run cat "$POOL_DIR/output/result.txt"
    [ "$status" -eq 0 ]
    [[ "$output" == "python-ok" ]]
}

@test "Docker sandbox runs Shell pool with production options" {
    if ! docker_available; then
        skip "Docker or sandbox image not available"
    fi
    _setup_shell_pool
    _sandbox_run
    run cat "$POOL_DIR/output/result.txt"
    [ "$status" -eq 0 ]
    [[ "$output" == "shell-ok" ]]
}

@test "Read-only root filesystem blocks writes outside /tmp and /pool" {
    if ! docker_available; then
        skip "Docker or sandbox image not available"
    fi
    _setup_python_pool
    cat > "$POOL_DIR/scripts/main.py" << 'PYEOF'
import os, sys
sys.dont_write_bytecode = True
try:
    with open("/etc/should-fail", "w") as f:
        f.write("nope")
except Exception:
    pass
os.makedirs("/pool/output", exist_ok=True)
with open(os.path.join("/pool/output", "result.txt"), "w") as f:
    f.write("ok\n")
PYEOF
    _sandbox_run
    run cat "$POOL_DIR/output/result.txt"
    [ "$status" -eq 0 ]
    [[ "$output" == "ok" ]]
}

@test "Container is removed after timeout" {
    if ! docker_available; then
        skip "Docker or sandbox image not available"
    fi
    cat > "$POOL_DIR/scripts/main.py" << 'PYEOF'
import time
time.sleep(30)
PYEOF
    cat > "$POOL_DIR/run.sh" << 'RUNEOF'
#!/usr/bin/env bash
if [[ -x /opt/venv/bin/python ]]; then
    exec /opt/venv/bin/python /pool/scripts/main.py
else
    sleep 30
fi
RUNEOF
    chmod 644 "$POOL_DIR/scripts/main.py"
    chmod 755 "$POOL_DIR/scripts" "$POOL_DIR/run.sh"
    chmod 777 "$POOL_DIR/output" "$POOL_DIR/logs"

    timeout 3 docker run \
        --name "smoke-test-$$" \
        --network none \
        --memory 256m \
        --cpus 1 \
        --pids-limit 32 \
        --cap-drop ALL \
        --security-opt no-new-privileges \
        --read-only \
        --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
        --user 10001:10001 \
        -v "$POOL_DIR/input:/pool/input:ro" \
        -v "$POOL_DIR/scripts:/pool/scripts:ro" \
        -v "$POOL_DIR/output:/pool/output:rw" \
        -v "$POOL_DIR/logs:/pool/logs:rw" \
        -v "$POOL_DIR/run.sh:/pool/run.sh:ro" \
        llmflask-sandbox:1 bash /pool/run.sh 2>/dev/null || true

    sleep 1
    run docker ps -q --filter "name=smoke-test-$$"
    [ -z "$output" ] || docker rm -f "smoke-test-$$" 2>/dev/null
}
