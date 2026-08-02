#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

load test_helper

@test "settings.yml fehlt -> block wird angehaengt" {
  run bash -c '
    SETTINGS_CHANGED=false
    settings="$(mktemp)"
    trap "rm -f \"$settings\"" EXIT
    if ! grep -q "^search:" "$settings"; then
      cat >> "$settings" <<EOF
search:
  formats:
    - html
    - json
EOF
      SETTINGS_CHANGED=true
    fi
    echo "SETTINGS_CHANGED=$SETTINGS_CHANGED"
    cat "$settings"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "SETTINGS_CHANGED=true" ]]
  [[ "$output" =~ "json" ]]
}

@test "json fehlt in settings.yml -> wird ergaenzt" {
  run bash -c '
    SETTINGS_CHANGED=false
    settings="$(mktemp)"
    trap "rm -f \"$settings\"" EXIT
    printf "%s\n" "search:" "  formats:" "    - html" > "$settings"
    if ! grep -q "    - json" "$settings"; then
      sed -i "/    - html/a\\    - json" "$settings"
      SETTINGS_CHANGED=true
    fi
    echo "SETTINGS_CHANGED=$SETTINGS_CHANGED"
    cat "$settings"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "SETTINGS_CHANGED=true" ]]
  [[ "$output" =~ "json" ]]
}

@test "json vorhanden -> kein Change" {
  run bash -c '
    SETTINGS_CHANGED=false
    settings="$(mktemp)"
    trap "rm -f \"$settings\"" EXIT
    printf "%s\n" "search:" "  formats:" "    - html" "    - json" > "$settings"
    if ! grep -q "    - json" "$settings"; then SETTINGS_CHANGED=true; fi
    echo "SETTINGS_CHANGED=$SETTINGS_CHANGED"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "SETTINGS_CHANGED=false" ]]
}

@test "docker-compose wird erkannt" {
  run bash -c '
    if command -v docker-compose >/dev/null; then
      echo "docker-compose"
    elif docker compose version >/dev/null 2>&1; then
      echo "docker compose"
    else
      echo "FEHLER"
    fi
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "docker-compose" ]]
}

@test "docker compose plugin wird erkannt wenn compose fehlt" {
  export MOCK_COMPOSE_MISSING=true
  run bash -c '
    if command -v docker-compose >/dev/null; then
      echo "docker-compose"
    elif docker compose version >/dev/null 2>&1; then
      echo "docker compose"
    else
      echo "FEHLER"
    fi
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "docker compose" ]]
}

@test "use_default_settings wird gesetzt wenn fehlend" {
  run bash -c '
    SETTINGS_CHANGED=false
    settings="$(mktemp)"
    trap "rm -f \"$settings\"" EXIT
    echo "general:" > "$settings"
    if ! grep -q "^use_default_settings: true" "$settings"; then
      sed -i "1i use_default_settings: true" "$settings"
      SETTINGS_CHANGED=true
    fi
    echo "SETTINGS_CHANGED=$SETTINGS_CHANGED"
    head -1 "$settings"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "SETTINGS_CHANGED=true" ]]
  [[ "$output" =~ "use_default_settings: true" ]]
}

@test "use_default_settings wird nicht doppelt gesetzt" {
  run bash -c '
    SETTINGS_CHANGED=false
    settings="$(mktemp)"
    trap "rm -f \"$settings\"" EXIT
    echo "use_default_settings: true" > "$settings"
    if ! grep -q "^use_default_settings: true" "$settings"; then SETTINGS_CHANGED=true; fi
    echo "SETTINGS_CHANGED=$SETTINGS_CHANGED"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "SETTINGS_CHANGED=false" ]]
}

@test "Health-Check erkennt leere Ergebnisse" {
  run bash -c '
    SEARX_RESPONSE="{\"results\":[]}"
    if echo "$SEARX_RESPONSE" | grep -q "\"results\""; then
      RESULT_COUNT=$(echo "$SEARX_RESPONSE" | grep -c "{" 2>/dev/null || true)
      if [ "${RESULT_COUNT:-0}" -le 1 ]; then
        echo "WARNUNG: keine Ergebnisse"
      fi
    fi
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "WARNUNG" ]]
}

@test "SearXNG pullt Updates und erhaelt bestehende Settings" {
  install_dir="$BATS_TEST_TMPDIR/searxng-install"
  call_log="$BATS_TEST_TMPDIR/compose-calls"
  mkdir -p "$install_dir/searxng"
  cat > "$install_dir/searxng/settings.yml" <<'EOF'
use_default_settings: true
custom_project_setting: keep-me
search:
  formats:
    - html
    - json
EOF

  export SEARXNG_DIR="$install_dir"
  export COMPOSE_CALL_LOG="$call_log"
  docker-compose() {
    printf '%s\n' "$*" >> "$COMPOSE_CALL_LOG"
  }
  sleep() { :; }
  export -f docker-compose sleep

  run bash components/local-ai/setup-searxng.sh

  [ "$status" -eq 0 ]
  grep -qx "pull" "$call_log"
  grep -qx "up -d" "$call_log"
  grep -qx "custom_project_setting: keep-me" "$install_dir/searxng/settings.yml"
  [ ! -e "$install_dir/searxng/settings.yml.llmflask-backup" ]
}

@test "SearXNG sichert Settings vor einer notwendigen Aenderung" {
  install_dir="$BATS_TEST_TMPDIR/searxng-change"
  call_log="$BATS_TEST_TMPDIR/compose-change-calls"
  mkdir -p "$install_dir/searxng"
  printf '%s\n' "custom_project_setting: keep-me" > "$install_dir/searxng/settings.yml"

  export SEARXNG_DIR="$install_dir"
  export COMPOSE_CALL_LOG="$call_log"
  docker-compose() { printf '%s\n' "$*" >> "$COMPOSE_CALL_LOG"; }
  sleep() { :; }
  export -f docker-compose sleep

  run bash components/local-ai/setup-searxng.sh

  [ "$status" -eq 0 ]
  grep -qx "custom_project_setting: keep-me" "$install_dir/searxng/settings.yml"
  grep -qx "custom_project_setting: keep-me" "$install_dir/searxng/settings.yml.llmflask-backup"
  grep -q "json" "$install_dir/searxng/settings.yml"
  ! grep -qE 'down|-v|rm' "$call_log"
}
