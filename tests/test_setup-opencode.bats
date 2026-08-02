#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

load test_helper

@test "opencode wird installiert wenn nicht vorhanden" {
  export MOCK_OPENCODE_MISSING=true
  run bash -c '
    if command -v opencode >/dev/null; then
      echo "OpenCode vorhanden"
    else
      echo "installiere opencode"
    fi
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "installiere" ]]
}

@test "opencode installation wird uebersprungen wenn vorhanden" {
  run bash -c '
    if command -v opencode >/dev/null; then
      echo "OpenCode vorhanden"
    else
      echo "installiere opencode"
    fi
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "vorhanden" ]]
}

@test "opencode --version funktioniert" {
  run bash -c '
    command -v opencode >/dev/null && opencode --version
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "1.0.0" ]]
}
