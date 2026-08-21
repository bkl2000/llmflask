#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

load test_helper

@test "Default Ollama data path uses the official service directory" {
  run bash -c '
    unset OLLAMA_LINK_DIR OLLAMA_REAL_DIR
    export LLMFLASK_TEST_FUNCTIONS_ONLY=1
    source components/local-ai/setup-local-ai.sh
    printf "%s\n%s\n" "$OLLAMA_LINK_DIR" "$OLLAMA_REAL_DIR"
  '
  [ "$status" -eq 0 ]
  [ "$output" = $'/usr/share/ollama\n/usr/share/ollama' ]
}

@test "Existing default Ollama symlink preserves its alternate filesystem" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    export OLLAMA_LINK_DIR="$base/official"
    unset OLLAMA_REAL_DIR
    export OLLAMA_SERVICE_UNIT="$base/ollama.service"
    alternate_dir="$base/large-disk/ollama"
    mkdir -p "$alternate_dir/.ollama/models"
    ln -s "$alternate_dir" "$OLLAMA_LINK_DIR"
    printf "ExecStart=/usr/local/bin/ollama serve\n" > "$OLLAMA_SERVICE_UNIT"
    chown() { return 0; }
    export LLMFLASK_TEST_FUNCTIONS_ONLY=1
    source components/local-ai/setup-local-ai.sh
    prepare_ollama_model_path
    [ -L "$OLLAMA_LINK_DIR" ]
    [ "$(readlink -f "$OLLAMA_LINK_DIR")" = "$alternate_dir" ]
    grep -q "OLLAMA_MODELS=$alternate_dir/.ollama/models" "$OLLAMA_SERVICE_UNIT"
  '
  [ "$status" -eq 0 ]
}

@test "Vorhandenes Modell wird auf Updates geprueft" {
  export OLLAMA_LIST_MOCK="llama3.1:8b               abc123      4.7GB    2 weeks ago"
  run bash -c '
    model="llama3.1:8b"
    echo "-- pruefen/aktualisieren: $model"
    ollama pull "$model"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "pruefen/aktualisieren" ]]
  [[ "$output" =~ "pulling" ]]
}

@test "Modell fehlt -> Pull wird ausgeloest" {
  export OLLAMA_LIST_MOCK=""
  run bash -c '
    model="qwen3:14b"
    if echo "" | awk "{print \$1}" | grep -qx "$model"; then
      echo "-- vorhanden: $model"
    else
      echo "-- pull: $model"
    fi
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "pull" ]]
}

@test "Symlink existiert korrekt -> OK" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    OLLAMA_LINK_DIR="$base/link"
    OLLAMA_REAL_DIR="$base/real"
    mkdir -p "$OLLAMA_REAL_DIR/.ollama/models"
    ln -s "$OLLAMA_REAL_DIR" "$OLLAMA_LINK_DIR"

    if [ -L "$OLLAMA_LINK_DIR" ]; then
      active_dir="$(readlink -f "$OLLAMA_LINK_DIR")"
      echo "Symlink OK: $active_dir"
    elif [ -d "$OLLAMA_LINK_DIR" ]; then
      active_dir="$OLLAMA_LINK_DIR"
    elif [ -e "$OLLAMA_LINK_DIR" ]; then
      echo "FEHLER"
      exit 1
    elif [ -d "$OLLAMA_REAL_DIR" ]; then
      active_dir="$OLLAMA_REAL_DIR"
      ln -s "$OLLAMA_REAL_DIR" "$OLLAMA_LINK_DIR"
    else
      active_dir="$OLLAMA_LINK_DIR"
    fi
    mkdir -p "$active_dir/.ollama/models"
    [ -d "$active_dir/.ollama/models" ]
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Symlink OK" ]]
}

@test "Vorhandenes Datenverzeichnis -> OK" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    OLLAMA_LINK_DIR="$base/link"
    OLLAMA_REAL_DIR="$base/real"
    mkdir -p "$OLLAMA_LINK_DIR/.ollama/models"

    if [ -L "$OLLAMA_LINK_DIR" ]; then
      active_dir="$(readlink -f "$OLLAMA_LINK_DIR")"
    elif [ -d "$OLLAMA_LINK_DIR" ]; then
      active_dir="$OLLAMA_LINK_DIR"
      echo "Verzeichnis OK: $active_dir"
    elif [ -e "$OLLAMA_LINK_DIR" ]; then
      echo "FEHLER"
      exit 1
    elif [ -d "$OLLAMA_REAL_DIR" ]; then
      active_dir="$OLLAMA_REAL_DIR"
      ln -s "$OLLAMA_REAL_DIR" "$OLLAMA_LINK_DIR"
    else
      active_dir="$OLLAMA_LINK_DIR"
    fi
    mkdir -p "$active_dir/.ollama/models"
    [ -d "$active_dir/.ollama/models" ]
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Verzeichnis OK" ]]
}

