#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
# Sourced by setup-local-ai.sh; model tags for the local installation profiles.

MINIMAL_MODELS=("llama3.2:3b")
CPU_MODELS=("qwen3:4b-instruct-2507-q4_K_M")
VRAM4_MODELS=("${MINIMAL_MODELS[@]}" "${CPU_MODELS[@]}")
VRAM8_MODELS=("llama3.1:8b" "qwen3.5:9b")
VRAM12_ADDITIONS=("qwen3:14b" "gemma4:12b")
VRAM24_OPTIONAL=("qwen3:32b")
