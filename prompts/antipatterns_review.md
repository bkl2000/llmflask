# Anti-Pattern Signals

Use these signals while applying `prompts/code_review_principles.md`. They are
search hints, not an exhaustive checklist. Report a match only when it has a
concrete correctness, operability, maintainability, or test-quality impact.

## Failure and state transitions

- Errors are swallowed, stripped of useful context, or caught broadly below a
  real process/request/event-loop boundary.
- A pre-check duplicates the operation's error path and creates a TOCTOU
  window. Environment validation and capability dispatch remain valid uses.
- A multi-step change can leave partial state, destroys before replacement is
  ready, or is unsafe when repeated.
- Cleanup failure replaces the primary error, or cleanup is skipped on timeout,
  cancellation, generator close, signal, or exception.

## Resource and lifecycle hazards

- Files, responses, database connections, subprocesses, threads, containers,
  temporary paths, or archives have no clear owner and deterministic close.
- User- or provider-controlled input is read fully into memory, accumulated,
  retried, logged, or waited on without a relevant bound.
- External calls lack deliberate connect/read/overall timeouts or abandon a
  running resource after cancellation.
- Mutable module state or import-time I/O leaks configuration between requests,
  tests, or callers.

## Architecture and abstraction

- A module or class owns several unrelated policies or reasons to change.
- Procedural code passes a state bag through unrelated functions, or a class is
  only a namespace for stateless helpers.
- Inheritance, factories, protocols, generic registries, or plugin machinery
  exist without multiple real implementations or an invariant they protect.
- Boolean flags, magic strings, or provider-name checks encode an implicit
  capability model that is already diverging between callers.
- A dependency is difficult to replace in tests because construction and use
  happen in the same layer.

## Boundary hazards

- External JSON, form fields, paths, filenames, archive entries, environment
  values, or process results cross into trusted code without validation.
- Path containment checks dereference symbolic links or accept special files at
  an input, mount, output, debug, download, or archive boundary.
- Commands are assembled through `shell=True`, `eval`, or unquoted Bash
  expansion when an argument list or quoted expansion is sufficient.
- Bash pipelines lose the relevant exit status, traps do not preserve cleanup,
  or functions mutate caller globals without `local` or an explicit result.
- Python uses mutable default arguments or manual open/close where a context
  manager owns the lifecycle more reliably.

## Test hazards

- Tests assert cosmetic spacing, punctuation, or private call structure rather
  than a documented output or behavior contract.
- Fixtures or module globals leak mutable state or require test ordering.
- Mocks replace internal helpers instead of HTTP, filesystem, database,
  subprocess, Docker, Ollama, or clock boundaries.
- Assertions prove only that code ran, not that the intended state, error,
  output, cleanup, or idempotent result occurred.
- Only happy paths exist for destructive, streaming, timeout, update, or
  persistence behavior.

## Low-signal hygiene

- Dead or unreachable code and stale compatibility shims have no caller.
- A domain policy is encoded as an unexplained repeated value.
- The same non-trivial pattern appears for the third time without a shared
  boundary. Do not extract two short occurrences solely for DRY.
