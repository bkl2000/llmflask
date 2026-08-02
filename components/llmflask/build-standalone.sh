#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

# build-standalone.sh
#
# Baut ein Standalone-Paket fuer die aktuelle Linux-Plattform mit PyInstaller.
# Idempotent — mehrfach ausfuehrbar.

show_help() {
    cat <<'EOF'
Usage: build-standalone.sh [--help]

Baut ein LLMFlask Standalone-Binary fuer die aktuelle Linux-Architektur:
  components/llmflask/standalone/llmflask-linux-$(uname -m)/llmflask

Voraussetzung:
  make llmflask-venv

Beispiele:
  ./components/llmflask/build-standalone.sh
  make standalone
  ./components/llmflask/standalone/llmflask-linux-$(uname -m)/llmflask --server production
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

command -v python3 >/dev/null || { echo "FEHLER: python3 fehlt"; exit 1; }
command -v tar >/dev/null || { echo "FEHLER: tar fehlt"; exit 1; }

readonly VENV_DIR="${VENV_DIR:-$HOME/.venvs/llmflask}"
if [ -x "$VENV_DIR/bin/python" ]; then
    readonly PYTHON_BIN="$VENV_DIR/bin/python"
else
    readonly PYTHON_BIN="python3"
fi

readonly VERSION=$("$PYTHON_BIN" -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
readonly PLATFORM="linux-$(uname -m)"
readonly NAME="llmflask"
readonly BUILD_ROOT="standalone"
readonly DIST_DIR="${BUILD_ROOT}/${NAME}-${PLATFORM}"
readonly BIN_PATH="${DIST_DIR}/${NAME}"
readonly ROOT_COMPONENT_DIR="${SCRIPT_DIR#"$REPO_ROOT"/}"
readonly ROOT_BIN_PATH="${ROOT_COMPONENT_DIR}/${BIN_PATH}"
readonly TGZ="${NAME}-standalone-${PLATFORM}-${VERSION}.tgz"
readonly TEMPLATE_DIR="${SCRIPT_DIR}/src/llmflask/templates"
readonly STATIC_DIR="${SCRIPT_DIR}/src/llmflask/static"
readonly PROVIDERS_JSON="${SCRIPT_DIR}/src/llmflask/services/providers.json"
readonly ENTRYPOINT="${SCRIPT_DIR}/standalone_main.py"

echo "== ${NAME} Standalone Builder =="
echo "Version:  $VERSION"
echo "Platform: $PLATFORM"
echo "Python:   $PYTHON_BIN"

if ! "$PYTHON_BIN" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "FEHLER: PyInstaller fehlt"
    echo "Installieren: make llmflask-venv"
    echo "Direkt:       ./components/llmflask/setup-venv.sh"
    echo "Manuell:      $PYTHON_BIN -m pip install -e '.[dev]'"
    exit 1
fi

rm -rf "$DIST_DIR" build/"${NAME}-standalone"
mkdir -p "$BUILD_ROOT"

"$PYTHON_BIN" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --name "$NAME" \
    --distpath "$DIST_DIR" \
    --specpath "build/${NAME}-standalone" \
    --workpath "build/${NAME}-standalone" \
    --add-data "${TEMPLATE_DIR}:llmflask/templates" \
    --add-data "${STATIC_DIR}:llmflask/static" \
    --add-data "${PROVIDERS_JSON}:llmflask/services" \
    --collect-submodules "gunicorn" \
    --collect-submodules "llmflask" \
    "$ENTRYPOINT"

echo "Packe ${TGZ} ..."
tar czf "$TGZ" -C "$BUILD_ROOT" "${NAME}-${PLATFORM}"

TAR_SIZE=$(du -h "$TGZ" | cut -f1)
echo "  ${TGZ} (${TAR_SIZE})"
echo
echo "Start:"
echo "  ./${ROOT_BIN_PATH}"
echo "  OPENAI_API_KEY=... ./${ROOT_BIN_PATH}"
echo "  DEEPSEEK_API_KEY=... ./${ROOT_BIN_PATH}"
echo "  ./${ROOT_BIN_PATH} --server production"
echo "  (aus components/llmflask: ./${BIN_PATH})"
echo "Installieren:"
echo "  cp ./${ROOT_BIN_PATH} ~/bin/${NAME}"
