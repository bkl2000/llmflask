#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

export LC_ALL=C.UTF-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
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
CHECK_STAGED=0
INSTALL_HOOK=0
HOOK_MARKER="# Managed by tools/check-publication.sh"

show_help() {
    cat <<'EOF'
Usage: tools/check-publication.sh [--staged] [--install-hooks] [--help]

Audits the public Git snapshot for licensing, private information, secrets,
and generated artifacts. The default checks committed HEAD; --staged checks
the Git index, as used by the optional pre-commit hook.

Options:
  --staged         Check the staged Git tree instead of committed HEAD
  --install-hooks  Install the managed pre-commit hook, then run the check
  --help, -h       Show this help before performing any checks
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

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --staged)
                CHECK_STAGED=1
                ;;
            --install-hooks)
                INSTALL_HOOK=1
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

install_hook() {
    local git_dir hook_path temporary_hook

    git_dir="$(git -C "$REPO_ROOT" rev-parse --git-dir)"
    if [[ "$git_dir" != /* ]]; then
        git_dir="$REPO_ROOT/$git_dir"
    fi
    hook_path="$git_dir/hooks/pre-commit"

    if [[ -e "$hook_path" ]]; then
        if grep -Fq "$HOOK_MARKER" "$hook_path"; then
            echo "Managed pre-commit hook is already installed."
            return 0
        fi
        fail "Existing pre-commit hook is not managed by this project; refusing to overwrite $hook_path"
    fi

    mkdir -p "$(dirname "$hook_path")"
    temporary_hook="${hook_path}.tmp.$$"
    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' "$HOOK_MARKER"
        printf '%s\n' 'set -euo pipefail'
        printf '%s\n' 'REPO_ROOT="$(git rev-parse --show-toplevel)"'
        printf '%s\n' 'exec "$REPO_ROOT/tools/check-publication.sh" --staged'
    } > "$temporary_hook"
    chmod 0755 "$temporary_hook"
    mv "$temporary_hook" "$hook_path"
    echo "Installed publication pre-commit hook: $hook_path"
}

prepare_snapshot() {
    local destination="$1"
    local treeish="HEAD"

    if [[ "$CHECK_STAGED" -eq 1 ]]; then
        treeish="$(git -C "$REPO_ROOT" write-tree)"
    fi
    mkdir -p "$destination"
    git -C "$REPO_ROOT" archive "$treeish" | tar -x -C "$destination"
}

check_metadata() {
    local snapshot="$1"
    local private_only_path required_ignore

    [[ -f "$snapshot/LICENSE" ]] || fail "LICENSE is missing from the public snapshot"
    grep -Fq 'MIT License' "$snapshot/LICENSE" || fail "LICENSE is not the expected MIT license"
    grep -Fq 'Copyright (c) 2024-2026 LLMFlask contributors' "$snapshot/LICENSE" || \
        fail "LICENSE copyright is inconsistent"
    for private_only_path in "${PRIVATE_ONLY_PATHS[@]}"; do
        grep -Fxq "$private_only_path export-ignore" "$snapshot/.gitattributes" || \
            fail "Private-only path is not export-ignored: $private_only_path"
    done

    for required_ignore in api.txt .github-config '*.db' 'components/llmflask/build/'; do
        grep -Fxq "$required_ignore" "$snapshot/.gitignore" || \
            fail ".gitignore is missing: $required_ignore"
    done
}

check_source_headers() {
    local snapshot="$1"
    local source_file relative_path

    while IFS= read -r -d '' source_file; do
        relative_path="${source_file#"$snapshot"/}"
        head -n 10 "$source_file" | grep -Fq 'SPDX-License-Identifier: MIT' || \
            fail "Missing MIT SPDX header: $relative_path"
        head -n 10 "$source_file" | grep -Fq \
            'Copyright (c) 2024-2026 LLMFlask contributors' || \
            fail "Missing or inconsistent copyright header: $relative_path"
    done < <(
        find "$snapshot" -type f \
            \( -name '*.py' -o -name '*.sh' -o -name '*.bash' -o -name '*.bats' \
               -o -name '*.js' -o -name '*.css' -o -name '*.html' \) \
            -print0
    )
}

check_forbidden_paths() {
    local snapshot="$1"
    local forbidden_path private_only_path

    forbidden_path="$(
        find "$snapshot" \
            \( -name api.txt -o -name .github-config -o -name .env \
               -o -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \
               -o -name '*.tgz' -o -name '*.tar.gz' -o -name '*.zip' \
               -o -name '*.pem' -o -name '*.key' \
               -o -name '*.p12' -o -name '*.pfx' -o -name 'id_rsa*' \
               -o -name 'id_ed25519*' -o -name __pycache__ -o -name .venv \
               -o -name venv -o -name build -o -name dist -o -name standalone \) \
            -print -quit
    )"
    [[ -z "$forbidden_path" ]] || \
        fail "Forbidden public artifact: ${forbidden_path#"$snapshot"/}"

    for private_only_path in "${PRIVATE_ONLY_PATHS[@]}"; do
        [[ ! -e "$snapshot/$private_only_path" ]] || \
            fail "Private-only path is present in the public snapshot: $private_only_path"
    done
}

check_forbidden_content() {
    local snapshot="$1"
    local credential_content personal_home personal_home_file private_content

    private_content="$(
        grep -RIlE \
            'homelinux\.com|/home/[[:alnum:]_.-]+/Nextcloud|[[:alnum:]_.+-]+@gmail\.com|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|(^|[^0-9])10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)|(^|[^0-9])192\.168\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)|(^|[^0-9])172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)' \
            "$snapshot" 2>/dev/null | head -1 || true
    )"
    [[ -z "$private_content" ]] || \
        fail "Private-looking content: ${private_content#"$snapshot"/}"

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

    credential_content="$(
        grep -RIlE \
            'github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|sk-(proj-|svcacct-)[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}' \
            "$snapshot" 2>/dev/null | head -1 || true
    )"
    [[ -z "$credential_content" ]] || \
        fail "Credential-looking content: ${credential_content#"$snapshot"/}"
}

audit_snapshot() {
    local snapshot="$1"

    check_metadata "$snapshot"
    check_source_headers "$snapshot"
    check_forbidden_paths "$snapshot"
    check_forbidden_content "$snapshot"
}

main() {
    local snapshot

    parse_args "$@"
    require_command git
    require_command tar
    require_command find
    require_command grep
    git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || \
        fail "Not inside a Git repository"

    if [[ "$INSTALL_HOOK" -eq 1 ]]; then
        install_hook
    fi

    TEMPORARY_ROOT="$(mktemp -d)"
    trap cleanup EXIT
    snapshot="$TEMPORARY_ROOT/snapshot"
    prepare_snapshot "$snapshot"
    audit_snapshot "$snapshot"

    if [[ "$CHECK_STAGED" -eq 1 ]]; then
        echo "Staged publication check passed."
    else
        echo "Committed publication check passed."
    fi
}

main "$@"
