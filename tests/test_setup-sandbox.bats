#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

load test_helper

SCRIPT="components/llmflask/setup-sandbox.sh"

@test "Docker missing -> error" {
  export MOCK_DOCKER_MISSING=true
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Docker is not installed" ]]
}

@test "Docker daemon not reachable -> error" {
  export MOCK_DOCKER_INFO_FAIL=true
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" =~ "daemon" ]]
}

@test "Image exists -> cached update build" {
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Building sandbox image" ]]
  [[ "$output" =~ "--pull" ]]
}

@test "Image missing -> docker build runs" {
  export MOCK_DOCKER_IMAGE_MISSING=true
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Building sandbox image" ]]
  [[ "$output" =~ "built successfully" ]]
}

@test "FORCE=1 -> rebuild even if image exists" {
  export FORCE=1
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Building sandbox image" ]]
  [[ ! "$output" =~ "skipping build" ]]
}

@test "--help shows help" {
  run bash "$SCRIPT" --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
  [[ "$output" =~ "Idempotent" ]]
}

@test "Containerfile missing -> error" {
  run bash -c '
    docker() { return 0; }
    export -f docker
    script_path="components/llmflask/setup-sandbox.sh"
    mv sandbox/Containerfile sandbox/Containerfile.bak
    trap "mv sandbox/Containerfile.bak sandbox/Containerfile" EXIT
    bash "$script_path"
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Containerfile not found" ]]
}
