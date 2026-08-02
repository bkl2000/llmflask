#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail

# setup-searxng.sh
#
# Default:
#   ./setup-searxng.sh
#
# Custom port:
#   SEARXNG_PORT=8072 ./setup-searxng.sh

show_help() {
  cat <<'EOF'
Usage: setup-searxng.sh [--help]

Installiert/aktualisiert SearXNG per Docker Compose und aktiviert JSON-Ausgabe.

Umgebung:
  SEARXNG_DIR=~/docker/searxng  Installationsverzeichnis
  SEARXNG_PORT=8071             Web/API-Port

Beispiele:
  ./components/local-ai/setup-searxng.sh
  SEARXNG_PORT=8072 ./components/local-ai/setup-searxng.sh
  make install-searxng
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  show_help
  exit 0
fi

SEARXNG_DIR="${SEARXNG_DIR:-$HOME/docker/searxng}"
SEARXNG_PORT="${SEARXNG_PORT:-8071}"
CONTAINER_NAME="searxng"

command -v docker >/dev/null || { echo "FEHLER: docker fehlt"; exit 1; }
command -v curl >/dev/null || { echo "FEHLER: curl fehlt"; exit 1; }

COMPOSE=""
for candidate in "docker-compose" "docker compose"; do
    if $candidate version >/dev/null 2>&1; then
        COMPOSE="$candidate"
        break
    fi
done
if [ -z "$COMPOSE" ]; then
    echo "Error: neither docker-compose nor docker compose is available" >&2
    exit 1
fi

echo "== SearXNG Setup =="
echo "Compose: $COMPOSE"
echo "Port:    $SEARXNG_PORT"
echo "Dir:     $SEARXNG_DIR"

mkdir -p "$SEARXNG_DIR/searxng"
cd "$SEARXNG_DIR"

cat > docker-compose.yml <<EOF
version: "3.8"

services:
  searxng:
    image: searxng/searxng:latest
    container_name: ${CONTAINER_NAME}
    restart: unless-stopped
    ports:
      - "${SEARXNG_PORT}:8080"
    volumes:
      - ./searxng:/etc/searxng:rw
    environment:
      - SEARXNG_BASE_URL=http://localhost:${SEARXNG_PORT}/
EOF

$COMPOSE pull
$COMPOSE up -d

sleep 5

if [ ! -f searxng/settings.yml ]; then
  docker cp "${CONTAINER_NAME}:/etc/searxng/settings.yml" searxng/settings.yml
fi

sudo chown -R "$USER:$USER" searxng

SETTINGS_CHANGED=false
SETTINGS_BACKED_UP=false

backup_settings() {
  if [ "$SETTINGS_BACKED_UP" = false ]; then
    cp -a searxng/settings.yml searxng/settings.yml.llmflask-backup
    echo "Bestehende Settings gesichert: searxng/settings.yml.llmflask-backup"
    SETTINGS_BACKED_UP=true
  fi
}

if ! grep -q "^use_default_settings: true" searxng/settings.yml; then
  backup_settings
  sed -i '1i use_default_settings: true' searxng/settings.yml
  SETTINGS_CHANGED=true
fi

if ! grep -q "^search:" searxng/settings.yml; then
  backup_settings
  cat >> searxng/settings.yml <<'EOF'

search:
  formats:
    - html
    - json
EOF
  SETTINGS_CHANGED=true
elif ! grep -q "    - json" searxng/settings.yml; then
  backup_settings
  if grep -q "    - html" searxng/settings.yml; then
    sed -i '/    - html/a\    - json' searxng/settings.yml
  else
    sed -i '/^search:/a\  formats:\n    - html\n    - json' searxng/settings.yml
  fi
  SETTINGS_CHANGED=true
fi

if [ "$SETTINGS_CHANGED" = true ]; then
  echo "Config geaendert, starte Container neu..."
  $COMPOSE restart
fi

echo
echo "== Health-Check =="

# 1. API erreichbar?
for i in {1..20}; do
  if curl -fsS "http://127.0.0.1:${SEARXNG_PORT}/search?q=test&format=json" >/dev/null 2>&1; then
    echo "SearXNG API erreichbar [OK]"
    break
  fi
  sleep 2
done

curl -fsS "http://127.0.0.1:${SEARXNG_PORT}/search?q=test&format=json" >/dev/null || {
  echo "FEHLER: SearXNG nicht erreichbar"
  docker logs "$CONTAINER_NAME" --tail 80 || true
  exit 1
}

# 2. Liefert Suchergebnisse?
SEARX_RESPONSE=$(curl -fsS "http://127.0.0.1:${SEARXNG_PORT}/search?q=test&format=json" 2>/dev/null || true)
if echo "$SEARX_RESPONSE" | grep -q '"results"'; then
  RESULT_COUNT=$(echo "$SEARX_RESPONSE" | grep -o '"results"[[:space:]]*:[[:space:]]*\[.*\]' | grep -c '{' 2>/dev/null || true)
  echo "Suchergebnisse: ${RESULT_COUNT:-?} [OK]"
else
  echo "WARNUNG: SearXNG liefert keine Ergebnisse!"
  echo "  Pruefe: grep use_default ~/docker/searxng/searxng/settings.yml"
fi

# 3. use_default_settings checken
if grep -q "^use_default_settings: true" searxng/settings.yml; then
  echo "use_default_settings: true [OK]"
else
  echo "WARNUNG: use_default_settings fehlt in settings.yml"
fi

# 4. Engine-Fehler in Logs
ENGINE_ERRORS=$(docker logs "$CONTAINER_NAME" --tail 50 2>&1 | grep -ci "error\|rate limit\|timeout\|blocked" || echo "0")
if [ "$ENGINE_ERRORS" -gt 0 ]; then
  echo "WARNUNG: $ENGINE_ERRORS Fehler/Warnings in SearXNG-Logs:"
  docker logs "$CONTAINER_NAME" --tail 50 2>&1 | grep -i "error\|rate limit" | tail -5
else
  echo "Engine-Logs sauber [OK]"
fi

echo
echo "== Container =="

docker ps --filter "name=$CONTAINER_NAME"

echo
echo "== Fertig =="

cat <<EOF
SearXNG:

  http://localhost:${SEARXNG_PORT}

Test:

  curl "http://127.0.0.1:${SEARXNG_PORT}/search?q=ollama&format=json"
EOF
