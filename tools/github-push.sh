#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

# Publish a clean project snapshot without exposing the private Git history.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/.github-config"
PUBLICATION_CHECKER="$SCRIPT_DIR/check-publication.sh"
PUBLIC_MARKER=".llmflask-public-snapshot"
TEMPORARY_ROOT=""

show_help() {
    cat <<'EOF'
Usage: tools/github-push.sh [--check|--help]

Publishes the committed project state to a separate public GitHub history.
The private branch and its commit metadata are never pushed to GitHub.

Modes:
  --check  Build and audit the public snapshot without network access
  --help   Show this help

First publication:
  1. Create an empty GitHub repository (no README or license).
  2. Configure a GitHub SSH key.
  3. Commit all intended private-repository changes.
  4. Run tools/github-push.sh and enter the GitHub user/repository.

Later publications use the same command. They append a commit to the separate
public history; never run "git push github master:main".

Environment overrides (mainly useful for tests or GitHub Enterprise):
  GITHUB_USER, GITHUB_REPO, GITHUB_REMOTE_URL
EOF
}

fail() {
    echo "Error: $*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$TEMPORARY_ROOT" && -d "$TEMPORARY_ROOT" ]]; then
        rm -rf "$TEMPORARY_ROOT"
    fi
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 not found"
}

check_clean_source() {
    local status
    status="$(git -C "$REPO_ROOT" status --porcelain --untracked-files=normal)"
    [[ -z "$status" ]] || fail "Working tree is not clean. Commit or remove untracked files first."
}

prepare_snapshot() {
    local destination="$1"
    local source_commit="$2"
    mkdir -p "$destination"
    git -C "$REPO_ROOT" archive "$source_commit" | tar -x -C "$destination"
}

run_publication_audit() {
    [[ -x "$PUBLICATION_CHECKER" ]] || \
        fail "Publication checker is missing or not executable: $PUBLICATION_CHECKER"
    "$PUBLICATION_CHECKER"
}

read_config_value() {
    local requested="$1"
    local name value

    [[ -f "$CONFIG_FILE" ]] || return 0
    while IFS='=' read -r name value; do
        case "$name" in
            GITHUB_USER|GITHUB_REPO)
                value="${value%\"}"
                value="${value#\"}"
                if [[ "$name" == "$requested" ]]; then
                    printf '%s' "$value"
                    return 0
                fi
                ;;
        esac
    done < "$CONFIG_FILE"
}

load_public_target() {
    local saved_user saved_repo

    saved_user="$(read_config_value GITHUB_USER)"
    saved_repo="$(read_config_value GITHUB_REPO)"
    GITHUB_USER="${GITHUB_USER:-$saved_user}"
    GITHUB_REPO="${GITHUB_REPO:-$saved_repo}"

    if [[ -z "$GITHUB_USER" ]]; then
        read -r -p "GitHub username: " GITHUB_USER
    fi
    if [[ -z "$GITHUB_REPO" ]]; then
        read -r -p "Repository name [llmflask]: " GITHUB_REPO
        GITHUB_REPO="${GITHUB_REPO:-llmflask}"
    fi

    [[ "$GITHUB_USER" =~ ^[A-Za-z0-9-]+$ ]] || fail "Invalid GitHub username"
    [[ "$GITHUB_REPO" =~ ^[A-Za-z0-9._-]+$ ]] || fail "Invalid GitHub repository name"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        printf 'GITHUB_USER="%s"\nGITHUB_REPO="%s"\n' \
            "$GITHUB_USER" "$GITHUB_REPO" > "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"
        echo "Saved local publication config to .github-config"
    fi

    GITHUB_REMOTE_URL="${GITHUB_REMOTE_URL:-git@github.com:$GITHUB_USER/$GITHUB_REPO.git}"
}

prepare_public_repository() {
    local snapshot="$1"
    local public_repo="$2"
    local refs

    if ! refs="$(git ls-remote "$GITHUB_REMOTE_URL")"; then
        fail "Cannot access $GITHUB_REMOTE_URL"
    fi

    if grep -q $'refs/heads/main$' <<< "$refs"; then
        git clone --quiet --branch main --single-branch "$GITHUB_REMOTE_URL" "$public_repo"
        [[ -f "$public_repo/$PUBLIC_MARKER" ]] || \
            fail "Remote main was not created by this publisher; refusing to overwrite it"
        git -C "$public_repo" rm -r -q --ignore-unmatch .
    elif [[ -n "$refs" ]]; then
        fail "Remote is not empty and has no managed main branch"
    else
        mkdir -p "$public_repo"
        git -C "$public_repo" init -q -b main
    fi

    cp -a "$snapshot/." "$public_repo/"
    printf '%s\n' "Managed by tools/github-push.sh; do not push private branches here." \
        > "$public_repo/$PUBLIC_MARKER"
    git -C "$public_repo" add -A
}

commit_and_push() {
    local public_repo="$1"

    git -C "$public_repo" config user.name "$GITHUB_USER"
    git -C "$public_repo" config user.email "$GITHUB_USER@users.noreply.github.com"

    if git -C "$public_repo" diff --cached --quiet; then
        echo "Public snapshot is already current; nothing to push."
        return 0
    fi

    git -C "$public_repo" -c commit.gpgsign=false commit -q \
        -m "Update public project snapshot"
    git -C "$public_repo" push origin main 2>/dev/null || \
        git -C "$public_repo" push "$GITHUB_REMOTE_URL" main:main
    echo "Published: https://github.com/$GITHUB_USER/$GITHUB_REPO"
}

main() {
    local mode="${1:-publish}"
    local snapshot public_repo source_commit

    case "$mode" in
        --help|-h)
            show_help
            return 0
            ;;
        --check|publish)
            ;;
        *)
            show_help >&2
            return 2
            ;;
    esac

    require_command git
    require_command tar
    check_clean_source
    source_commit="$(git -C "$REPO_ROOT" rev-parse --verify HEAD)"
    run_publication_audit
    [[ "$(git -C "$REPO_ROOT" rev-parse --verify HEAD)" == "$source_commit" ]] || \
        fail "Committed HEAD changed during the publication audit; rerun the command"

    TEMPORARY_ROOT="$(mktemp -d)"
    trap cleanup EXIT
    snapshot="$TEMPORARY_ROOT/snapshot"
    public_repo="$TEMPORARY_ROOT/public"
    prepare_snapshot "$snapshot" "$source_commit"

    if [[ "$mode" == "--check" ]]; then
        echo "Public snapshot check passed."
        return 0
    fi

    load_public_target
    prepare_public_repository "$snapshot" "$public_repo"
    commit_and_push "$public_repo"
}

main "$@"
