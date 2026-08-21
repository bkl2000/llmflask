#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

@test "build check prints apt command for missing core tool" {
    command() {
        if [ "${1:-}" = "-v" ] && [ "${2:-}" = "curl" ]; then
            return 1
        fi
        builtin command "$@"
    }
    export -f command

    run ./tools/check-install-prerequisites.sh --build

    [ "$status" -ne 0 ]
    [[ "$output" == *"missing required commands: curl"* ]]
    [[ "$output" == *"sudo apt install -y ca-certificates git curl make tar python3 python3-venv python3-pip"* ]]
}

@test "old Python reports the required version without changing it" {
    python3() {
        echo "3 11"
    }
    export -f python3

    run ./tools/check-install-prerequisites.sh --build

    [ "$status" -ne 0 ]
    [[ "$output" == *"Python 3.12 or newer is required; found 3.11"* ]]
    [[ "$output" == *"Install a supported system Python"* ]]
}

@test "Debian 12 Python 3.11 explains the clone-and-build boundary" {
    local os_release="$BATS_TEST_TMPDIR/os-release"
    cat > "$os_release" <<'EOF'
ID=debian
VERSION_ID="12"
EOF
    python3() {
        echo "3 11"
    }
    export -f python3

    run env LLMFLASK_OS_RELEASE_FILE="$os_release" \
        ./tools/check-install-prerequisites.sh --build

    [ "$status" -ne 0 ]
    [[ "$output" == *"Debian 12 provides Python 3.11"* ]]
    [[ "$output" == *"path is not supported or tested out of the box"* ]]
}

@test "future apt-family releases pass based on capabilities, not version lists" {
    local os_release
    local distro

    python3() {
        case "$*" in
            *sys.version_info*) echo "3 14" ;;
            *ensurepip*) return 0 ;;
            *) return 0 ;;
        esac
    }
    export -f python3

    for distro in "debian:14:debian" "ubuntu:26.04:debian" "linuxmint:23:ubuntu debian"; do
        IFS=: read -r distro_id distro_version distro_like <<< "$distro"
        os_release="$BATS_TEST_TMPDIR/os-release-$distro_id"
        {
            printf 'ID=%s\n' "$distro_id"
            printf 'VERSION_ID="%s"\n' "$distro_version"
            printf 'ID_LIKE="%s"\n' "$distro_like"
        } > "$os_release"

        run env LLMFLASK_OS_RELEASE_FILE="$os_release" \
            ./tools/check-install-prerequisites.sh --build

        [ "$status" -eq 0 ]
        [[ "$output" == *"OS=${distro_id} ${distro_version}, Python=3.14"* ]]
    done
}

@test "missing venv support prints the exact apt repair command" {
    python3() {
        case "$*" in
            *sys.version_info*) echo "3 12" ;;
            *ensurepip*) return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f python3

    run ./tools/check-install-prerequisites.sh --build

    [ "$status" -ne 0 ]
    [[ "$output" == *"Python venv/ensurepip support is missing"* ]]
    [[ "$output" == *"sudo apt install -y python3-venv python3-pip"* ]]
}

@test "inactive systemd explains local build alternative" {
    systemctl() {
        echo "offline"
        return 1
    }
    export -f systemctl

    run ./tools/check-install-prerequisites.sh --local

    [ "$status" -ne 0 ]
    [[ "$output" == *"systemd is not active"* ]]
    [[ "$output" == *"make standalone"* ]]
    [[ "$output" == *"OLLAMA_URL"* ]]
}

@test "full check keeps Docker external and prints recovery commands" {
    command() {
        if [ "${1:-}" = "-v" ] && [ "${2:-}" = "docker" ]; then
            return 1
        fi
        builtin command "$@"
    }
    systemctl() {
        echo "running"
    }
    export -f command systemctl

    run ./tools/check-install-prerequisites.sh --full

    [ "$status" -ne 0 ]
    [[ "$output" == *"Docker Engine is not installed"* ]]
    [[ "$output" == *"https://docs.docker.com/engine/install/"* ]]
    [[ "$output" == *"sudo systemctl enable --now docker"* ]]
    [[ "$output" == *"sudo usermod -aG docker"* ]]
}

@test "full check explains that legacy Compose v1 is insufficient" {
    docker() {
        if [ "${1:-}" = "compose" ]; then
            return 1
        fi
        return 0
    }
    systemctl() {
        echo "running"
    }
    export -f docker systemctl

    run ./tools/check-install-prerequisites.sh --full

    [ "$status" -ne 0 ]
    [[ "$output" == *'Error: Docker Compose v2 is required (`docker compose`).'* ]]
    [[ "$output" == *"sudo apt install docker-compose-v2"* ]]
    [[ "$output" == *'the package `docker-compose` installs legacy Compose v1'* ]]
    [[ "$output" == *"docker compose version"* ]]
    [[ "$output" == *"For Ollama and local models only, Docker is not required"* ]]
    [[ "$output" == *"./components/local-ai/setup-local-ai.sh"* ]]
}