@test "Legacy-Datenverzeichnis ohne Link -> ln -s wird angelegt" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    OLLAMA_LINK_DIR="$base/link"
    OLLAMA_REAL_DIR="$base/real"
    mkdir -p "$OLLAMA_REAL_DIR"

    if [ -L "$OLLAMA_LINK_DIR" ]; then
      active_dir="$(readlink -f "$OLLAMA_LINK_DIR")"
    elif [ -d "$OLLAMA_LINK_DIR" ]; then
      active_dir="$OLLAMA_LINK_DIR"
    elif [ -e "$OLLAMA_LINK_DIR" ]; then
      echo "FEHLER"
      exit 1
    elif [ -d "$OLLAMA_REAL_DIR" ]; then
      active_dir="$OLLAMA_REAL_DIR"
      ln -s "$OLLAMA_REAL_DIR" "$OLLAMA_LINK_DIR"
      echo "Link angelegt"
    else
      active_dir="$OLLAMA_LINK_DIR"
    fi
    mkdir -p "$active_dir/.ollama/models"
    [ -L "$OLLAMA_LINK_DIR" ]
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Link angelegt" ]]
}

@test "Neue Installation -> offizielles Datenverzeichnis wird angelegt" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    OLLAMA_LINK_DIR="$base/link"
    OLLAMA_REAL_DIR="$base/real"

    if [ -L "$OLLAMA_LINK_DIR" ]; then
      active_dir="$(readlink -f "$OLLAMA_LINK_DIR")"
    elif [ -d "$OLLAMA_LINK_DIR" ]; then
      active_dir="$OLLAMA_LINK_DIR"
    elif [ -e "$OLLAMA_LINK_DIR" ]; then
      echo "FEHLER"
      exit 1
    elif [ -d "$OLLAMA_REAL_DIR" ]; then
      active_dir="$OLLAMA_REAL_DIR"
      ln -s "$OLLAMA_REAL_DIR" "$OLLAMA_LINK_DIR"
    else
      active_dir="$OLLAMA_LINK_DIR"
      echo "Verzeichnis wird angelegt"
    fi
    mkdir -p "$active_dir/.ollama/models"
    [ -d "$OLLAMA_LINK_DIR/.ollama/models" ]
    [ ! -L "$OLLAMA_LINK_DIR" ]
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Verzeichnis wird angelegt" ]]
}

@test "Ungueltiger bestehender Pfad -> Fehler" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    OLLAMA_LINK_DIR="$base/link"
    OLLAMA_REAL_DIR="$base/real"
    touch "$OLLAMA_LINK_DIR"

    if [ -L "$OLLAMA_LINK_DIR" ]; then
      active_dir="$(readlink -f "$OLLAMA_LINK_DIR")"
    elif [ -d "$OLLAMA_LINK_DIR" ]; then
      active_dir="$OLLAMA_LINK_DIR"
    elif [ -e "$OLLAMA_LINK_DIR" ]; then
      echo "FEHLER: existiert, ist aber weder Verzeichnis noch Symlink"
      exit 1
    elif [ -d "$OLLAMA_REAL_DIR" ]; then
      active_dir="$OLLAMA_REAL_DIR"
      ln -s "$OLLAMA_REAL_DIR" "$OLLAMA_LINK_DIR"
    else
      active_dir="$OLLAMA_LINK_DIR"
    fi
    mkdir -p "$active_dir/.ollama/models"
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "FEHLER" ]]
}

@test "Unerwartetes Ollama-Symlinkziel wird vor chown abgelehnt" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    export OLLAMA_LINK_DIR="$base/link"
    export OLLAMA_REAL_DIR="$base/expected"
    mkdir -p "$OLLAMA_REAL_DIR" "$base/unexpected"
    ln -s "$base/unexpected" "$OLLAMA_LINK_DIR"
    export LLMFLASK_TEST_FUNCTIONS_ONLY=1
    source components/local-ai/setup-local-ai.sh
    prepare_ollama_model_path
  '
  [ "$status" -eq 1 ]
}

