# Code Review — Project Quality Model

Review the requested diff or subsystem against the quality model in
`AGENTS.md`. Correctness and operational impact outrank style. Report only
concrete findings and skip categories with no findings.

For every finding provide:

- file and line;
- severity (`high`, `medium`, `low`) and confidence;
- the violated contract or practical consequence;
- the smallest maintainable fix and the regression test that proves it.

Distinguish an observed defect from a design risk or readability suggestion.
Do not turn heuristic matches into findings without demonstrating impact.

## 1. Contracts and correctness

- Do behavior, inputs, outputs, invariants, ownership, and failure modes agree
  across CLI, HTTP, database, filesystem, process, and provider boundaries?
- Do partial responses, missing fields, interruption, retries, and repeated
  execution have deliberate outcomes?
- Is compatibility preserved unless the change explicitly declares otherwise?

## 2. Simplicity and readability

- Is non-obvious branching or iteration named after its purpose?
- Does nesting reveal a missing boundary, or is it inherent to the operation?
- Would a lookup table or rule set be clearer than a branch chain? Do not
  replace straightforward control flow with data-driven indirection merely to
  satisfy the heuristic.

## 3. Cohesion and composition

- Does each function, class, or module have one coherent reason to change?
- Are dependencies directed from orchestration toward small services rather
  than hidden in globals or imports?
- Prefer pure functions for transformations. Use classes for related state,
  invariants, or resource lifecycles; prefer composition over inheritance and
  flag both forced OO and stateful procedural code.

## 4. Effects and resource lifecycles

- Are file, network, database, subprocess, thread, container, and temporary
  resource lifecycles explicit and deterministic?
- Are work, memory, output, retries, and waits bounded where inputs or external
  services can grow or stall?
- Do timeout, cancellation, cleanup, atomicity, and idempotency work on every
  exit path without hiding the original failure?

## 5. Proportional abstraction

- Apply the Rule of Three: keep the first occurrence local, note the second,
  and extract the third unless the duplication protects clearer boundaries.
- Reject speculative provider/plugin abstractions without current callers or
  concrete capability differences.
- Name domain values and policies; ignore ordinary literals with no hidden
  meaning.

## 6. Verification

- Do tests exercise public contracts and external boundaries instead of
  monkeypatching private helpers?
- Are boundary values, negative paths, partial failure, timeout, cancellation,
  cleanup, and repeated execution covered in proportion to risk?
- Treat coverage as a map of unexamined paths, not a uniform percentage gate.
  A green legacy suite is not evidence for behavior it never asserts.

Use `prompts/antipatterns_review.md` as a focused signal catalogue while
reviewing these dimensions; do not run it as a competing second quality model.
