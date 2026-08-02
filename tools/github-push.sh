#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

# Publish a clean project snapshot without exposing the private Git history.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/.github-config"
PUBLIC_MARKER=".llmflask-public-snapshot"
TEMPORARY_ROOT=""
PRIVATE_ONLY_PATHS=(
    archive/legacy-docs
    AGENTS.md
    OPENCODE_INSTALLATION_PLAN.md
    OPENCODE_REVIEW_PLAN.md
    PROJECT_TRACE.md
    PYTHON_GROSSREFAKTOR_REVIEW.md
    llmflask_local_ai_workbench_pool_phase1_AI_Draft_Unreviewed_2026-07-12.md
    opencode.json
    prompts/ollama_prompt_pack_pythonic.tar.gz
)

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
    mkdir -p "$destination"
    git -C "$REPO_ROOT" archive HEAD | tar -x -C "$destination"
}

audit_snapshot() {
    local snapshot="$1"
    local forbidden_path
    local forbidden_content
    local personal_home
    local personal_home_file
    local private_only_path

    forbidden_path="$(
        find "$snapshot" \
            \( -name api.txt -o -name .env -o -name '*.db' \
               -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.tgz' \
               -o -name '*.tar.gz' -o -name '*.zip' \
               -o -name '*.pem' -o -name '*.key' -o -name '*.p12' \
               -o -name '*.pfx' -o -name 'id_rsa*' -o -name 'id_ed25519*' \
               -o -name __pycache__ -o -name build -o -name dist \
               -o -name standalone \) -print -quit
    )"
    [[ -z "$forbidden_path" ]] || fail "Forbidden public artifact: ${forbidden_path#"$snapshot"/}"

    for private_only_path in "${PRIVATE_ONLY_PATHS[@]}"; do
        [[ ! -e "$snapshot/$private_only_path" ]] || \
            fail "Private-only path is present in the public snapshot: $private_only_path"
    done

    forbidden_content="$(
        grep -RIlE \
            'homelinux\.com|/home/[[:alnum:]_.-]+/Nextcloud|[[:alnum:]_.+-]+@gmail\.com|(^|[^0-9])10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)|(^|[^0-9])192\.168\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)|(^|[^0-9])172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)' \
            "$snapshot" 2>/dev/null | head -1 || true
    )"
    [[ -z "$forbidden_content" ]] || fail "Private-looking content: ${forbidden_content#"$snapshot"/}"

    personal_home="$(
        grep -RhoE '/home/[[:alnum:]_.-]+' "$snapshot" 2>/dev/null | \
            while IFS= read -r home_path; do
                case "$home_path" in
                    /home/git)
                        ;;
                    *)
                        printf '%s\n' "$home_path"
                        break
                        ;;
                esac
            done || true
    )"
    if [[ -n "$personal_home" ]]; then
        personal_home_file="$(
            grep -RIlF "$personal_home" "$snapshot" 2>/dev/null | head -1 || true
        )"
        fail "Personal home path $personal_home: ${personal_home_file#"$snapshot"/}"
    fi
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
    local snapshot public_repo

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

    TEMPORARY_ROOT="$(mktemp -d)"
    trap cleanup EXIT
    snapshot="$TEMPORARY_ROOT/snapshot"
    public_repo="$TEMPORARY_ROOT/public"
    prepare_snapshot "$snapshot"
    audit_snapshot "$snapshot"

    if [[ "$mode" == "--check" ]]; then
        echo "Public snapshot check passed."
        return 0
    fi

    load_public_target
    prepare_public_repository "$snapshot" "$public_repo"
    commit_and_push "$public_repo"
}

main "$@"
