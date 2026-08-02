#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

setup() {
    export MOCK_BIN="$BATS_TEST_TMPDIR/bin"
    export MOCK_LOG="$BATS_TEST_TMPDIR/llmflask.args"
    export MOCK_CMD_DELAY=0
    mkdir -p "$MOCK_BIN"

    cat > "$MOCK_BIN/llmflask" <<'MOCKEOF'
#!/usr/bin/env bash
echo "$@" >> "$MOCK_LOG"
case "$*" in
    *--models*)
        printf "MODELREF\tPROVIDER\tLABEL\tSIZE\tVRAM\n"
        printf "ollama/llama3.2:3b\tollama\tOllama: llama3.2:3b\t1.9G\t4 GB\n"
        printf "zen/big-pickle\tzen\tOpenCode Zen: big-pickle\t\t\n"
        printf "zen/claude-opus-5\tzen\tOpenCode Zen: claude-opus-5\t\t\n"
        printf "deepseek/deepseek-v4-flash\tdeepseek\tDeepSeek: V4 Flash\t\t\n"
        ;;
    *--cmd*)
        sleep "${MOCK_CMD_DELAY:-0}"
        echo "OK"
        ;;
    *)
        exit 1 ;;
esac
MOCKEOF
    chmod +x "$MOCK_BIN/llmflask"

    export CACHE_DIR="$BATS_TEST_TMPDIR/cache"
    export LLMFLASK_MODEL_TEST_CACHE="$CACHE_DIR/model-test.tsv"
    mkdir -p "$CACHE_DIR"
}

# --------------------------------------------------------------------------
@test "help is handled locally" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"llmflask-model-test"* ]]
    [ ! -e "$MOCK_LOG" ]
}

@test "help via -h works" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test -h
    [ "$status" -eq 0 ]
    [[ "$output" == *"llmflask-model-test"* ]]
}

@test "unknown flag exits 2" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --bogus
    [ "$status" -eq 2 ]
}

@test "--timeout without value exits 2" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --timeout
    [ "$status" -eq 2 ]
}

@test "--clear removes cache" {
    echo "dummy" > "$LLMFLASK_MODEL_TEST_CACHE"
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --clear
    [ "$status" -eq 0 ]
    [ ! -f "$LLMFLASK_MODEL_TEST_CACHE" ]
    [ ! -e "$MOCK_LOG" ]
}

@test "--show on empty cache" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --show
    [ "$status" -eq 0 ]
    [[ "$output" == "No cached results." ]]
    [ ! -e "$MOCK_LOG" ]
}

@test "first run tests all models" {
    run rm -f "$MOCK_LOG"
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test

    [ "$status" -eq 0 ]
    [[ "$output" == *"ollama/llama3.2:3b"*"OK"* ]]
    [[ "$output" == *"zen/big-pickle"*"OK"* ]]
    [[ "$output" == *"zen/claude-opus-5"*"OK"* ]]
    [[ "$output" == *"deepseek/deepseek-v4-flash"*"OK"* ]]
    [[ "$output" == *"Tested: 4"* ]]
    [[ "$output" == *"Cached: 0"* ]]
    # cache was created
    [ -f "$LLMFLASK_MODEL_TEST_CACHE" ]
    # all models in cache
    grep -qF "ollama/llama3.2:3b"$'\t' "$LLMFLASK_MODEL_TEST_CACHE"
    grep -qF "deepseek/deepseek-v4-flash"$'\t' "$LLMFLASK_MODEL_TEST_CACHE"
}

@test "second run skips cached models" {
    run rm -f "$MOCK_LOG"
    # first run
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test
    [ "$status" -eq 0 ]
    # count calls in log (models + cmd calls)
    first_calls=$(wc -l < "$MOCK_LOG")

    # second run
    rm -f "$MOCK_LOG"
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test

    [ "$status" -eq 0 ]
    [[ "$output" == *"Tested: 0"* ]]
    [[ "$output" == *"Cached: 4"* ]]
    [[ "$output" == *"(cached)"* ]]
    # only --models call, no --cmd calls
    second_calls=$(wc -l < "$MOCK_LOG")
    [ "$second_calls" -eq 1 ]
}

@test "--refresh retests all models" {
    # pre-fill cache
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test
    rm -f "$MOCK_LOG"

    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --refresh

    [ "$status" -eq 0 ]
    [[ "$output" == *"Tested: 4"* ]]
    [[ "$output" == *"Cached: 0"* ]]
    # 1 models call + 4 cmd calls
    [ "$(wc -l < "$MOCK_LOG")" -eq 5 ]
}

