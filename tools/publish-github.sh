#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

export LC_ALL=C.UTF-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DRY_RUN=0
AUTH_HELP=0
SSH_PUBLIC_KEY=""

show_help() {
    cat <<'EOF'
Usage: tools/publish-github.sh [--dry-run] [--auth-help] [--ssh-public-key PATH]

Beginner-safe GitHub publisher. It tests the project, audits the committed
public snapshot, verifies GitHub SSH authentication, and delegates the push to
tools/github-push.sh. Private master and its history are never sent to GitHub.
This command publishes committed HEAD only. It never stages files, creates a
private commit, or pushes origin/master; those remain manual maintainer steps.

Options:
  --dry-run              Run all local tests and audits without network changes
  --auth-help            Show the one-time GitHub SSH setup instructions
  --ssh-public-key PATH  Public .pub key to mention in authentication help
  --help, -h             Show this help

Recommended first use:
  tools/publish-github.sh --auth-help
  tools/publish-github.sh --dry-run
  tools/publish-github.sh

Before publishing an update:
  git status && git diff
  git add -p && git diff --cached
  git commit && git push origin master
EOF
}

fail() {
    echo "Error: $*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 not found"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=1
                ;;
            --auth-help)
                AUTH_HELP=1
                ;;
            --ssh-public-key)
                [[ $# -ge 2 ]] || fail "--ssh-public-key requires a path"
                SSH_PUBLIC_KEY="$2"
                shift
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
}

select_public_key() {
    local candidate

    if [[ -n "$SSH_PUBLIC_KEY" ]]; then
        candidate="$SSH_PUBLIC_KEY"
    elif [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
        candidate="$HOME/.ssh/id_ed25519.pub"
    elif [[ -f "$HOME/.ssh/id_rsa.pub" ]]; then
        candidate="$HOME/.ssh/id_rsa.pub"
    else
        return 1
    fi

    [[ "$candidate" == *.pub ]] || fail "SSH public key path must end in .pub"
    [[ -f "$candidate" && ! -L "$candidate" ]] || \
        fail "SSH public key must be a regular, non-symbolic-link .pub file"
    grep -Eq '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp[0-9]+) ' "$candidate" || \
        fail "File does not look like an SSH public key: $candidate"
    SSH_PUBLIC_KEY="$candidate"
}

show_auth_help() {
    local quoted_key

    cat <<'EOF'
GitHub SSH setup (one time)
==========================

Do NOT use ssh-copy-id: GitHub is not a normal interactive SSH server.
Open this page while signed in to the intended GitHub account:

  https://github.com/settings/ssh/new

Choose "Authentication Key". Display and copy only your public key file.
Never display, copy, commit, or upload the matching file without ".pub".
EOF

    if select_public_key; then
        printf -v quoted_key '%q' "$SSH_PUBLIC_KEY"
        printf '\nDetected public key: %s\n' "$SSH_PUBLIC_KEY"
        if command -v ssh-keygen >/dev/null 2>&1; then
            ssh-keygen -lf "$SSH_PUBLIC_KEY"
        fi
        printf '\nSafe command to display it:\n\n  cat %s\n' "$quoted_key"
    else
        cat <<'EOF'

No id_ed25519.pub or id_rsa.pub key was found. Follow GitHub's official key
generation instructions, then rerun this command. Never share the private key.
EOF
    fi

    cat <<'EOF'

After saving the public key on GitHub, test it:

  ssh -T git@github.com

Success contains:

  Hi USERNAME! You've successfully authenticated, but GitHub does not provide shell access.

GitHub intentionally returns status 1 even for that successful test. If you
see "Permission denied (publickey)", confirm the key is added to the correct
account and loaded into ssh-agent. If port 22 is blocked, follow GitHub's
official "SSH over the HTTPS port" instructions.
EOF
}

check_clean_source() {
    [[ -z "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=normal)" ]] || \
        fail "Working tree is not clean. Review git status and git diff, stage only intended files, commit them manually, and push origin/master before publication."
}

verify_github_ssh() {
    local output status

    set +e
    output="$(ssh -o BatchMode=yes -T git@github.com 2>&1)"
    status=$?
    set -e

    if [[ "$output" == *"successfully authenticated"* ]]; then
        echo "$output"
        echo "GitHub SSH authentication verified (GitHub status $status is expected)."
        return 0
    fi

    echo "$output" >&2
    fail "GitHub SSH authentication failed. Run tools/publish-github.sh --auth-help"
}

run_local_preflight() {
    make -C "$REPO_ROOT" test
    "$SCRIPT_DIR/check-publication.sh"
    "$SCRIPT_DIR/github-push.sh" --check
}

main() {
    parse_args "$@"

    if [[ "$AUTH_HELP" -eq 1 ]]; then
        show_auth_help
        return 0
    fi

    require_command git
    require_command make
    check_clean_source
    run_local_preflight

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "GitHub publication dry run passed; no network changes were made."
        return 0
    fi

    require_command ssh
    verify_github_ssh
    "$SCRIPT_DIR/github-push.sh"
}

main "$@"
