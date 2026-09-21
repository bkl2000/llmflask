#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
set -euo pipefail
export LC_ALL=C.UTF-8

# setup-local-ai.sh
#
# Installs/updates Ollama and models.
# Idempotent — safe to run multiple times.
#
# Every run checks the Ollama version via GitHub API — update only if needed.
# Model tags are checked with ollama pull on every run.
#
# Model selection automatic by NVIDIA GPU VRAM, with a CPU-only default.
# Models from ollama.com/library — check for updates:
#   https://ollama.com/search
#
# Custom models via environment variable:
#   MODELS="qwen3:14b llama3.1:8b" ./setup-local-ai.sh
#   MODEL_PROFILE=cpu ./setup-local-ai.sh
#   INSTALL_32B=yes ./setup-local-ai.sh

show_help() {
  cat <<'EOF'
Usage: setup-local-ai.sh [--help]

Install/update Ollama and local models:
  - Ollama
  - models selected automatically for CPU or NVIDIA GPU memory

Environment:
  MODEL_PROFILE=cpu|4gb|8gb|12gb|24gb  override automatic selection
  MODELS="qwen3:14b llama3.1:8b"  explicit model list
  INSTALL_32B=yes                  install qwen3:32b on a nominal 24 GB GPU

MODELS takes priority over MODEL_PROFILE. CPU-only systems are detected automatically.

Full stack:
  make install-ai

Examples:
  make install-ai
  make install-ai MODEL_PROFILE=cpu
  make install-ai MODELS="qwen3:14b"
  ./components/local-ai/setup-local-ai.sh
  MODEL_PROFILE=cpu ./components/local-ai/setup-local-ai.sh
  INSTALL_32B=yes ./components/local-ai/setup-local-ai.sh
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  show_help
  exit 0
fi

INSTALL_32B="${INSTALL_32B:-no}"
MODEL_GEMMA4_12B_MIN_VRAM_GB=11
MODEL_32B_MIN_VRAM_GB=23
CPU_MODELS=("qwen3:4b-instruct-2507-q4_K_M")
VRAM4_MODELS=("llama3.2:3b" "${CPU_MODELS[@]}")
VRAM8_MODELS=("llama3.1:8b" "qwen3:8b")
VRAM12_ADDITIONS=("qwen3:14b" "gemma4:12b")
VRAM24_OPTIONAL=("qwen3:32b")

OLLAMA_LINK_DIR="${OLLAMA_LINK_DIR:-/usr/share/ollama}"
OLLAMA_REAL_DIR="${OLLAMA_REAL_DIR:-$OLLAMA_LINK_DIR}"

prepare_ollama_model_path() {
  local active_dir

  sudo systemctl stop ollama >/dev/null 2>&1 || true

  # Dangling Symlinks reparieren: Ziel fehlt -> Symlink entfernen, echtes
  # Datenverzeichnis wird nachfolgend angelegt.
  if [ -L "$OLLAMA_LINK_DIR" ] && [ ! -e "$OLLAMA_LINK_DIR" ]; then
    echo "WARNING: Dangling symlink removed: $OLLAMA_LINK_DIR"
    sudo rm "$OLLAMA_LINK_DIR"
  fi

  if [ -L "$OLLAMA_LINK_DIR" ]; then
    active_dir="$(readlink -f "$OLLAMA_LINK_DIR")" || {
      echo "ERROR: Broken symlink: $OLLAMA_LINK_DIR"
      exit 1
    }
    if [ "$active_dir" != "$(readlink -f "$OLLAMA_REAL_DIR")" ]; then
      echo "ERROR: $OLLAMA_LINK_DIR points to an unexpected target: $active_dir"
      echo "Expected: $OLLAMA_REAL_DIR"
      exit 1
    fi
    echo "$OLLAMA_LINK_DIR is a symlink: $active_dir"
  elif [ -d "$OLLAMA_LINK_DIR" ]; then
    active_dir="$OLLAMA_LINK_DIR"
    echo "$OLLAMA_LINK_DIR is an existing directory"
  elif [ -e "$OLLAMA_LINK_DIR" ]; then
    echo "ERROR: $OLLAMA_LINK_DIR exists but is neither a directory nor a symlink."
    echo "Please check:"
    echo "  sudo ls -ld $OLLAMA_LINK_DIR"
    exit 1
  elif [ -d "$OLLAMA_REAL_DIR" ]; then
    active_dir="$OLLAMA_REAL_DIR"
    sudo ln -s "$OLLAMA_REAL_DIR" "$OLLAMA_LINK_DIR"
    echo "$OLLAMA_LINK_DIR -> $OLLAMA_REAL_DIR created"
  else
    active_dir="$OLLAMA_LINK_DIR"
    echo "$OLLAMA_LINK_DIR created as Ollama data directory"
  fi

  sudo mkdir -p "$active_dir/.ollama/models"

  sudo [ -d "$active_dir/.ollama/models" ] || {
    echo "ERROR: Ollama model path missing: $active_dir/.ollama/models"
    exit 1
  }

  sudo chown -R ollama:ollama "$active_dir/.ollama"

  if [ -L "$OLLAMA_LINK_DIR" ]; then
    sudo chown -h ollama:ollama "$OLLAMA_LINK_DIR" || true
  fi

  ensure_ollama_service_models_env "$active_dir"
}

# Stellt sicher, dass der systemd-Dienst die Modelle findet: OLLAMA_MODELS
# idempotent in die Unit schreiben und dem ollama-User Schreibzugriff auf
# das Modellverzeichnis geben (ollama pull laeuft als User=ollama).
ensure_ollama_service_models_env() {
  local active_dir="$1"
  local unit="${OLLAMA_SERVICE_UNIT:-/etc/systemd/system/ollama.service}"
  local models_dir="${OLLAMA_MODELS:-$active_dir/.ollama/models}"

  sudo mkdir -p "$models_dir" 2>/dev/null || true
  sudo chown -R ollama:ollama "$models_dir"

  if grep -q "OLLAMA_MODELS=" "$unit" 2>/dev/null; then
    echo "OLLAMA_MODELS is already set in $unit."
  else
    echo "Setting OLLAMA_MODELS=$models_dir in $unit"
    sudo sed -i "/^ExecStart=/a Environment=\"OLLAMA_MODELS=$models_dir\"" "$unit"
    sudo systemctl daemon-reload
  fi
}

select_models() {
  local nvidia_smi_output vram_mb vram_gb

  if [ -n "${MODELS+x}" ]; then
    read -ra MODELS <<< "$MODELS"
    echo "Model profile: custom (MODELS override)"
  else
    if [ -n "${MODEL_PROFILE+x}" ]; then
      echo "Model profile: $MODEL_PROFILE (explicit MODEL_PROFILE)"
    elif nvidia_smi_output=$(nvidia-smi 2>/dev/null); then
      echo "$nvidia_smi_output"
      if vram_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null); then
        vram_mb=${vram_mb%%$'\n'*}
      fi
      if [[ "${vram_mb:-}" =~ ^[0-9]+$ ]]; then
        vram_gb=$((10#$vram_mb / 1024))
        echo "NVIDIA VRAM detected: ${vram_gb} GB"
        if [ "$vram_gb" -lt 8 ]; then
          MODEL_PROFILE=4gb
        elif [ "$vram_gb" -lt "$MODEL_GEMMA4_12B_MIN_VRAM_GB" ]; then
          MODEL_PROFILE=8gb
        elif [ "$vram_gb" -lt "$MODEL_32B_MIN_VRAM_GB" ]; then
          MODEL_PROFILE=12gb
        else
          MODEL_PROFILE=24gb
        fi
      else
        echo "NVIDIA VRAM could not be detected; using CPU profile."
        MODEL_PROFILE=cpu
      fi
      echo "Model profile: $MODEL_PROFILE"
    else
      echo "No NVIDIA GPU detected."
      MODEL_PROFILE=cpu
      echo "Model profile: $MODEL_PROFILE"
    fi

    case "$MODEL_PROFILE" in
      cpu) MODELS=("${CPU_MODELS[@]}") ;;
      4gb) MODELS=("${VRAM4_MODELS[@]}") ;;
      8gb) MODELS=("${VRAM8_MODELS[@]}") ;;
      12gb|24gb)
        MODELS=("${VRAM8_MODELS[@]}" "${VRAM12_ADDITIONS[@]}")
        if [ "$MODEL_PROFILE" = 24gb ] && [ "$INSTALL_32B" = yes ]; then
          MODELS+=("${VRAM24_OPTIONAL[@]}")
        fi
        ;;
      *)
        echo "ERROR: Invalid MODEL_PROFILE '$MODEL_PROFILE'. Valid profiles: cpu, 4gb, 8gb, 12gb, 24gb." >&2
        return 1
        ;;
    esac
  fi

  echo "Models: ${MODELS[*]}"
}

