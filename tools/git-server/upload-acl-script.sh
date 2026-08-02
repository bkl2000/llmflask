#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: upload-acl-script.sh [--help]

Kopiert das Git-Server-ACL-Setup-Script per SSH auf den Server.
Es wird nichts remote ausgefuehrt.

Umgebung:
  GIT_SERVER=git-server.example.com
  GIT_SERVER_PORT=2222
  GIT_SERVER_USER=git
  REMOTE_PATH=/tmp/setup-llmflask-acl-readonly.sh

Beispiel:
  tools/git-server/upload-acl-script.sh
  ssh -p 2222 git@git-server.example.com ls -l /tmp/setup-llmflask-acl-readonly.sh
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  show_help
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_PATH="$SCRIPT_DIR/setup-llmflask-acl-readonly.sh"
GIT_SERVER="${GIT_SERVER:-git-server.example.com}"
GIT_SERVER_PORT="${GIT_SERVER_PORT:-2222}"
GIT_SERVER_USER="${GIT_SERVER_USER:-git}"
REMOTE_PATH="${REMOTE_PATH:-/tmp/setup-llmflask-acl-readonly.sh}"

command -v scp >/dev/null || {
  echo "FEHLER: scp fehlt." >&2
  exit 1
}

if [ ! -f "$SOURCE_PATH" ]; then
  echo "FEHLER: Quelle fehlt: $SOURCE_PATH" >&2
  exit 1
fi

scp -P "$GIT_SERVER_PORT" "$SOURCE_PATH" "${GIT_SERVER_USER}@${GIT_SERVER}:${REMOTE_PATH}"

cat <<EOF
Kopiert nach:
  ${GIT_SERVER_USER}@${GIT_SERVER}:${REMOTE_PATH}

Auf dem Server als root ausfuehren:
  su -
  bash ${REMOTE_PATH}
EOF
