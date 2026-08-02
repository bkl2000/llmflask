# Changelog

## 0.2.0 — 2026-08

Local-first security defaults:

- the server now binds to `127.0.0.1` by default;
- Workbench is disabled unless explicitly enabled;
- exact trusted Host validation protects local and configured LAN endpoints;
- state-changing API requests require an intent header and browser Origins
  must match the request endpoint;
- bundled Web, CLI, TUI, batch, pool, and remote-test clients send the header;
- GitHub publication now delegates every path to one authoritative audit.

## 0.1.0 — 2026-08

Initial public source release.

### Features
- **LLMFlask**: Flask server, Curses TUI, Web GUI for local LLM chat
- **Batch mode**: Single-question CLI (`--cmd --text`)
- **Pool Workbench**: Docker-sandboxed code generation (`--usepool`)
- **Auto-download**: Results saved locally after execution
- **CLI Management**: pool, result, session, user, reset commands
- **Convenience scripts**: `llm-models`, `llm-ask`, `llm-pool`
- **Setup targets**: `install-dev`, `install-server`, `install-tools`
- **SearXNG integration**: Privacy-focused web search
- **Standalone build support**: local PyInstaller one-file build for the current
  Linux architecture; no downloadable GitHub binary is included yet
- **Offline client build support**: self-extracting package with an embedded
  pip wheelhouse

### Backend
- PoolManager, SandboxRunner, ScriptGenerator, ArtifactManager, Repair
- Docker sandbox with `--read-only`, `--tmpfs`, timeout cleanup
- SSE streaming for all operations
- Idempotent permission handling (644/755/777)
- Code fence stripping, sys.argv wrapper

### Tests
- Maintainer tree: 485 pytest; public snapshot: 481 passed plus 4 private-only
  checks skipped; both run 96 regular BATS, 4 Docker smoke, 11 remote tests,
  and JavaScript checks