if [ "${LLMFLASK_TEST_FUNCTIONS_ONLY:-}" = "1" ]; then
  return 0 2>/dev/null || exit 0
fi

_has_sudo() {
    if (id -nG || true) 2>/dev/null | grep -qE '(^| )(sudo|wheel)( |$)'; then
        return 0
    fi
    if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        return 0
    fi
    return 1
}

echo "== System Check =="

command -v curl >/dev/null || { echo "ERROR: curl is missing"; exit 1; }
command -v git >/dev/null || { echo "ERROR: git is missing"; exit 1; }

select_models

echo
echo "== Ollama Install/Update =="

if command -v ollama >/dev/null; then
  CURRENT_VER=$(ollama --version 2>/dev/null | grep -o '[0-9.]*' | head -1)
  echo "Installed: $CURRENT_VER"

  LATEST_TAG=$(curl -fsSL https://api.github.com/repos/ollama/ollama/releases/latest 2>/dev/null \
    | grep -o '"tag_name": "v[0-9.]*"' | grep -o '[0-9.]*' | tail -1) || true
  echo "Available: ${LATEST_TAG:-(could not check)}"

  if [ -n "$LATEST_TAG" ] && [ "$CURRENT_VER" != "$LATEST_TAG" ]; then
    echo "Updating from $CURRENT_VER to $LATEST_TAG"
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "Ollama is up to date."
  fi
