#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail
export LC_ALL=C.UTF-8

show_help() {
  cat <<'EOF'
Usage: setup-llmflask-acl-readonly.sh [--help]

Configure ACLs for the llmflask.git bare repository on the Git server:
  - git retains write access
  - team01 through team10 can read and pull
  - team01 through team10 cannot push

Run this script as root on the Git server.

Environment:
  REPO_PATH=/home/git/git/llmflask.git  Bare repository
  READ_GROUP=llmflask-read              Read-only group
  WRITE_USER=git                        Service user with write access
  ADMIN_USER=admin                      Optional administrator with write access

Example without an administrator ACL:
  su -
  bash /tmp/setup-llmflask-acl-readonly.sh

Example with an administrator ACL:
  ADMIN_USER=admin bash /tmp/setup-llmflask-acl-readonly.sh

Note:
  Team users retain a normal login shell for SSH login and port forwarding.
  Git read-only access is enforced exclusively through ACLs.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  show_help
  exit 0
fi

REPO_PATH="${REPO_PATH:-/home/git/git/llmflask.git}"
READ_GROUP="${READ_GROUP:-llmflask-read}"
WRITE_USER="${WRITE_USER:-git}"
ADMIN_USER="${ADMIN_USER:-}"
TEAM_USERS=(
  team01 team02 team03 team04 team05
  team06 team07 team08 team09 team10
)

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must run as root." >&2
    exit 1
  fi
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null || {
    echo "ERROR: Required command is missing: $cmd" >&2
    exit 1
  }
}

ensure_group() {
  local group="$1"
  if getent group "$group" >/dev/null; then
    echo "Group already exists: $group"
  else
    groupadd "$group"
    echo "Group created: $group"
  fi
}

ensure_user() {
  local user="$1"

  if id "$user" >/dev/null 2>&1; then
    echo "User already exists: $user"
  else
    useradd --create-home --shell /bin/bash "$user"
    echo "User created: $user"
  fi

  usermod -aG "$READ_GROUP" "$user"
}

check_repo() {
  if [ ! -d "$REPO_PATH" ]; then
    echo "ERROR: Repository is missing: $REPO_PATH" >&2
    exit 1
  fi

  if ! git --bare --git-dir="$REPO_PATH" rev-parse --is-bare-repository >/dev/null 2>&1; then
    echo "ERROR: Not a bare repository: $REPO_PATH" >&2
    exit 1
  fi
}

ensure_safe_directory() {
  if git config --system --get-all safe.directory 2>/dev/null | grep -Fx "$REPO_PATH" >/dev/null; then
    echo "Git safe.directory already configured: $REPO_PATH"
  else
    git config --system --add safe.directory "$REPO_PATH"
    echo "Git safe.directory configured: $REPO_PATH"
  fi
}

warn_if_team_can_write_via_unix_group() {
  local repo_group
  repo_group="$(stat -c '%G' "$REPO_PATH")"

  for user in "${TEAM_USERS[@]}"; do
    if id -nG "$user" | tr ' ' '\n' | grep -qx "$repo_group"; then
      echo "WARNING: $user is a member of repository group $repo_group."
      echo "         Remove this membership if $repo_group has write access."
    fi
  done
}

backup_acl() {
  local backup="/root/llmflask.git.acl.$(date +%Y%m%d-%H%M%S)"
  getfacl -R "$REPO_PATH" > "$backup"
  echo "ACL backup: $backup"
}

set_parent_acl() {
  local git_home
  local git_root
  git_home="$(dirname "$(dirname "$REPO_PATH")")"
  git_root="$(dirname "$REPO_PATH")"

  setfacl -m "g:${READ_GROUP}:--x" "$git_home"
  setfacl -m "g:${READ_GROUP}:--x" "$git_root"
  echo "Traversal ACL configured: $git_home, $git_root"
}

set_repo_acl() {
  chmod -R o-w "$REPO_PATH"

  setfacl -R -m "u:${WRITE_USER}:rwX" "$REPO_PATH"
  setfacl -R -m "g:${READ_GROUP}:rX" "$REPO_PATH"
  setfacl -R -m "m::rwX" "$REPO_PATH"
  setfacl -R -d -m "u:${WRITE_USER}:rwX" "$REPO_PATH"
  setfacl -R -d -m "g:${READ_GROUP}:rX" "$REPO_PATH"
  setfacl -R -d -m "m::rwX" "$REPO_PATH"

  if [ -z "$ADMIN_USER" ]; then
    echo "Administrator ACL skipped: ADMIN_USER is not set."
  elif id "$ADMIN_USER" >/dev/null 2>&1; then
    setfacl -R -m "u:${ADMIN_USER}:rwX" "$REPO_PATH"
    setfacl -R -d -m "u:${ADMIN_USER}:rwX" "$REPO_PATH"
    echo "Administrator ACL configured: $ADMIN_USER"
  else
    echo "Note: ADMIN_USER does not exist; skipping administrator ACL: $ADMIN_USER"
  fi

  echo "Repository ACL configured: $REPO_PATH"
}

print_summary() {
  cat <<EOF

== Complete ==

Read-only users:
  ${TEAM_USERS[*]}

Team-Test:
  git clone ssh://team01@git-server.example.com:2222${REPO_PATH}
  cd llmflask
  git pull
  git push   # must fail

Write-Test:
  git clone ssh://${WRITE_USER}@git-server.example.com:2222${REPO_PATH}
  git push   # must succeed for ${WRITE_USER}

Inspect ACLs:
  getfacl ${REPO_PATH} | less
EOF
}

require_root
for cmd in git getent getfacl setfacl stat useradd usermod chmod id date; do
  require_command "$cmd"
done
id "$WRITE_USER" >/dev/null 2>&1 || {
  echo "ERROR: WRITE_USER does not exist: $WRITE_USER" >&2
  exit 1
}

check_repo
ensure_safe_directory
ensure_group "$READ_GROUP"
for user in "${TEAM_USERS[@]}"; do
  ensure_user "$user"
done
warn_if_team_can_write_via_unix_group
backup_acl
set_parent_acl
set_repo_acl
print_summary
