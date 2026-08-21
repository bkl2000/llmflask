#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

export LC_ALL=C.UTF-8

CHECK_MODE="build"

show_help() {
    cat <<'EOF'
Usage: tools/check-install-prerequisites.sh [--build|--local|--full] [--help]

Check installation prerequisites without changing the system.

Modes:
  --build  Check requirements for the Python environment and standalone build
  --local  Also require sudo and an active systemd installation for Ollama
  --full   Also require a usable Docker Engine and Docker Compose plugin

On supported apt-based systems, failures include copyable installation or
repair commands. Docker remains an external prerequisite.
EOF
}

fail() {
    echo "Error: $*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build)
            CHECK_MODE="build"
            ;;
        --local)
            CHECK_MODE="local"
            ;;
        --full)
            CHECK_MODE="full"
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            show_help >&2
            fail "Unknown option: $1"
            ;;
    esac
    shift
done

OS_ID="unknown"
OS_VERSION="unknown"
OS_ID_LIKE=""
OS_RELEASE_FILE="${LLMFLASK_OS_RELEASE_FILE:-/etc/os-release}"
if [[ -r "$OS_RELEASE_FILE" ]]; then
    while IFS='=' read -r os_key os_value; do
        os_value="${os_value%\"}"
        os_value="${os_value#\"}"
        os_value="${os_value%\'}"
        os_value="${os_value#\'}"
        case "$os_key" in
            ID) OS_ID="$os_value" ;;
            VERSION_ID) OS_VERSION="$os_value" ;;
            ID_LIKE) OS_ID_LIKE="$os_value" ;;
        esac
    done < "$OS_RELEASE_FILE"
fi

is_apt_based() {
    local family

    command -v apt-get >/dev/null 2>&1 && return 0
    for family in "$OS_ID" $OS_ID_LIKE; do
        case "$family" in
            debian|ubuntu|linuxmint)
                return 0
                ;;
        esac
    done
    return 1
}

print_core_install_command() {
    if is_apt_based; then
        cat >&2 <<'EOF'
Install the required packages, then run the command again:
  sudo apt update
  sudo apt install -y ca-certificates git curl make tar python3 python3-venv python3-pip
EOF
    else
        cat >&2 <<'EOF'
Install ca-certificates, Git, curl, Make, tar, Python 3.12 or newer, and
Python venv/pip support with this system's package manager, then retry.
The documented first-install path targets apt-based distributions.
EOF
    fi
}

missing_commands=()
for command_name in git curl make tar python3; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        missing_commands+=("$command_name")
    fi
done

if [[ ${#missing_commands[@]} -gt 0 ]]; then
    echo "Error: missing required commands: ${missing_commands[*]}" >&2
    print_core_install_command
    exit 1
fi

read -r python_major python_minor < <(
    python3 -c 'import sys; print(sys.version_info.major, sys.version_info.minor)'
)
if (( python_major < 3 || (python_major == 3 && python_minor < 12) )); then
    echo "Error: Python 3.12 or newer is required; found ${python_major}.${python_minor}." >&2
    if [[ "$OS_ID" == "debian" && "$OS_VERSION" == 12* ]]; then
        cat >&2 <<'EOF'
Debian 12 provides Python 3.11 as its default Python, so this clone-and-build
path is not supported or tested out of the box. This does not prove that
LLMFlask cannot run there. Use a supported build computer and copy the
standalone binary built for the same CPU architecture if appropriate.
EOF
    else
        cat >&2 <<'EOF'
Install a supported system Python, then ensure its venv package is installed:
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip
EOF
    fi
    exit 1
fi

if ! python3 -c 'import ensurepip, venv' >/dev/null 2>&1; then
    cat >&2 <<'EOF'
Error: the Python venv/ensurepip support is missing.
Install it, then run the command again:
  sudo apt update
  sudo apt install -y python3-venv python3-pip
EOF
    exit 1
fi

if [[ "$CHECK_MODE" == "local" || "$CHECK_MODE" == "full" ]]; then
    if (( EUID != 0 )) && ! command -v sudo >/dev/null 2>&1; then
        cat >&2 <<'EOF'
Error: sudo is required to install and manage the Ollama system service.
Ask the administrator to install sudo or run the installation as root:
  apt update
  apt install -y sudo
EOF
        exit 1
    fi
    if (( EUID != 0 )) && command -v sudo >/dev/null 2>&1 \
        && ! ((id -nG || true) 2>/dev/null | grep -qE '(^| )(sudo|wheel)( |$)') \
        && ! (sudo -n true 2>/dev/null); then
        cat >&2 <<'EOF'
Warning: sudo is installed but you do not have sudo access.
If the installer asks for a sudo password later, you may need to add
your user to the sudo group as root first, then log out and back in:
  su -c '/usr/sbin/usermod -aG sudo ${USER:-your-user}'
EOF
    fi
    command -v systemctl >/dev/null 2>&1 || fail \
        "systemd is required for the managed Ollama service; systemctl was not found."

    systemd_state="$(systemctl is-system-running 2>/dev/null || true)"
    case "$systemd_state" in
        running|degraded|starting)
            ;;
        *)
            cat >&2 <<'EOF'
Error: systemd is not active. The local installer manages Ollama as a systemd
service. Boot this distribution with systemd enabled, or build only the
standalone with `make standalone` and connect it to an existing Ollama server
through OLLAMA_URL.
EOF
            exit 1
            ;;
    esac
fi

if [[ "$CHECK_MODE" == "full" ]]; then
    if ! command -v docker >/dev/null 2>&1; then
        cat >&2 <<'EOF'
Error: Docker Engine is not installed. It is an external prerequisite for the
full SearXNG/OpenCode/Workbench stack. Follow:
  https://docs.docker.com/engine/install/
After installation, run:
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
Log out and back in before retrying.
EOF
        exit 1
    fi
    if ! docker compose version >/dev/null 2>&1; then
        cat >&2 <<'EOF'
Error: Docker Compose v2 is required (`docker compose`).

Ubuntu 24.04:
    sudo apt install docker-compose-v2

Note: the package `docker-compose` installs legacy Compose v1
and does not satisfy this requirement.

Verify:
    docker compose version

For Ollama and local models only, Docker is not required:
    ./components/local-ai/setup-local-ai.sh
EOF
        exit 1
    fi
    if ! docker info >/dev/null 2>&1; then
        cat >&2 <<'EOF'
Error: Docker is installed but the daemon is stopped or access is denied.
Run:
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
Then log out and back in, and verify `docker info` before retrying.
EOF
        exit 1
    fi
fi

echo "Prerequisites OK: mode=$CHECK_MODE, OS=${OS_ID} ${OS_VERSION}, Python=${python_major}.${python_minor}"
