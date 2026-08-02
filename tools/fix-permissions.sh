#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

show_help() {
    cat <<'EOF'
Usage: fix-permissions.sh [--check] [--help] [DIR]

Restores the executable bit on tracked project tools after a Nextcloud sync
or checkout stripped them. Idempotent and safe to run repeatedly.

The set of executable files is derived generically from the Git index
(all files tracked as mode 100755), so new tools are covered automatically
without editing this script. Without a Git repository it falls back to
shebang-based and shell-script detection.

Options:
  --check   Only report files that should be executable but are not;
            exit non-zero if any are missing.
  --help    Show this help and exit.
  DIR       Project directory to fix (default: this repository root).

Examples:
  tools/fix-permissions.sh
  tools/fix-permissions.sh --check
  make fix-permissions
EOF
}

check_only=0
target_dir=""
for arg in "$@"; do
    case "$arg" in
        --check) check_only=1 ;;
        --help | -h) show_help && exit 0 ;;
        -*) echo "llmflask: error: unknown option: $arg" >&2 && exit 2 ;;
        *) target_dir="$arg" ;;
    esac
done

if [ -z "$target_dir" ]; then
    target_dir="$(cd "$(dirname "$0")/.." && pwd)"
fi
if [ ! -d "$target_dir" ]; then
    echo "llmflask: error: not a directory: $target_dir" >&2
    exit 2
fi

collect_from_git() {
    git -C "$target_dir" ls-files -s 2>/dev/null | awk '$1 == "100755" {print $4}'
}

collect_from_heuristic() {
    find "$target_dir" -type f \( -name '*.sh' -o -name 'llm-*' -o -name 'llmflaskcmd' -o -name 'llm-runresult' \) \
        -not -path '*/.git/*' -not -path '*/build/*' -not -path '*/dist/*' \
        -not -path '*/standalone/*' -not -path '*/__pycache__/*' -printf '%P\n' 2>/dev/null
    find "$target_dir" -type f -name '*.py' -not -path '*/.git/*' \
        -not -path '*/build/*' -not -path '*/dist/*' -not -path '*/standalone/*' \
        -not -path '*/__pycache__/*' -exec sh -c 'head -c 2 "$1" | grep -q "#!"' _ {} \; -printf '%P\n' 2>/dev/null
}

missing=0
changed=0
restore_file() {
    local file="$1"
    if [ -x "$file" ]; then
        return
    fi
    missing=$((missing + 1))
    echo "missing exec bit: $file" >&2
    if [ "$check_only" -eq 1 ]; then
        return
    fi
    if chmod +x "$file"; then
        changed=$((changed + 1))
    fi
}

targets=""
if [ -d "$target_dir/.git" ] || git -C "$target_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    targets="$(collect_from_git)"
fi
if [ -z "$targets" ]; then
    targets="$(collect_from_heuristic)"
fi

while IFS= read -r file; do
    [ -n "$file" ] || continue
    [ -f "$target_dir/$file" ] || continue
    restore_file "$target_dir/$file"
done <<< "$targets"

if [ "$check_only" -eq 1 ]; then
    if [ "$missing" -gt 0 ]; then
        echo "$missing file(s) missing the executable bit." >&2
        exit 1
    fi
    echo "All executable bits are in place."
    exit 0
fi

if [ "$changed" -gt 0 ]; then
    echo "Fixed executable bits on $changed file(s)."
else
    echo "No permissions to fix."
fi