else
  echo "Ollama not found, installing..."
  if (( EUID != 0 )) && ! _has_sudo; then
    echo ""
    echo "ERROR: sudo access is required to install Ollama."
    echo "  Option 1: Add your user to the sudo group as root, then re-login:"
    echo "      su -c '/usr/sbin/usermod -aG sudo $USER'"
    echo "  Option 2: Install Ollama manually as root, then run make all again:"
    echo "      su -c 'curl -fsSL https://ollama.com/install.sh | sh'"
    exit 1
  fi
  curl -fsSL https://ollama.com/install.sh | sh
fi

echo "Status: $(ollama --version 2>/dev/null || echo 'not available')"

echo
echo "== Prepare Ollama Model Path =="

prepare_ollama_model_path

echo
echo "== Start Ollama Service =="

echo "Configuring systemd service (systemctl needs sudo)..."
sudo systemctl enable ollama >/dev/null
sudo systemctl restart ollama

for i in {1..30}; do
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  sleep 2
done

curl -fsS http://127.0.0.1:11434/api/tags >/dev/null || {
  echo "ERROR: Ollama API is not reachable"
  systemctl status ollama --no-pager || true
  exit 1
}

ensure_group_membership() {
  if getent group ollama >/dev/null 2>&1; then
    if ! id -nG "$USER" 2>/dev/null | grep -qw ollama; then
      echo "Adding $USER to the ollama group (needed for ollama pull without sudo)"
      sudo usermod -aG ollama "$USER"
      echo "NOTE: Re-login required for group membership to take effect."
    fi
  fi
}
ensure_group_membership

echo
echo "== Model Check/Pull =="
echo "Models from ollama.com/library — check for updates: https://ollama.com/search"

for model in "${MODELS[@]}"; do
  echo "-- checking/pulling: $model"
  ollama pull "$model"
done

echo
echo "== Models =="

ollama list

echo
echo "== Docker Container =="

command -v docker >/dev/null && docker ps -a || true

echo
echo "== GPU/VRAM =="

command -v nvidia-smi >/dev/null && nvidia-smi || true

echo
echo "== Done =="

cat <<EOF
SearXNG:

    make install-searxng

OpenCode:

    make install-opencode

Standard (auto-detect CPU or NVIDIA VRAM):

    make install-ai

CPU profile explicitly (normally detected automatically):

    make install-ai MODEL_PROFILE=cpu

Specify models manually:

    MODELS="qwen3:14b llama3.1:8b" make install-ai

With 32B (nominal 24 GB VRAM for full-GPU use):

    INSTALL_32B=yes make install-ai

Check for new model versions:
  https://ollama.com/search

VRAM recommendations:
- CPU:   qwen3:4b-instruct-2507-q4_K_M
- 4 GB:  llama3.2:3b + qwen3:4b-instruct-2507-q4_K_M (~2.5 GB), context 2048 for speed
- 8 GB:  llama3.1:8b + qwen3:8b, context 4096 for speed
- 12 GB: 8B with context 8192; qwen3:14b + gemma4:12b as quality tests
- 24+ GB: qwen3:32b opt-in test

Performance:
- CPU shares in "ollama ps" indicate offloading; reduce context/model.
- OLLAMA_NUM_PARALLEL=1 is the safe default for 8/12 GB.
EOF
