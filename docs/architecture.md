# Architecture

## Project Structure

```
llmflask/
├── components/
│   ├── local-ai/          Shell scripts for AI stack setup
│   └── llmflask/           LLMFlask Python application
│       └── src/llmflask/
│           ├── routes/     Flask route handlers
│           ├── services/   External API clients
│           ├── workbench/  Pool workbench modules
│           ├── tui/        Terminal UI
│           ├── static/     Web GUI (JS, CSS)
│           └── templates/  HTML templates
├── sandbox/                Docker Containerfile
├── prompts/                LLM prompt templates
├── samples/                Test data for pool workbench
├── tools/                  Convenience scripts and remote tests
├── tests/                  pytest, BATS, JavaScript tests
└── docs/                   Documentation
```

## Key Components

### LLMFlask Server (`llmflask --server`)

Flask application serving:
- `/api/chat` — Streaming chat endpoint
- `/api/pool` and `/api/pools/...` — Pool workbench endpoints
- `/api/sessions`, `/api/users`, `/api/models`
- Web GUI at `/`

The server binds to `127.0.0.1` by default. Remote access should normally use
an SSH tunnel. An explicit LAN bind through `LLMFLASK_HOST` or `--host` also
requires a comma-separated `LLMFLASK_TRUSTED_HOSTS` allowlist. Unexpected Host
headers receive HTTP 400. State-changing API requests (`POST`, `PUT`, `PATCH`,
and `DELETE`) require `X-LLMFlask-Request: 1` and receive HTTP 403 when the
header is absent or wrong; the bundled clients add it automatically. A browser
Origin that differs from the request scheme, hostname, or port also receives
HTTP 403. These are request-boundary checks, not authentication or tenant
isolation.

### Pool Workbench (`llmflask --usepool`)

Status: experimental Phase 1, implemented and runnable for generated Python
and Bash tasks. It uses the prebuilt `llmflask-sandbox:1` image based on Debian
13 slim; it is not the planned fresh-install test container.

1. **PoolManager** — Creates pool directory, copies input files
2. **ScriptGenerator** — Sends request to LLM, parses response into files
3. **SandboxRunner** — Executes generated code in isolated Docker container
4. **Repair** — Attempts LLM-based repair on failed runs
5. **Orchestrator** — Coordinates the full pipeline

The server-side Workbench API is disabled by default. Operational activation
means making `docker info` succeed for the server account, building the image
with `make install-sandbox`, and starting the server with
`LLMFLASK_WORKBENCH_ENABLED=1`. Every execution uses a new restricted container
with no network and removes it afterward; there is no persistent pool
container to start.

### CLI (`llmflask --cmd`, `llmflask --tui`)

- `--cmd` — Stateless batch queries
- `--tui` — Interactive terminal client
- `pool/result/session/user/reset` — Management subcommands

## Data Flow

```
Pool client → HTTP POST → Flask workbench route
  → PoolManager.create (pool dir)
  → ScriptGenerator (LLM → code)
  → SandboxRunner (Docker execute)
  → Auto-download (client-side result)

TUI/batch with an explicit server → LLMFlask HTTP API
TUI/batch with a direct provider → provider API (no LLMFlask server)
`llmflask result ...` → local downloaded-result directory
```

## Dependencies

- Python 3.12+ with httpx, flask, gunicorn
- Docker Engine (for the sandbox and SearXNG)
- Ollama (for local LLM inference)