@test "--refresh MODEL retests only that one" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test
    rm -f "$MOCK_LOG"

    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --refresh zen/big-pickle

    [ "$status" -eq 0 ]
    [[ "$output" == *"Tested: 1"* ]]
    [[ "$output" == *"Cached: 3"* ]]
    # 1 models + 1 cmd for refreshed model
    cmd_count=$(grep -c "\--cmd" "$MOCK_LOG" || true)
    [ "$cmd_count" -eq 1 ]
}

@test "--refresh rejects --show combination" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --show --refresh
    [ "$status" -eq 2 ]
    [ ! -e "$MOCK_LOG" ]
}

@test "--timeout triggers TIMEOUT status" {
    export MOCK_CMD_DELAY=5
    run env PATH="$MOCK_BIN:$PATH" MOCK_CMD_DELAY=5 \
        ./tools/llmflask-model-test --timeout 1 ollama/llama3.2:3b

    [ "$status" -eq 0 ]
    [[ "$output" == *"TIMEOUT"* ]]
    [[ "$output" == *"Failed: 1"* ]]
}

@test "--quick only tests ollama and zen" {
    run rm -f "$MOCK_LOG"
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --quick

    [ "$status" -eq 0 ]
    [[ "$output" == *"ollama/llama3.2:3b"* ]]
    [[ "$output" == *"zen/big-pickle"* ]]
    [[ "$output" == *"zen/claude-opus-5"* ]]
    # deepseek should be absent from output
    [[ "$output" != *"deepseek/deepseek-v4-flash"* ]]
    [[ "$output" == *"Tested: 3"* ]]
    [ ! -e "$MOCK_LOG" ] || grep -qv "deepseek" "$MOCK_LOG"
}

@test "--quick respects LLMFLASK_MODEL_TEST_QUICK_PROVIDERS env" {
    rm -f "$MOCK_LOG"
    run env PATH="$MOCK_BIN:$PATH" \
        LLMFLASK_MODEL_TEST_QUICK_PROVIDERS="deepseek,zen" \
        ./tools/llmflask-model-test --quick

    [ "$status" -eq 0 ]
    [[ "$output" != *"ollama/"* ]]
    [[ "$output" == *"deepseek/deepseek-v4-flash"* ]]
    [[ "$output" == *"zen/big-pickle"* ]]
    [[ "$output" == *"Tested: 3"* ]]
}

@test "positional MODEL filters" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test \
        ollama/llama3.2:3b deepseek/deepseek-v4-flash

    [ "$status" -eq 0 ]
    [[ "$output" == *"ollama/llama3.2:3b"* ]]
    [[ "$output" == *"deepseek/deepseek-v4-flash"* ]]
    # zen models not in output
    [[ "$output" != *"zen/"* ]]
    [[ "$output" == *"Tested: 2"* ]]
}

@test "multiline response is sanitized" {
    cat > "$MOCK_BIN/llmflask" <<'MOCKEOF'
#!/usr/bin/env bash
echo "$@" >> "$MOCK_LOG"
case "$*" in
    *--models*)
        printf "MODELREF\tPROVIDER\tLABEL\tSIZE\tVRAM\n"
        printf "ollama/llama3.2:3b\tollama\tOllama: llama3.2:3b\t1.9G\t4 GB\n"
        ;;
    *--cmd*)
        printf 'Line 1\nLine 2 with\ttab\nLine 3\n'
        ;;
esac
MOCKEOF
    chmod +x "$MOCK_BIN/llmflask"

    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test
    [ "$status" -eq 0 ]
    [[ "$output" == *"Line 1"* ]]
    # no tab or newline in response column
    [[ "$output" != *"	"* ]] || true
    [[ "$output" != *"Line 2"* ]]
}

@test "--show after testing displays cached results" {
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test
    [ "$status" -eq 0 ]

    rm -f "$MOCK_LOG"
    run env PATH="$MOCK_BIN:$PATH" ./tools/llmflask-model-test --show

    [ "$status" -eq 0 ]
    [[ "$output" == *"ollama/llama3.2:3b"*"(cached)"* ]]
    # --show should not call llmflask at all
    [ ! -e "$MOCK_LOG" ]
}

@test "missing llmflask exits 2" {
    mkdir -p "$BATS_TEST_TMPDIR/emptybin"
    run env PATH="$BATS_TEST_TMPDIR/emptybin:/usr/bin:/bin" \
        ./tools/llmflask-model-test
    [ "$status" -eq 2 ]
    [[ "$output" == *"llmflask is not installed"* ]]
}
