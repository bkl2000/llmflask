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

run_model_selection() {
  run bash -c '
    export LLMFLASK_TEST_FUNCTIONS_ONLY=1
    nvidia-smi() {
      [ -n "${MOCK_NVIDIA_VRAM_MB:-}" ] || return 1
      case "${1:-}" in
        --query-gpu=memory.total) printf "%s\\n" "$MOCK_NVIDIA_VRAM_MB" ;;
        *) echo "NVIDIA GPU" ;;
      esac
    }
    source components/local-ai/setup-local-ai.sh
    select_models
    printf "Selected: %s\\n" "${MODELS[*]}"
  '
}

@test "No NVIDIA GPU selects only the CPU model" {
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"No NVIDIA GPU detected."* ]]
  [[ "$output" == *"Model profile: cpu"* ]]
  [[ "$output" == *"Selected: qwen3:4b-instruct-2507-q4_K_M"* ]]
  [[ "$output" != *"assuming 8 GB"* ]]
}

@test "Under 8 GB keeps the small GPU models" {
  export MOCK_NVIDIA_VRAM_MB=4096
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"NVIDIA VRAM detected: 4 GB"* ]]
  [[ "$output" == *"Model profile: 4gb"* ]]
  [[ "$output" == *"Selected: llama3.2:3b qwen3:4b-instruct-2507-q4_K_M"* ]]
}

@test "8 GB keeps the existing 8 GB models" {
  export MOCK_NVIDIA_VRAM_MB=8192
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Model profile: 8gb"* ]]
  [[ "$output" == *"Selected: llama3.1:8b qwen3:8b"* ]]
}

@test "Nominal 12 GB adds both larger models at 11 GiB detected" {
  export MOCK_NVIDIA_VRAM_MB=12282
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"NVIDIA VRAM detected: 11 GB"* ]]
  [[ "$output" == *"Model profile: 12gb"* ]]
  [[ "$output" == *"Selected: llama3.1:8b qwen3:8b qwen3:14b gemma4:12b"* ]]
}

@test "Explicit CPU profile overrides NVIDIA detection" {
  export MOCK_NVIDIA_VRAM_MB=24576 MODEL_PROFILE=cpu
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Model profile: cpu (explicit MODEL_PROFILE)"* ]]
  [[ "$output" == *"Selected: qwen3:4b-instruct-2507-q4_K_M"* ]]
}

@test "Explicit GPU profiles use their model sets" {
  export MODEL_PROFILE=4gb
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Selected: llama3.2:3b qwen3:4b-instruct-2507-q4_K_M"* ]]

  export MODEL_PROFILE=8gb
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Selected: llama3.1:8b qwen3:8b"* ]]

  export MODEL_PROFILE=12gb
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Selected: llama3.1:8b qwen3:8b qwen3:14b gemma4:12b"* ]]
}

@test "Unavailable NVIDIA VRAM uses the CPU profile" {
  export MOCK_NVIDIA_VRAM_MB=unknown
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"NVIDIA VRAM could not be detected; using CPU profile."* ]]
  [[ "$output" == *"Selected: qwen3:4b-instruct-2507-q4_K_M"* ]]
}

@test "Explicit MODELS overrides MODEL_PROFILE" {
  export MODEL_PROFILE=cpu MODELS="override:first override:second"
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Model profile: custom (MODELS override)"* ]]
  [[ "$output" == *"Selected: override:first override:second"* ]]
}

@test "Invalid MODEL_PROFILE fails before installation" {
  export MODEL_PROFILE=unknown
  run_model_selection
  [ "$status" -eq 1 ]
  [[ "$output" == *"Invalid MODEL_PROFILE 'unknown'"* ]]
  [[ "$output" == *"Valid profiles: cpu, 4gb, 8gb, 12gb, 24gb."* ]]
}

@test "32B remains opt-in at 23 GiB detected" {
  export MOCK_NVIDIA_VRAM_MB=23552 INSTALL_32B=yes
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Model profile: 24gb"* ]]
  [[ "$output" == *"Selected: llama3.1:8b qwen3:8b qwen3:14b gemma4:12b qwen3:32b"* ]]

  export MOCK_NVIDIA_VRAM_MB=16384
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Selected: llama3.1:8b qwen3:8b qwen3:14b gemma4:12b"* ]]

  export MOCK_NVIDIA_VRAM_MB=23552 INSTALL_32B=no
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Selected: llama3.1:8b qwen3:8b qwen3:14b gemma4:12b"* ]]
}

@test "Explicit 24 GB profile permits opt-in 32B" {
  export MODEL_PROFILE=24gb INSTALL_32B=yes
  run_model_selection
  [ "$status" -eq 0 ]
  [[ "$output" == *"Model profile: 24gb (explicit MODEL_PROFILE)"* ]]
  [[ "$output" == *"Selected: llama3.1:8b qwen3:8b qwen3:14b gemma4:12b qwen3:32b"* ]]
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