@test "Dangling Symlink wird repariert und OLLAMA_MODELS gesetzt" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    export OLLAMA_LINK_DIR="$base/link"
    export OLLAMA_REAL_DIR="$base/real"
    export OLLAMA_SERVICE_UNIT="$base/ollama.service"
    chown() { return 0; }
    ln -s "$base/does-not-exist" "$OLLAMA_LINK_DIR"
    printf "ExecStart=/usr/local/bin/ollama serve\n" > "$OLLAMA_SERVICE_UNIT"
    export LLMFLASK_TEST_FUNCTIONS_ONLY=1
    source components/local-ai/setup-local-ai.sh
    prepare_ollama_model_path
    [ ! -L "$OLLAMA_LINK_DIR" ]
    [ -d "$OLLAMA_LINK_DIR/.ollama/models" ]
    grep -q "OLLAMA_MODELS=$OLLAMA_LINK_DIR/.ollama/models" "$OLLAMA_SERVICE_UNIT"
  '
  [ "$status" -eq 0 ]
}

@test "OLLAMA_MODELS vorhanden -> keine Doppelzeile in der Unit" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    export OLLAMA_LINK_DIR="$base/link"
    export OLLAMA_REAL_DIR="$base/real"
    export OLLAMA_SERVICE_UNIT="$base/ollama.service"
    chown() { return 0; }
    mkdir -p "$OLLAMA_LINK_DIR/.ollama/models"
    printf "ExecStart=/usr/local/bin/ollama serve\nEnvironment=\"OLLAMA_MODELS=/custom/models\"\n" > "$OLLAMA_SERVICE_UNIT"
    export LLMFLASK_TEST_FUNCTIONS_ONLY=1
    source components/local-ai/setup-local-ai.sh
    prepare_ollama_model_path
    [ "$(grep -c OLLAMA_MODELS "$OLLAMA_SERVICE_UNIT")" -eq 1 ]
  '
  [ "$status" -eq 0 ]
}

@test "OLLAMA_MODELS env-Override wird respektiert" {
  run bash -c '
    base="$(mktemp -d)"
    trap "rm -rf \"$base\"" EXIT
    export OLLAMA_LINK_DIR="$base/link"
    export OLLAMA_REAL_DIR="$base/real"
    export OLLAMA_SERVICE_UNIT="$base/ollama.service"
    export OLLAMA_MODELS="$base/custom-models"
    chown() { return 0; }
    mkdir -p "$OLLAMA_LINK_DIR/.ollama/models"
    printf "ExecStart=/usr/local/bin/ollama serve\n" > "$OLLAMA_SERVICE_UNIT"
    export LLMFLASK_TEST_FUNCTIONS_ONLY=1
    source components/local-ai/setup-local-ai.sh
    prepare_ollama_model_path
    grep -q "OLLAMA_MODELS=$base/custom-models" "$OLLAMA_SERVICE_UNIT"
  '
  [ "$status" -eq 0 ]
}

@test "Ollama chown bleibt auf den .ollama-Datenbaum begrenzt" {
  run grep -F 'sudo chown -R ollama:ollama "$active_dir/.ollama"' components/local-ai/setup-local-ai.sh
  [ "$status" -eq 0 ]
}

@test "curl ist vorhanden" {
  run command -v curl
  [ "$status" -eq 0 ]
}

@test "git ist vorhanden" {
  run command -v git
  [ "$status" -eq 0 ]
}

@test "VRAM 4 GB -> nur kleine Modelle" {
  run bash -c '
    VRAM_GB=4
    if [ "$VRAM_GB" -lt 8 ]; then
      MODELS=("llama3.2:3b" "qwen3:4b-instruct-2507-q4_K_M")
    else
      MODELS=("llama3.1:8b" "qwen3:8b")
      if [ "$VRAM_GB" -ge 11 ]; then
        MODELS+=("qwen3:14b")
      fi
    fi
    echo "Modelle: ${MODELS[*]}"
    echo "Anzahl: ${#MODELS[@]}"
    [[ "${MODELS[*]}" =~ "llama3.2:3b" ]]
    [[ "${MODELS[*]}" =~ "qwen3:4b-instruct-2507-q4_K_M" ]]
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Anzahl: 2" ]]
}

@test "Installer pins current Qwen tiers and full-GPU 32B threshold" {
  run bash -c '
    script=components/local-ai/setup-local-ai.sh
    grep -qF "qwen3:4b-instruct-2507-q4_K_M" "$script"
    grep -qF "qwen3:8b" "$script"
    grep -qF "qwen3:14b" "$script"
    grep -qF "MODEL_32B_MIN_VRAM_GB=23" "$script"
    ! grep -qF "qwen3:1.7b" "$script"
    ! grep -qF "qwen3:latest" "$script"
  '
  [ "$status" -eq 0 ]
}

