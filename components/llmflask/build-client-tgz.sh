#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

# build-client-tgz.sh
#
# Baut das Wheelhouse, packt es mit einem selbstinstallierenden
# install-client.sh in ein .tgz zur Verteilung an Client-Rechner.
# Idempotent — mehrfach ausfuehrbar.

show_help() {
    cat <<'EOF'
Usage: build-client-tgz.sh [--help]

Baut das LLMFlask Offline-Client-Paket:
  components/llmflask/llmflask-client-<version>.tgz

Das Paket enthaelt eine Wheelhouse und install-client.sh. Der Zielrechner
braucht Python >= 3.12, aber kein Git, kein SSH und kein Internet.

Beispiele:
  ./components/llmflask/build-client-tgz.sh
  make client-tgz
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

command -v python3 >/dev/null || { echo "FEHLER: python3 fehlt"; exit 1; }
command -v tar >/dev/null || { echo "FEHLER: tar fehlt"; exit 1; }

readonly VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
readonly NAME="llmflask"
readonly TGZ="${NAME}-client-${VERSION}.tgz"
readonly ROOT_TGZ="components/llmflask/${TGZ}"
readonly STAGE="${NAME}-client-${VERSION}"

echo "== ${NAME} Client-TGZ Builder =="
echo "Version: $VERSION"

echo "Baue Wheelhouse..."
python3 -m pip wheel -q -w dist . 2>&1
PROJECT_WHEEL=$(find dist -maxdepth 1 -type f -name "${NAME}-*.whl" | sort | head -1)
if [ -z "$PROJECT_WHEEL" ]; then
    echo "FEHLER: Kein Projekt-Wheel in dist/ gefunden"
    exit 1
fi
WHEEL_COUNT=$(find dist -maxdepth 1 -type f -name "*.whl" | wc -l)
echo "  Wheelhouse:    dist/ (${WHEEL_COUNT} Wheels)"
echo "  Projekt-Wheel: $(basename "$PROJECT_WHEEL")"

echo "Erstelle ${STAGE}/ ..."
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -r dist "$STAGE/dist"

cat > "$STAGE/install-client.sh" << 'INSTALL_EOF'
#!/usr/bin/env bash
set -euo pipefail

CLIENT_VENV="${HOME}/.venvs/llmflask-client"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

show_help() {
    cat <<'EOF'
Usage: install-client.sh [--help]

Installiert LLMFlask aus dem Offline-Paket in:
  ~/.venvs/llmflask-client

Der Zielrechner braucht Python >= 3.12. Internet, Git und SSH sind nicht
erforderlich.

Beispiele:
  ./install-client.sh
  ~/.venvs/llmflask-client/bin/llmflask --tui --host SERVER_IP --user alice
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

echo "== llmflask Client Install =="

command -v python3 >/dev/null || { echo "FEHLER: python3 fehlt — bitte Python >= 3.12 installieren"; exit 1; }

PY_VERSION=$(python3 -c 'import sys; print(sys.version_info[:2])')
PY_MAJOR=$(echo "$PY_VERSION" | python3 -c 'import sys,ast; m=ast.literal_eval(sys.stdin.read()); print(m[0])')
PY_MINOR=$(echo "$PY_VERSION" | python3 -c 'import sys,ast; m=ast.literal_eval(sys.stdin.read()); print(m[1])')
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 12 ]; }; then
    echo "FEHLER: Python >= 3.12 benoetigt (gefunden: ${PY_MAJOR}.${PY_MINOR})"
    exit 1
fi
echo "  Python: ${PY_MAJOR}.${PY_MINOR}"

if [ -d "$CLIENT_VENV" ]; then
    echo "  Venv vorhanden: $CLIENT_VENV"
else
    echo "  Erstelle venv:  $CLIENT_VENV"
    python3 -m venv "$CLIENT_VENV"
fi

echo "Installiere llmflask + Abhaengigkeiten..."
"$CLIENT_VENV/bin/pip" install --no-index --find-links "$SCRIPT_DIR/dist" llmflask 2>&1

echo
echo "=== Fertig ==="
echo "Start:    $CLIENT_VENV/bin/llmflask --tui --host SERVER_IP"
echo "          $CLIENT_VENV/bin/llmflask --tui --host SERVER_IP --user standard"
echo "Aktualisieren: erneut ./install-client.sh ausfuehren (idempotent)"
echo
INSTALL_EOF

chmod +x "$STAGE/install-client.sh"

echo "Packe ${TGZ} ..."
tar czf "$TGZ" "$STAGE"
rm -rf "$STAGE"

TAR_SIZE=$(du -h "$TGZ" | cut -f1)
echo "  ${TGZ} (${TAR_SIZE})"

echo
echo "=== Fertig ==="
echo
echo "Weitergeben an Client:"
echo "  scp ${ROOT_TGZ} user@client:"
echo "  rsync -avP ${ROOT_TGZ} user@client:"
echo "  (aus components/llmflask: scp ${TGZ} user@client:)"
echo
echo "Auf dem Client:"
echo "  tar xzf ${TGZ}"
echo "  ./${STAGE}/install-client.sh"
echo
