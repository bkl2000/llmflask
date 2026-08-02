# Server Deployment

## Prerequisites

- Debian/Ubuntu build computer with Python 3.12 or newer
- Docker Engine installed when setting up the local AI stack or Workbench:
  https://docs.docker.com/engine/install/
- A reachable Ollama service with an installed model for local inference, or
  an API key configured on the server account for each selected optional
  OpenAI or DeepSeek provider

## Install

```bash
git clone https://github.com/bkl2000/llmflask.git llmflask
cd llmflask
sudo apt install python3-venv python3-pip
make install-server
make standalone
mkdir -p ~/bin
install -m 0755 \
  components/llmflask/standalone/llmflask-linux-$(uname -m)/llmflask \
  ~/bin/llmflask
```

The standalone binary contains the Web server, TUI, and command modes. It does
not require Python, a venv, or the source checkout at runtime. Ollama, SearXNG,
and the optional Docker sandbox remain separate services.

### Copy to another server

Build on the same Linux architecture as the destination, then copy the single
binary:

```bash
LLMFLASK_BINARY="components/llmflask/standalone/llmflask-linux-$(uname -m)/llmflask"
ssh user@server 'mkdir -p ~/bin'
scp "$LLMFLASK_BINARY" user@server:~/bin/llmflask
ssh user@server 'chmod 0755 ~/bin/llmflask && ~/bin/llmflask --version'
```

Set `OLLAMA_URL=http://GPU_SERVER:11434` when Ollama runs on another computer.
Set `SEARXNG_URL` in the same way when search uses a remote SearXNG instance.

## Start

The safe default listens only on `127.0.0.1`:

```bash
# Production server (Gunicorn, loopback only):
~/bin/llmflask --server production --port 5000

# Detached:
nohup ~/bin/llmflask --server production > /tmp/llmflask.log 2>&1 &

# Development server (Flask):
~/bin/llmflask --server
```

Developers can alternatively run `llmflask` from `~/.venvs/llmflask`, but a
venv is not needed for normal standalone operation.

## Recommended remote access: SSH tunnel

Keep the server on loopback. On the trusted client, forward a local port and
leave the SSH command running:

```bash
ssh -N -L 60010:127.0.0.1:5000 user@LLMFLASK_SERVER
```

Open <http://127.0.0.1:60010>, or use the client in another terminal:

```bash
llmflask --models --host 127.0.0.1 --port 60010
llmflask --tui --host 127.0.0.1 --port 60010
```

SSH provides encryption and authentication. LLMFlask does not.

## Protected-LAN opt-in

Only when every client on the reachable network is trusted, bind to the
server's LAN address and list every hostname or IP address clients will use:

```bash
LLMFLASK_HOST=192.0.2.20 \
LLMFLASK_TRUSTED_HOSTS=192.0.2.20,llmflask.internal \
  ~/bin/llmflask --server production --port 5000

# Equivalent explicit bind flag:
LLMFLASK_TRUSTED_HOSTS=192.0.2.20,llmflask.internal \
  ~/bin/llmflask --server production --host 192.0.2.20 --port 5000
```

`LLMFLASK_TRUSTED_HOSTS` is comma-separated. Each entry is one exact hostname
or IP address without a scheme, path, port, or wildcard. A rejected Host header
returns HTTP 400. The allowlist is not authentication, so firewall port 5000
to the trusted clients only. Do not expose LLMFlask directly to the internet.

Custom HTTP clients must send `X-LLMFlask-Request: 1` with all `POST`, `PUT`,
`PATCH`, and `DELETE` requests. The same-origin Web UI and bundled CLI add the
header automatically; a missing or wrong value returns HTTP 403.
Browser requests whose `Origin` does not match the request scheme, hostname,
and port also return HTTP 403.

## Optional Workbench

Workbench is disabled by default. Enable it only on a server whose account can
use Docker:

```bash
docker info
make install-sandbox
LLMFLASK_WORKBENCH_ENABLED=1 ~/bin/llmflask --server production
```

The setting must be present each time that server starts. A disabled Workbench
response means the server must be restarted with the opt-in after Docker and
the sandbox image are ready.

## Firewall

The loopback default requires no inbound LLMFlask firewall opening. For the
protected-LAN opt-in, permit port 5000 only from trusted clients. SearXNG uses
port 8071 and Ollama uses port 11434; expose either only when specifically
required and restricted to its intended clients.

## Update

```bash
git pull
make install-server
make standalone
install -m 0755 \
  components/llmflask/standalone/llmflask-linux-$(uname -m)/llmflask \
  ~/bin/llmflask
pkill -f llmflask
~/bin/llmflask --server production
```

For a server that only received the binary, build the update on a compatible
computer and copy it again with `scp`.

## Ollama

Ollama runs as a systemd service on port 11434. Models are downloaded on first use by `make install-ai`.
