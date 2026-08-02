#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: setup-sandbox.sh [--help]

Baut das llmflask-sandbox:1 Docker-Image fuer die Workbench-Pool-Funktion.
Das Image ist Voraussetzung fuer llmflask --usepool und :pool in der TUI.

Idempotent: Baut bei jedem Lauf mit Docker-Cache und aktualisiert das Basis-Image.

Umgebung:
  FORCE=1              Kompatibilitaetsoption; Builds laufen inzwischen immer
  SANDBOX_IMAGE=...    Image-Name (default: llmflask-sandbox:1)

Beispiele:
  ./components/llmflask/setup-sandbox.sh
  FORCE=1 ./components/llmflask/setup-sandbox.sh
  make install-sandbox
EOF
  exit 0
}

for arg in "$@"; do
  case "$arg" in
    --help|-h) show_help ;;
    *) echo "setup-sandbox.sh: unbekannte Option '$arg'. Nutze --help." >&2; exit 1 ;;
  esac
done

IMAGE="${SANDBOX_IMAGE:-llmflask-sandbox:1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTAINERFILE="$REPO_ROOT/sandbox/Containerfile"
BUILD_CONTEXT="$REPO_ROOT/sandbox"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is not installed." >&2
  echo "Install Docker Engine (https://docs.docker.com/engine/install/) and try again." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker daemon is not running or permission denied." >&2
  echo "Start Docker service or add your user to the docker group." >&2
  exit 1
fi

if [[ ! -f "$CONTAINERFILE" ]]; then
  echo "Error: Containerfile not found: $CONTAINERFILE" >&2
  exit 1
fi

echo "[llmflask] Building sandbox image $IMAGE ..."
docker build --pull -t "$IMAGE" -f "$CONTAINERFILE" "$BUILD_CONTEXT"
echo "[llmflask] Sandbox image $IMAGE built successfully."
