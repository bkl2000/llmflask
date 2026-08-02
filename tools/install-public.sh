#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

export LC_ALL=C.UTF-8

DEFAULT_REPOSITORY="https://github.com/bkl2000/llmflask.git"
REPOSITORY_URL="$DEFAULT_REPOSITORY"
INSTALL_DIRECTORY="$PWD/llmflask"
FULL_AI=0

show_help() {
    cat <<'EOF'
Usage: tools/install-public.sh [OPTIONS]

Clones or safely updates the public LLMFlask repository and runs the
idempotent installation targets. The default local installation does not need
Docker. Docker Engine and Compose are external prerequisites for --full-ai and
are never installed by this script.

Options:
  --repo URL         Repository URL (default: GitHub bkl2000/llmflask)
  --directory DIR    Clone/install directory (default: ./llmflask)
  --full-ai          Install the complete AI stack instead of the minimal model
  --help, -h         Show this help before dependency checks
EOF
}

fail() {
    echo "Error: $*" >&2
    exit 1
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --repo)
                [[ $# -ge 2 ]] || fail "--repo requires a URL"
                REPOSITORY_URL="$2"
                shift
                ;;
            --directory)
                [[ $# -ge 2 ]] || fail "--directory requires a path"
                INSTALL_DIRECTORY="$2"
                shift
                ;;
            --full-ai)
                FULL_AI=1
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

    [[ -n "$REPOSITORY_URL" ]] || fail "Repository URL must not be empty"
    [[ -n "$INSTALL_DIRECTORY" ]] || fail "Install directory must not be empty"
}

check_prerequisites() {
    local command_name
    local missing_commands=()

    for command_name in git curl python3 make tar; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            missing_commands+=("$command_name")
        fi
    done
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        echo "Error: missing required commands: ${missing_commands[*]}" >&2
        echo "Run:" >&2
        echo "  sudo apt update" >&2
        echo "  sudo apt install -y ca-certificates git curl make tar python3 python3-venv python3-pip" >&2
        exit 1
    fi
    python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' || \
        fail "Python 3.12 or newer is required"
}

prepare_checkout() {
    local configured_origin

    if [[ ! -e "$INSTALL_DIRECTORY" ]]; then
        git clone -- "$REPOSITORY_URL" "$INSTALL_DIRECTORY"
        return 0
    fi

    [[ -d "$INSTALL_DIRECTORY/.git" ]] || \
        fail "Existing target is not a Git checkout: $INSTALL_DIRECTORY"
    [[ -z "$(git -C "$INSTALL_DIRECTORY" status --porcelain --untracked-files=normal)" ]] || \
        fail "Existing checkout has local changes: $INSTALL_DIRECTORY"

    configured_origin="$(git -C "$INSTALL_DIRECTORY" remote get-url origin 2>/dev/null || true)"
    [[ "$configured_origin" == "$REPOSITORY_URL" ]] || \
        fail "Existing checkout origin does not match $REPOSITORY_URL"
    git -C "$INSTALL_DIRECTORY" pull --ff-only origin main
}

install_project() {
    if [[ "$FULL_AI" -eq 1 ]]; then
        make -C "$INSTALL_DIRECTORY" install-server
        make -C "$INSTALL_DIRECTORY" install-standalone
        make -C "$INSTALL_DIRECTORY" install-tools
    else
        make -C "$INSTALL_DIRECTORY" all
    fi
}

main() {
    parse_args "$@"
    check_prerequisites
    prepare_checkout
    install_project
    echo "LLMFlask installation complete: $INSTALL_DIRECTORY"
}

main "$@"
