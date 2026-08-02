#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: setup-opencode.sh [--help]

Installiert oder aktualisiert OpenCode per offiziellem Installer.

Beispiele:
  ./components/local-ai/setup-opencode.sh
  make install-opencode
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  show_help
  exit 0
fi

curl -fsSL https://opencode.ai/install | bash
