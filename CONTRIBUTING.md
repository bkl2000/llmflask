# Contributing

## Tests

Run the full test suite before submitting changes:

```bash
make setup-test-env
make test
```

Tests include pytest (Python), BATS (Shell), and JavaScript syntax checks.
Write tests for new features. Mock external dependencies (httpx, docker, ollama).

## Code Style

- Python: type hints, snake_case, no long if/elif chains (use dict dispatch)
- Bash: `#!/usr/bin/env bash`, `set -euo pipefail`, pass `bash -n` syntax check
- JavaScript: pass `node --check`
- All scripts must have `--help`/`-h` before any network or dependency checks
- Operations must be idempotent — safe to run multiple times

## Pull Requests

1. Run `make test` — must pass
2. Keep commits focused and atomic
3. Update README.md and the relevant public documentation for user-facing changes
4. Stage only intended files and review `git diff --cached` before committing
5. Agents and automation must not commit or push without an explicit
   maintainer request

## Questions

Open an issue on GitHub.
