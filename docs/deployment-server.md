# Server Deployment

## Prerequisites

- Debian/Ubuntu build computer with Python 3.12 or newer
- Docker Engine installed when setting up the local AI stack or Workbench:
  https://docs.docker.com/engine/install/

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

```bash
# Production server (Gunicorn):
~/bin/llmflask --server production --host 0.0.0.0 --port 5000

# Detached:
nohup ~/bin/llmflask --server production > /tmp/llmflask.log 2>&1 &

# Development server (Flask):
~/bin/llmflask --server
```

Developers can alternatively run `llmflask` from `~/.venvs/llmflask`, but a
venv is not needed for normal standalone operation.

## Firewall

Ports 5000 (LLMFlask) and 8071 (SearXNG) should be
accessible where those browser interfaces are needed. Ollama uses port 11434
locally; expose it only when clients are intended to access Ollama directly.

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
