#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

setup() {
  export MOCK_BIN="$BATS_TEST_TMPDIR/bin"
  export MOCK_LOG="$BATS_TEST_TMPDIR/llmflask.args"
  mkdir -p "$MOCK_BIN"
  cat > "$MOCK_BIN/llmflask" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$MOCK_LOG"
exit "${MOCK_EXIT:-0}"
EOF
  chmod +x "$MOCK_BIN/llmflask"
}

@test "llm-ask help is handled locally" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llm-ask --help

  [ "$status" -eq 0 ]
  [[ "$output" == *"List server models first"* ]]
  [ ! -e "$MOCK_LOG" ]
}

@test "llm-ask requires an explicit or configured model" {
  run env -u LLMFLASK_MODEL PATH="$MOCK_BIN:$PATH" ./tools/llm-ask "hello"

  [ "$status" -eq 2 ]
  [[ "$output" == *"a model is required"* ]]
  [ ! -e "$MOCK_LOG" ]
}

@test "llm-pool parses named file and text options" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llm-pool \
    --model ollama/qwen3:8b --file data.csv --text "analyze this"

  [ "$status" -eq 0 ]
  run grep -Fx -- "--file" "$MOCK_LOG"
  [ "$status" -eq 0 ]
  run grep -Fx -- "data.csv" "$MOCK_LOG"
  [ "$status" -eq 0 ]
  run grep -Fx -- "analyze this" "$MOCK_LOG"
  [ "$status" -eq 0 ]
}

@test "wrapper options report missing values" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llm-models --host

  [ "$status" -eq 2 ]
  [[ "$output" == *"requires a value"* ]]
}

@test "new wrapper help is handled locally" {
  for wrapper in llm-chat llm-pools llm-results llm-sessions; do
    run env PATH="$MOCK_BIN:$PATH" "./tools/$wrapper" --help
    [ "$status" -eq 0 ]
  done

  [ ! -e "$MOCK_LOG" ]
}

@test "llm-chat applies server defaults from the environment" {
  run env PATH="$MOCK_BIN:$PATH" LLMFLASK_HOST=server.local \
    LLMFLASK_PORT=60010 LLMFLASK_USER=alice ./tools/llm-chat

  [ "$status" -eq 0 ]
  grep -Fx -- "--tui" "$MOCK_LOG"
  grep -Fx -- "server.local" "$MOCK_LOG"
  grep -Fx -- "60010" "$MOCK_LOG"
  grep -Fx -- "alice" "$MOCK_LOG"
}

@test "llm-chat omits server target for a direct provider" {
  run env PATH="$MOCK_BIN:$PATH" LLMFLASK_HOST=server.local \
    LLMFLASK_PORT=60010 ./tools/llm-chat --provider openai

  [ "$status" -eq 0 ]
  grep -Fx -- "openai" "$MOCK_LOG"
  ! grep -Fx -- "--host" "$MOCK_LOG"
  ! grep -Fx -- "--port" "$MOCK_LOG"
}

@test "llm-pools run uses configured model and server" {
  run env PATH="$MOCK_BIN:$PATH" LLMFLASK_HOST=server.local \
    LLMFLASK_PORT=60010 LLMFLASK_MODEL=ollama/qwen3:8b \
    ./tools/llm-pools run demo

  [ "$status" -eq 0 ]
  grep -Fx -- "pool" "$MOCK_LOG"
  grep -Fx -- "run" "$MOCK_LOG"
  grep -Fx -- "demo" "$MOCK_LOG"
  grep -Fx -- "ollama/qwen3:8b" "$MOCK_LOG"
}

@test "llm-pools run requires an explicit or configured model" {
  run env -u LLMFLASK_MODEL PATH="$MOCK_BIN:$PATH" ./tools/llm-pools run demo

  [ "$status" -eq 2 ]
  [[ "$output" == *"run requires --model"* ]]
  [ ! -e "$MOCK_LOG" ]
}

@test "llm-pools forwards run subcommand help without requiring a model" {
  run env -u LLMFLASK_MODEL PATH="$MOCK_BIN:$PATH" ./tools/llm-pools run --help

  [ "$status" -eq 0 ]
  grep -Fx -- "run" "$MOCK_LOG"
  grep -Fx -- "--help" "$MOCK_LOG"
}

@test "llm-results forwards actions and llmflask exit status" {
  run env PATH="$MOCK_BIN:$PATH" MOCK_EXIT=7 ./tools/llm-results remove all

  [ "$status" -eq 7 ]
  grep -Fx -- "result" "$MOCK_LOG"
  grep -Fx -- "remove" "$MOCK_LOG"
  grep -Fx -- "all" "$MOCK_LOG"
}

@test "llm-sessions applies user and server defaults" {
  run env PATH="$MOCK_BIN:$PATH" LLMFLASK_HOST=server.local \
    LLMFLASK_PORT=60010 LLMFLASK_USER=alice ./tools/llm-sessions remove all

  [ "$status" -eq 0 ]
  grep -Fx -- "server.local" "$MOCK_LOG"
  grep -Fx -- "60010" "$MOCK_LOG"
  grep -Fx -- "alice" "$MOCK_LOG"
  grep -Fx -- "session" "$MOCK_LOG"
  grep -Fx -- "all" "$MOCK_LOG"
}

@test "llmflaskcmd help is handled locally" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llmflaskcmd --help

  [ "$status" -eq 0 ]
  [[ "$output" == *"Defaults"* ]]
  [ ! -e "$MOCK_LOG" ]
}

@test "llmflaskcmd forwards model and provider to llmflask" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llmflaskcmd \
    --model deepseek/deepseek-chat --provider deepseek "Hello world"

  [ "$status" -eq 0 ]
  grep -Fx -- "--cmd" "$MOCK_LOG"
  grep -Fx -- "deepseek/deepseek-chat" "$MOCK_LOG"
  grep -Fx -- "deepseek" "$MOCK_LOG"
  grep -Fx -- "Hello world" "$MOCK_LOG"
}

@test "llmflaskcmd uses server defaults when provider is server" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llmflaskcmd "test"

  [ "$status" -eq 0 ]
  grep -Fx -- "--host" "$MOCK_LOG"
  grep -Fx -- "--port" "$MOCK_LOG"
  grep -Fx -- "--cmd" "$MOCK_LOG"
  grep -Fx -- "ollama/qwen3:14b" "$MOCK_LOG"
}

@test "llmflaskcmd rejects conflicting management modes" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llmflaskcmd pool list

  [ "$status" -eq 1 ]
  [[ "$output" == *"not valid"* ]]
  [ ! -e "$MOCK_LOG" ]
}

@test "llm-runresult help is handled locally" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llm-runresult --help

  [ "$status" -eq 0 ]
  [[ "$output" == *"Runs a previously"* ]]
  [ ! -e "$MOCK_LOG" ]
}

@test "llm-runresult forwards name to llmflask result run" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llm-runresult myresult

  [ "$status" -eq 0 ]
  grep -Fx -- "result" "$MOCK_LOG"
  grep -Fx -- "run" "$MOCK_LOG"
  grep -Fx -- "myresult" "$MOCK_LOG"
}

@test "llm-runresult requires a name" {
  run env PATH="$MOCK_BIN:$PATH" ./tools/llm-runresult

  [ "$status" -eq 2 ]
  [[ "$output" == *"Usage"* ]]
  [ ! -e "$MOCK_LOG" ]
}
