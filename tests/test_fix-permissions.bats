#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

setup() {
  export TEST_DIR="$BATS_TEST_TMPDIR"
}

@test "fix-permissions shows help and exits zero" {
  run ./tools/fix-permissions.sh --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]

  run ./tools/fix-permissions.sh -h
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "fix-permissions restores tracked exec bits from the git index" {
  local repo="$TEST_DIR/gitrepo"
  mkdir -p "$repo/tools"
  printf '#!/usr/bin/env bash\necho hi\n' > "$repo/tools/mytool.sh"
  chmod +x "$repo/tools/mytool.sh"
  git -C "$repo" init -q
  git -C "$repo" add tools/mytool.sh
  git -C "$repo" -c user.email=t@t -c user.name=t commit -qm init

  chmod -x "$repo/tools/mytool.sh"
  [ ! -x "$repo/tools/mytool.sh" ]

  run ./tools/fix-permissions.sh "$repo"
  [ "$status" -eq 0 ]
  [ -x "$repo/tools/mytool.sh" ]

  run ./tools/fix-permissions.sh "$repo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"No permissions to fix."* ]]
}

@test "fix-permissions --check reports and fails on missing bits" {
  local repo="$TEST_DIR/checkrepo"
  mkdir -p "$repo"
  printf '#!/usr/bin/env bash\necho hi\n' > "$repo/tool.sh"
  chmod +x "$repo/tool.sh"
  git -C "$repo" init -q
  git -C "$repo" add tool.sh
  git -C "$repo" -c user.email=t@t -c user.name=t commit -qm init

  chmod -x "$repo/tool.sh"
  run ./tools/fix-permissions.sh --check "$repo"
  [ "$status" -eq 1 ]
  [[ "$output" == *"missing exec bit"* ]]

  run ./tools/fix-permissions.sh "$repo"
  [ "$status" -eq 0 ]
  run ./tools/fix-permissions.sh --check "$repo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"All executable bits are in place."* ]]
}

@test "fix-permissions heuristic restores bits without a git repo" {
  local plain="$TEST_DIR/plain"
  mkdir -p "$plain/tools"
  printf '#!/usr/bin/env bash\necho hi\n' > "$plain/tools/helper.sh"
  chmod -x "$plain/tools/helper.sh"
  printf '#!/usr/bin/env python3\nprint(1)\n' > "$plain/tools/tool.py"
  chmod -x "$plain/tools/tool.py"

  run ./tools/fix-permissions.sh "$plain"
  [ "$status" -eq 0 ]
  [ -x "$plain/tools/helper.sh" ]
  [ -x "$plain/tools/tool.py" ]
}