@test "VRAM 8 GB -> nur Basis-Modelle" {
  run bash -c '
    VRAM_GB=8
    MODELS=("llama3.1:8b" "qwen3:8b")
    if [ "$VRAM_GB" -ge 11 ]; then
      MODELS+=("qwen3:14b")
    fi
    echo "Modelle: ${MODELS[*]}"
    echo "Anzahl: ${#MODELS[@]}"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Anzahl: 2" ]]
}

@test "VRAM 11 GB -> + 14b Modell" {
  run bash -c '
    VRAM_GB=11
    MODELS=("llama3.1:8b" "qwen3:8b")
    if [ "$VRAM_GB" -ge 11 ]; then
      MODELS+=("qwen3:14b")
    fi
    echo "Modelle: ${MODELS[*]}"
    echo "Anzahl: ${#MODELS[@]}"
    [[ "${MODELS[*]}" =~ "14b" ]]
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Anzahl: 3" ]]
}

@test "INSTALL_32B=yes + 23 GiB detected -> + 32b" {
  run bash -c '
    INSTALL_32B=yes
    MODEL_32B_MIN_VRAM_GB=23
    VRAM_GB=23
    MODELS=("llama3.1:8b" "qwen3:8b")
    if [ "$VRAM_GB" -ge 11 ]; then
      MODELS+=("qwen3:14b")
    fi
    if [ "$INSTALL_32B" = "yes" ] && [ "$VRAM_GB" -ge "$MODEL_32B_MIN_VRAM_GB" ]; then
      MODELS+=("qwen3:32b")
    fi
    echo "Modelle: ${MODELS[*]}"
    echo "Anzahl: ${#MODELS[@]}"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Anzahl: 4" ]]
}

@test "INSTALL_32B=yes + 16 GB -> kein 32b" {
  run bash -c '
    INSTALL_32B=yes
    MODEL_32B_MIN_VRAM_GB=23
    VRAM_GB=16
    MODELS=("llama3.1:8b" "qwen3:8b")
    if [ "$VRAM_GB" -ge 11 ]; then
      MODELS+=("qwen3:14b")
    fi
    if [ "$INSTALL_32B" = "yes" ] && [ "$VRAM_GB" -ge "$MODEL_32B_MIN_VRAM_GB" ]; then
      MODELS+=("qwen3:32b")
    fi
    echo "Modelle: ${MODELS[*]}"
    echo "Anzahl: ${#MODELS[@]}"
    [[ ! "${MODELS[*]}" =~ "qwen3:32b" ]]
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Anzahl: 3" ]]
}

@test "MODELS via Env (String) wird in Array umgewandelt" {
  run bash -c '
    MODELS="llama3.1:8b qwen3:14b qwen3:8b"
    read -ra MODELS <<< "$MODELS"
    echo "Modelle: ${MODELS[*]}"
    echo "Anzahl: ${#MODELS[@]}"
    for m in "${MODELS[@]}"; do echo "  - $m"; done
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Anzahl: 3" ]]
  [[ "$output" =~ "llama3.1:8b" ]]
  [[ "$output" =~ "qwen3:14b" ]]
}

@test "User not in ollama group -> usermod called" {
  run bash -c '
    USER=testuser
    id() { if [ "$1" = "-nG" ]; then echo "testuser nogroup"; fi; }
    getent() { if [ "$1" = "group" ] && [ "$2" = "ollama" ]; then return 0; fi; }
    usermod() { echo "usermod called: $@"; }
    export -f id getent usermod
    ensure_group_membership() {
      if getent group ollama >/dev/null 2>&1; then
        if ! id -nG "$USER" 2>/dev/null | grep -qw ollama; then
          echo "Adding $USER to the ollama group (needed for ollama pull without sudo)"
          usermod -aG ollama "$USER"
          echo "NOTE: Re-login required for group membership to take effect."
        fi
      fi
    }
    ensure_group_membership
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "usermod called" ]]
  [[ "$output" =~ "Re-login required" ]]
}

@test "User already in ollama group -> no usermod" {
  run bash -c '
    USER=testuser
    id() { if [ "$1" = "-nG" ]; then echo "testuser ollama"; fi; }
    getent() { if [ "$1" = "group" ] && [ "$2" = "ollama" ]; then return 0; fi; }
    usermod() { echo "SHOULD NOT CALL USERMOD"; exit 1; }
    export -f id getent usermod
    ensure_group_membership() {
      if getent group ollama >/dev/null 2>&1; then
        if ! id -nG "$USER" 2>/dev/null | grep -qw ollama; then
          usermod -aG ollama "$USER"
        fi
      fi
    }
    ensure_group_membership
  '
  [ "$status" -eq 0 ]
  [[ "$output" != *"usermod"* ]]
}
