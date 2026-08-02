# Security Policy

## Reporting a Vulnerability

Do not include vulnerability details, credentials, or private data in a public
issue. Use GitHub's private vulnerability reporting when it is enabled for the
repository. If that feature is unavailable, contact the maintainer through the
public GitHub profile and request a private reporting channel.

## Security Model

This project is designed for locally managed AI services. The server listens
on loopback by default. Do not expose its ports to the internet without a
separate authentication layer, firewall rules, TLS termination, and an
explicit deployment review.

LLMFlask intentionally does not authenticate users. The `--user` value and Web
GUI profile selector organize chats but do not enforce access control. Every
client that can reach the server must therefore be trusted, including for chat
and Workbench pool management.

The supported deployment is a single trusted machine, an SSH tunnel, or an
explicitly configured protected network whose clients are all trusted. An SSH
tunnel is the recommended remote-access path because LLMFlask itself provides
no transport encryption or authentication. Internet-facing or untrusted
multi-user use requires a separate authentication and authorization layer,
TLS termination or a reviewed reverse proxy, firewall rules, and a deployment
threat model. These controls are not provided by the current application.

For a protected LAN, start with `llmflask --server production --listen 0.0.0.0`
and connect using the server's real IP address. IP-literal Host headers are
accepted on wildcard IPv4 or IPv6 binds; unrelated DNS names are not. A specific
`--listen` address trusts only that exact address or hostname. Add an intentional
DNS alias with repeatable `--trusted-host HOST`. `LLMFLASK_HOST` and the
comma-separated `LLMFLASK_TRUSTED_HOSTS` remain advanced service/automation
equivalents. This Host-header allowlist limits unexpected routing; it is not
user authentication. State-changing API requests also require
`X-LLMFlask-Request: 1`. The same-origin Web UI and bundled CLI add it
automatically. When a browser sends an `Origin`, it must match the request's
scheme, hostname, and port. These checks reduce browser-based request abuse but
do not turn an untrusted network into a supported deployment.

- **API keys**: Never committed. `llmflask --configure-api-keys` stores them in
  `${XDG_CONFIG_HOME:-$HOME/.config}/llmflask/api.txt` with restricted
  permissions. `LLMFLASK_API_KEYS_FILE`, individual environment variables, and
  the legacy gitignored `./api.txt` remain supported.
- **Chat data**: Stored locally in SQLite (`~/.local/share/llmflask/chat.db`).
- **Pool sandbox**: Disabled by default and enabled explicitly with
  `LLMFLASK_WORKBENCH_ENABLED=1`. Its Docker containers run with
  `--network none`, `--read-only`, and `--cap-drop ALL`.
- **Uploads**: Workbench request, per-file, and file-count limits are enabled
  by default and can be adjusted with the documented `LLMFLASK_MAX_UPLOAD_*`
  environment variables.
- **No telemetry**: LLMFlask does not send usage telemetry.
- **External providers**: Prompts and context are sent to OpenAI or DeepSeek
  only when a model from that provider is deliberately selected.
- **Web search**: Search terms are sent to the configured SearXNG instance and
  may be forwarded by that instance to its enabled search engines.

## Known Limitations

- The project has not completed an adversarial threat model or an independent
  security audit. Its AI-assisted Codex review is not a substitute for either.
- Loopback is the default bind. Operators can deliberately select a LAN
  address, but must also configure trusted hosts and firewall access.
- User profiles are not tenants. Any client that can reach the server can
  select another profile and manage its chats or Workbench pools.
- Host validation and the `X-LLMFlask-Request` request-intent header are not
  authentication, authorization, CSRF tokens, or tenant isolation.
- Workbench containers use network isolation, a read-only root filesystem,
  dropped capabilities, resource limits, and an unprivileged user. These
  controls reduce risk but cannot eliminate Docker, kernel, generated-code, or
  host-filesystem risks.
- Output-artifact validation includes post-run limits. A generated process can
  consume space in its writable host-mounted output area before the final
  total-size validation rejects the result.

Treat this as a local-first project for trusted users, not as a hardened
internet service.

## Dependencies

- Docker Engine (external prerequisite)
- Python 3.12+ (system or venv)
- Ollama (local installation)
- SearXNG (optional, Docker)
