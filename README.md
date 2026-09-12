# LLMFlask

> A practical Linux toolkit for chatting with local Ollama models or optional
> OpenAI and DeepSeek APIs—from a browser, a terminal UI, or a single command.

> [!WARNING]
> LLMFlask 0.3.0 is intended for trusted local users and protected networks.
> It has no authentication, authorization, or tenant isolation. The server
> listens on loopback by default; keep it local, reach it through an SSH
> tunnel, or explicitly configure a protected LAN. Do not expose it directly
> to the internet or to untrusted users. See [Security](SECURITY.md).

Current development version: **0.3.0**. Versions change only for intentional
releases, not for each pull, commit, or GitHub snapshot.

## What LLMFlask is

LLMFlask is not an inference engine, model runtime, or multi-user AI platform.
It uses existing services — local Ollama or optional OpenAI and DeepSeek APIs.

Its focus is simple deployment and consistent operation: copy one standalone
Linux binary to a compatible system and use the same application through a Web
interface, a terminal UI, or command-line commands. The target system does not
need Python, a virtual environment, or a source checkout.

Larger platforms provide authentication, team management, RAG systems, and agent
marketplaces. LLMFlask deliberately stays smaller and easier to understand. It is
intended for individual users, administrators, and trusted internal environments
that want a practical interface to existing LLM services without deploying a
complete AI platform.

## Why LLMFlask?

`ollama run` is the simplest choice when you are sitting at the model computer.
LLMFlask adds a shared Web, terminal, and command-line interface when the model
runs elsewhere on the network, several clients need access, or local and
optional external providers should use the same chat workflow.

```text
Laptop / server / VPS                 GPU computer
┌────────────────────┐               ┌───────────────┐
│      LLMFlask      │   HTTP/API    │    Ollama     │
│                    │ ────────────> │               │
│ Web, TUI, and CLI  │               │ Local models  │
└────────────────────┘               └───────────────┘
```

A practical administrator use case is to operate an approved Ollama or other
LLM service on controlled infrastructure and distribute the standalone
LLMFlask executable to trusted remote Linux computers. The remote systems do
not need Python, a virtual environment, or a source checkout, while inference
and model management stay on infrastructure selected by the administrator.
This can make an authorized internal model service easier to use consistently
without installing a complete AI stack on every client.

LLMFlask is not a way to bypass organizational restrictions on AI software,
data processing, or external providers. Administrators must obtain the
required approval and configure models, network access, logging, and data
handling according to their organization's policies.

The standalone build packages the complete application as one executable. Copy
that binary to a compatible Linux computer with `scp` and use it as a Web
server, Curses frontend, or command-line client without installing Python, a
venv, or the source repository there. All three interfaces share the same
provider, configuration, conversation, and session logic.

Ollama and optional services are not embedded in the binary. They can run on
the same computer or elsewhere on the network. Docker is needed on a LLMFlask
server only when it should provide optional components such as SearXNG or the
isolated code workbench.

This keeps the interface independent from the inference hardware without
turning LLMFlask into a full AI platform. The design goal is a small,
understandable LLM application that can be copied, installed, and operated like
a normal Unix program.

The surrounding setup scripts install and update the local AI stack
idempotently: Ollama, suitable local models, SearXNG, OpenCode, and the LLMFlask
sandbox. Docker Engine and Docker Compose remain external prerequisites for
that full local stack, but not for a copied standalone client or a server that
does not provide Docker-backed features.

## AI-assisted development

LLMFlask is an AI-assisted project, an approach sometimes described as vibe
coding. It was developed iteratively with OpenCode using DeepSeek V4, followed
by risk-based review and refinement with Codex. The maintainer defines the
requirements, reviews proposed changes, and manually approves commits and
publication. The repository includes automated Python, shell, JavaScript,
Docker sandbox, and remote integration tests.

AI-assisted implementation and review do not guarantee correctness and are
not an independent human or third-party security audit. Users should review
the code and documented limitations for their own environment. Detailed
design decisions, review findings, and test evidence are retained in the
project history. LLMFlask is independent and is not affiliated with Ollama,
OpenAI, or DeepSeek.

## Three ways to use LLMFlask

| Interface | Best for | Start it |
|---|---|---|
| **Web GUI** | Comfortable chats in a browser | `llmflask --server`, then open `http://localhost:5000` |
| **TUI** | Interactive chats entirely in a terminal | `llmflask --tui` |
| **CMD** | One-off questions, pipes, and shell scripts | Run `llmflask --models`, then pass a listed `MODELREF` to `--model` |

All three interfaces can use the same models. Local models run through Ollama
on your own machine. OpenAI and DeepSeek are optional and are enabled only when
you provide an API key. Provider API usage may incur charges from that provider.

## Before the first start

Choose the backend that will answer your requests:

- **Local models:** Ollama must be reachable and must contain at least one
  model. LLMFlask uses `http://127.0.0.1:11434` by default. The
  recommended `make all` command below installs Ollama and a small starter
  model, then enables and starts the Ollama system service.
- **Ollama on another computer:** the client does not need a local Ollama
  installation, but the remote endpoint must be reachable. Set
  `OLLAMA_URL=http://OLLAMA_SERVER:11434` when starting LLMFlask.
- **Ollama Cloud through the local daemon:** run `ollama signin`, then
  `ollama pull MODEL:cloud` for your chosen model on the Ollama host. Every
  model in that daemon's `/api/tags` appears automatically alongside local
  and remote models; cloud tags use the same Ollama chat endpoint.
- **OpenAI or DeepSeek:** Ollama is not required for direct provider access,
  but the selected provider requires its own API key. After installing
  LLMFlask, run `~/bin/llmflask --configure-api-keys`; the helper stores keys
  in `~/.config/llmflask/api.txt` with restricted permissions.

For a local Ollama installation, these checks must succeed before local chats
can work:

```bash
systemctl is-active ollama
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null
ollama list
```

After installing LLMFlask, run `~/bin/llmflask --models` to confirm the models
it can actually use. See [Remote servers and API keys](#remote-servers-and-api-keys)
for the detailed client/server combinations and where credentials belong.

## Quick start on Linux

The minimum supported first-install path is Debian 13 or newer, Ubuntu 24.04
or newer, and Linux Mint 22 or newer with `systemd` and Python 3.12 or newer.
These minimums are not an upper-version allowlist: later apt-based releases,
such as a future Debian 14, are accepted when the required commands and
capabilities are present. A release is described as *tested* only after the
complete `make all` flow has run on a clean installation of that release.

Debian 12 ships Python 3.11, so the clone-and-build path is not supported or
tested there out of the box. This does not mean the application cannot run on
Debian 12: a standalone binary built on a compatible Linux system with the
same CPU architecture may work without Python on the destination. The build
computer also needs `sudo`, internet access, and enough free disk space for
Python packages and the selected Ollama model.

Python 3.11 may run parts of the code, but it is not sufficient for the
out-of-box installation: the package metadata and built distributions require
Python 3.12 or newer, so `pip` rejects Python 3.11 before installation, and the
project does not run its compatibility suite on 3.11.

Install the basic system tools first:

```bash
sudo apt update
sudo apt install -y ca-certificates git curl make tar python3 python3-venv python3-pip
python3 --version
```

If the reported Python is older than 3.12, stop and use a supported build host;
do not replace the distribution's system Python manually. The prerequisite
checker also stops before installation and prints a copyable repair command
when an apt package, Python venv support, sudo, or systemd is missing.
Compatibility checks use those capabilities instead of rejecting an otherwise
usable system merely because its distribution version is newer than the ones
already tested.

An NVIDIA GPU is optional. Without `nvidia-smi`, the model installer uses a
conservative 8 GB selection; local inference can still run on the CPU, but it
will usually be slower. With less than 8 GB of GPU memory the installer
automatically selects small models (`ollama/llama3.2:3b`,
`ollama/qwen3:4b-instruct-2507-q4_K_M`). The pinned Qwen model is the Q4_K_M
build of Qwen3-4B-Instruct-2507 (about 2.5 GB). At 8 GB the normal Qwen choice
remains `ollama/qwen3:8b`; a 12 GB card also adds `ollama/qwen3:14b` and
`ollama/gemma4:12b` as capacity-oriented quality options. The optional
`qwen3:32b` selection requires at least 24 GB for full-GPU use.

Clone the public GitHub repository:

```bash
git clone https://github.com/bkl2000/llmflask.git llmflask
cd llmflask
make all
```

`make all` is the beginner-safe local installation. It checks prerequisites,
installs and starts Ollama with `llama3.2:3b`, builds the standalone for the
current architecture, installs it as `~/bin/llmflask`, and installs the
convenience commands. It does not require Docker. When it finishes, run the
printed verification and start commands:

An existing `/usr/share/ollama` symlink to another local filesystem is
preserved and used for model data. Set `OLLAMA_REAL_DIR` only when the installer
should require that symlink to resolve to one specific configured target.

```bash
systemctl is-active ollama
ollama list
~/bin/llmflask --models
~/bin/llmflask --server production
```

Then open <http://localhost:5000>. Keep the server command running. OpenAI and
DeepSeek remain optional; use `~/bin/llmflask --configure-api-keys` only when
you intend to select one of those providers.

After the GitHub repository is public, a fresh machine can instead download,
inspect, and run the idempotent installer:

```bash
curl -fLO https://raw.githubusercontent.com/bkl2000/llmflask/main/tools/install-public.sh
less install-public.sh
bash install-public.sh --directory "$PWD/llmflask"
```

Add `--full-ai` for the complete local AI stack. The default uses the minimal
Ollama model and still builds the LLMFlask venv, standalone binary, and tools.

For SearXNG, OpenCode, and the Workbench sandbox, install Docker Engine and its
Compose plugin separately by following the
[official Docker instructions](https://docs.docker.com/engine/install/). Make
Docker usable by the normal account, then install the complete stack:

```bash
docker info
docker compose version
make install-server
```

`make install-server` includes `make install-ai`, the central full-stack
installer. The scripts are idempotent, so running the command again updates or
verifies the installation while preserving models and persistent data. It
reuses the LLMFlask environment and binary already created by `make all`.

To rebuild and reinstall only the standalone after source changes:

```bash
make standalone
install -m 0755 \
  components/llmflask/standalone/llmflask-linux-$(uname -m)/llmflask \
  ~/bin/llmflask
```

No venv activation is needed when using the standalone binary.
`make install-server` requires the Docker checks above to succeed and downloads
software from Ollama, SearXNG, OpenCode, PyPI, and their image registries. The
venv it creates remains useful for rebuilding LLMFlask and for development.

The server listens on `127.0.0.1` by default, matching the local client
default. This is the safest normal setup: only programs on the same computer
can connect. For another computer, prefer the SSH-tunnel flow in
[Remote servers and API keys](#remote-servers-and-api-keys). A protected-LAN
deployment requires an explicit bind address and trusted Host allowlist.

LLMFlask deliberately has no authentication layer. Names selected with
`--user` are organizational chat profiles, not security boundaries: anyone
who can reach the server can technically select another profile and manage its
chats or pools. Use the server only with trusted users on a protected network
or through SSH port forwarding.

### Confirm the installation

In a second terminal, ask the running standalone server which models it can
use:

```bash
~/bin/llmflask --version
~/bin/llmflask --models --host 127.0.0.1
```

Copy a value from the `MODELREF` column exactly as printed and use it for
`--model`. The beginner-safe `make all` path installs
`ollama/llama3.2:3b`. The optional full-stack installer may add other models
according to available GPU memory. The `--models` table is authoritative and
shows each installed model's size and recommended VRAM tier.

Model discovery depends on where the models and API keys live:

```bash
# Directly query local Ollama plus remote providers configured on this client
llmflask --models

# Query a running LLMFlask server through an SSH tunnel on local port 60010
llmflask --models --host 127.0.0.1 --port 60010

# Query one remote provider directly; its API key must be configured locally
llmflask --models --provider deepseek
llmflask --models --provider zen
```

The Web GUI and TUI show an interactive model selector, so they do not take a
startup `--model` option.

## First conversations

### Web GUI

Keep `llmflask --server` running and visit <http://localhost:5000>. Select a
model, create a chat, and send a message. Chats are stored by default in
`~/.local/share/llmflask/chat.db`.

### Terminal UI

Start the TUI with automatic backend selection:

```bash
llmflask --tui --user alice
```

This uses a running local LLMFlask server first, then falls back to the only
configured OpenAI or DeepSeek provider. If both remote providers are
configured, select one explicitly with `--provider deepseek` or
`--provider openai`. To connect to a particular server, give its address:

```bash
llmflask --tui --host 127.0.0.1 --user alice
```

Useful keys include `Ctrl+N` for a new chat, `Ctrl+E` to export Markdown,
`Ctrl+S` to toggle search, `Ctrl+P` to change models, and `Tab` to move between
the chat and session list. Run with `--tui-trace` only when debugging; tracing
is off by default and writes under `/tmp`.

### Command mode

Ask one question and stream the answer to the terminal:

```bash
llmflask --cmd --text "Explain why local LLMs are useful" \
  --model ollama/llama3.2:3b
```

Without `--host` or `--port`, CMD talks directly to Ollama or the selected
remote provider on the current machine. Add an explicit server target to route
the request through LLMFlask instead:

```bash
llmflask --cmd --text "Summarize this in three points" \
  --model ollama/llama3.2:3b --host 127.0.0.1 --port 60010

echo "Explain shell pipelines" | \
  llmflask --cmd --model ollama/llama3.2:3b --output answer.md
```

Use `--session ID --user NAME` if a CMD answer should be stored in a chat that
is also visible in the GUI and TUI.

### Convenience commands

`make install-tools` copies short wrappers to `~/bin`. They share the
`LLMFLASK_HOST`, `LLMFLASK_PORT`, `LLMFLASK_USER`, and `LLMFLASK_MODEL`
defaults where applicable:

```bash
llm-chat --user alice
llm-models
llm-ask --model ollama/llama3.2:3b "Summarize this directory layout"
llm-pool --model ollama/llama3.2:3b --file data.csv --text "Analyze the data"
llm-pools list
llm-results list
llm-sessions --user alice list

# Direct batch query with local defaults (edit script to set DEFAULT_MODEL etc.)
llmflaskcmd "What is Python?"
llmflaskcmd --model deepseek/deepseek-chat --provider deepseek "Hello"
# Run a downloaded pool result locally (auto-runs setup.sh + run.sh)
llm-runresult myresult
```

`llm-pools` also exposes `show`, `run`, `path`, `pack`, `debug`, and explicit
`remove` actions. `llm-results` supports `inspect`, `run`, and `remove`, while
`llm-sessions` supports `remove`. Pass a specific name or ID, or the explicit
value `all`, to a removal action.

`llmflask-model-test` runs "Answer only with OK." against every available model
and caches the results. Subsequent runs skip already-tested models; use
`--refresh` to retest. Use each command's `--help` output for its
complete syntax.

## Search and code workbench

SearXNG provides optional privacy-focused web search on port 8071. In the GUI
or TUI, enable search only when a question benefits from current web results.

### Pool status and activation

The pool workbench is an experimental but runnable Phase 1 feature. It is not
merely a future design: the current implementation can generate and execute
Python or Bash tasks, preserve server-side pools, and download results. Its
Docker runtime uses the project's Debian 13 slim sandbox image. It is not a
general-purpose development container: execution has no network, no
interactive shell, a read-only root filesystem, fixed resource limits, and
only the packages and tools already built into the image.

`make all` does not install or activate the pool sandbox. Enable it on the
computer that runs the LLMFlask server:

```bash
# Docker Engine must already be installed and usable by this account.
docker info

# Build or update the short-lived pool runtime image.
make install-sandbox
docker image inspect llmflask-sandbox:1 >/dev/null

# Workbench is opt-in. Enable it only for this server process.
LLMFLASK_WORKBENCH_ENABLED=1 ~/bin/llmflask --server production
```

There is no persistent pool container to start. Each pool execution creates a
hardened temporary container and removes it afterward. The Workbench API is
disabled unless `LLMFLASK_WORKBENCH_ENABLED=1` is present when the server
starts. Remove the setting and restart the server to disable it again.

On a remote installation, build the sandbox image and start LLMFlask on the
server. The client needs only LLMFlask. After opening the recommended SSH
tunnel on local port 60010, select that forwarded endpoint explicitly:

```bash
llmflask --models --host 127.0.0.1 --port 60010
llmflask --usepool --host 127.0.0.1 --port 60010 \
  --model MODELREF --file data.csv --text "Calculate useful statistics"
```

Use a `MODELREF` copied from the server's `--models` output. Local Ollama or
optional provider keys must be available to the server, while downloaded pool
results are stored on the client under `~/llmflask-results/` by default.

The pool workbench asks a model to create files, runs generated code inside the
hardened Docker sandbox, and downloads the result to `~/llmflask-results/`.
It requires a running LLMFlask server, a model available to that server, a
working Docker daemon, and the sandbox image built by `make install-server` or
`make install-sandbox`:

```bash
llmflask --usepool --text "Create a Python log analyzer" \
  --model ollama/qwen3:8b

llmflask --usepool --file data.csv --text "Calculate useful statistics" \
  --model ollama/qwen3:8b

llmflask result list
llmflask result inspect RESULT_NAME
```

`--usepool` and `llmflask pool run POOL_NAME` always require an explicit
`--model MODELREF`; there is no hidden default. Successful commands print the
exact timestamped `RESULT_NAME` to use with `result inspect` or `result run`.

Generated code should still be reviewed before you trust or reuse it. Run
`llmflask --help` for all pool, result, session, and user commands.

Current real-Docker smoke coverage verifies Python execution, Bash execution,
the read-only root filesystem, and cleanup after a timeout. Broader toolchains,
additional runtime languages, interactive pool access, and host-level disk
quotas remain future work.

Workbench uploads default to 512 MiB per request, 256 MiB per file, and 1,000
files. Override these limits with `LLMFLASK_MAX_UPLOAD_BYTES`,
`LLMFLASK_MAX_UPLOAD_FILE_BYTES`, and `LLMFLASK_MAX_UPLOAD_FILES`. Persistent
server-side pool archives default to the LLMFlask data directory;
`LLMFLASK_POOL_ARCHIVE_ROOT` selects another controlled location.

Sandbox output defaults to 1,000,000 characters each for stdout and stderr,
at most 20 output artifacts, and 100,000,000 bytes per artifact. Configure
these with `LLMFLASK_SANDBOX_MAX_STDOUT`, `LLMFLASK_SANDBOX_MAX_STDERR`,
`LLMFLASK_SANDBOX_MAX_ARTIFACTS`, and
`LLMFLASK_SANDBOX_MAX_ARTIFACT_BYTES`. CLI uploads and result downloads are
streamed through files so these potentially large payloads are not accumulated
in client memory.

## Remote servers and API keys

The standalone executable is the recommended runtime for both clients and
servers. The connection mode determines where Ollama must run and where an API
key must be configured:

| Connection mode | How to select it | Where the backend runs | Where an API key belongs |
|---|---|---|---|
| Direct local Ollama | Omit `--host`, `--port`, and `--provider` | Ollama on the current computer | No key |
| Direct remote Ollama | Set `OLLAMA_URL=http://OLLAMA_SERVER:11434` | Ollama on the named computer | No key |
| LLMFlask server | After an SSH tunnel, add `--host 127.0.0.1 --port 60010` | The server selects Ollama or a remote provider | On the server account, only for OpenAI/DeepSeek |
| Web GUI | Start `llmflask --server` | The server selects Ollama or a remote provider | On the server account, only for OpenAI/DeepSeek |
| Direct OpenAI/DeepSeek | Add `--provider openai` or `--provider deepseek` | The selected provider | On the client account |

`--usepool` and the `pool` commands always use a running LLMFlask server.
Direct OpenAI/DeepSeek providers cannot be combined with `--host` or `--port`.
For the TUI, omitting both the server target and `--provider` first tries a
local LLMFlask server. If none is running and exactly one remote provider key
is configured, the TUI selects that provider directly.

### Copy the standalone to a client or server

Build once per Linux architecture and copy the result only to machines of the
same architecture:

```bash
make standalone
LLMFLASK_BINARY="components/llmflask/standalone/llmflask-linux-$(uname -m)/llmflask"
ssh user@server 'mkdir -p ~/bin'
scp "$LLMFLASK_BINARY" user@server:~/bin/llmflask
ssh user@server 'chmod 0755 ~/bin/llmflask && ~/bin/llmflask --version'
```

An `x86_64` binary must not be copied to an `aarch64` computer or vice versa.
The destination does not need Python, a venv, or the repository, but it does
need network access to Ollama, a LLMFlask server, or a selected external
provider.

For example, run the copied executable as a loopback-only server in front of
Ollama on a separate GPU computer:

```bash
# On the LLMFlask server
OLLAMA_URL=http://OLLAMA_SERVER:11434 ~/bin/llmflask --server production
```

The recommended remote path is an SSH tunnel. Keep the server on its default
loopback address, start this command on the trusted client, and leave it
running:

```bash
ssh -N -L 60010:127.0.0.1:5000 user@LLMFLASK_SERVER

# In another client terminal
~/bin/llmflask --models --host 127.0.0.1 --port 60010
~/bin/llmflask --tui --host 127.0.0.1 --port 60010 --user alice
```

The Web GUI is then available at <http://127.0.0.1:60010>. SSH supplies the
encrypted and authenticated transport that LLMFlask itself does not provide.

For a protected LAN whose clients are all trusted, the simplest command listens
on all local interfaces. Connect with the server's real IP address, which
`hostname -I` prints; do not enter `0.0.0.0` in a browser:

```bash
~/bin/llmflask --server production --listen 0.0.0.0 --port 5000
hostname -I
```

Bind to one address when preferred. Its exact IP is trusted automatically. Add
each intentional DNS alias with a repeatable option:

```bash
~/bin/llmflask --server production --listen 192.0.2.20 --port 5000
~/bin/llmflask --server production --listen 192.0.2.20 --port 5000 \
  --trusted-host llmflask.internal
```

The trusted-Host check rejects unexpected HTTP `Host` headers; it does not
authenticate users. Entries are exact hostnames or IP addresses without a URL
scheme, path, port, or wildcard. A rejection includes the exact restart command
with `--trusted-host`. `LLMFLASK_HOST` and comma-separated
`LLMFLASK_TRUSTED_HOSTS` remain advanced service/automation settings; server-side
`--host` is a temporary compatibility alias for `--listen`. Keep firewall access
limited to the trusted LAN.

The copied server needs Docker only if it should run the Workbench sandbox. If
SearXNG also runs elsewhere, set `SEARXNG_URL` on the server. LLMFlask has no
authentication or tenant isolation, so do not expose either LLMFlask or Ollama
directly to an untrusted network.

As an alternative, `make client-tgz` creates an offline Python client archive.
That archive includes its wheelhouse and installs without internet access, but
requires Python 3.12 or newer on the destination. See
[Server deployment](docs/deployment-server.md) and
[Team deployment](docs/deployment-team.md) for production startup, SSH tunnels,
and multi-user access.

### Configure optional OpenAI and DeepSeek keys

API keys are not needed for Ollama. LLMFlask supports `OPENAI_API_KEY` and
`DEEPSEEK_API_KEY` only for the corresponding optional providers. Configure
only the providers you intend to use:

```bash
~/bin/llmflask --configure-api-keys
```

If `llmflask` is already in your `PATH`, the shorter
`llmflask --configure-api-keys` works as well. The helper:

1. creates `~/.config/llmflask/api.txt` if it does not exist;
2. protects the directory with permissions `700` and the file with `600`;
3. opens the file in `$VISUAL`, `$EDITOR`, or `vi`.

Add a key after the matching `=` sign, then save and close the editor. Leave an
unused provider empty or remove its line:

```text
# Add only the providers you use. These are placeholders, not real keys.
OPENAI_API_KEY=replace-with-your-openai-key
DEEPSEEK_API_KEY=replace-with-your-deepseek-key
```

For example, use Nano for this invocation with
`EDITOR=nano ~/bin/llmflask --configure-api-keys` if Nano is installed. The
helper safely reopens the same file and never replaces its contents. It does
not send or test a key; a key is used only when you select that provider.

No shell-profile entry or permanent `export` is needed. Never commit API keys.
Run the helper on the client account for direct CMD/TUI provider access. For
the Web GUI or any client using `--host`, run it on the server as the account
that starts `llmflask --server`; clients do not receive the server's keys.

Direct provider examples:

```bash
llmflask --models --provider deepseek
llmflask --tui --provider deepseek --user alice
llmflask --cmd --provider openai --model gpt-4.1-mini \
  --text "Give me a concise Linux checklist"
```

Advanced overrides remain available: `XDG_CONFIG_HOME` changes the base
configuration directory, and `LLMFLASK_API_KEYS_FILE` selects a completely
custom key file. Without either override, the path is
`~/.config/llmflask/api.txt`. Existing installations with `./api.txt` continue
to work as a compatibility fallback. A directly set `OPENAI_API_KEY` or
`DEEPSEEK_API_KEY` takes precedence over the corresponding file entry.

OpenAI-compatible remote providers can be replaced with
`${XDG_CONFIG_HOME:-~/.config}/llmflask/providers.json`. The file contains a
top-level `providers` list; each entry requires non-empty `name`, `label`, and
`base_url` strings. Names use letters, digits, `_`, or `-`; `api_style` is
currently `"openai"` only. `requires_auth` defaults to `true`; authenticated
entries also need an `api_key_name` ending in `_API_KEY`. A user file replaces
the bundled provider list; invalid files produce a warning and fall back to
the bundled defaults.

Read-only team users keep their checkout current with `git pull`. Repository
ACLs intentionally prevent them from pushing while preserving normal SSH login
and port forwarding.

## Common startup problems

- **`No models found`:** confirm `ollama list` and the Ollama system service
  locally, or open the documented SSH tunnel and query it with
  `--host 127.0.0.1 --port 60010`. For a remote provider, confirm its API key
  and network access.
- **`No server at ...`:** start `llmflask --server` on the target machine and
  check the host, port, firewall, or SSH tunnel.
- **Docker permission or daemon errors:** make `docker info` work as the normal
  user before running the installer or Workbench.
- **`Workbench is disabled`:** run `docker info`, build the sandbox with
  `make install-sandbox`, then restart the server with
  `LLMFLASK_WORKBENCH_ENABLED=1`.
- **`Host` rejected with HTTP 400:** connect through the default loopback/SSH
  tunnel flow, or add the exact client-facing hostname or IP address to the
  server's comma-separated `LLMFLASK_TRUSTED_HOSTS` value and restart it.
- **`X-LLMFlask-Request` rejected with HTTP 403:** the same-origin Web UI and
  bundled CLI add `X-LLMFlask-Request: 1` automatically. A custom HTTP client
  must send that header on every `POST`, `PUT`, `PATCH`, and `DELETE` request.
  The header is a request-intent check, not authentication.
- **`Origin` rejected with HTTP 403:** use the bundled UI from the same scheme,
  hostname, and port as the request. A reverse proxy must preserve a matching
  external Host and Origin and requires a separate security review.
- **`OPENAI_API_KEY` or `DEEPSEEK_API_KEY` missing:** configure the key on the
  machine that performs the direct request with
  `~/bin/llmflask --configure-api-keys`, or run the helper as the server account
  for server-backed requests.
- **PDF export unavailable:** install `pandoc`; Markdown export and normal chat
  operation do not require it.

## Updating and testing

Update an installation by pulling the repository and rerunning the idempotent
installer, then replace the standalone binary:

```bash
git pull
make install-server
make standalone
install -m 0755 \
  components/llmflask/standalone/llmflask-linux-$(uname -m)/llmflask \
  ~/bin/llmflask
```

For copied installations, repeat the `scp` step instead of cloning the
repository on every destination.

Every run checks Ollama and all selected model tags, pulls the current SearXNG
image, updates OpenCode and the Python environment, and rebuilds the sandbox
with Docker's cache and a refreshed base image. This can download data even
when the commands were already installed. Existing Ollama models, SearXNG
bind-mounted settings, chat databases, pools, and Docker volumes are retained;
the installer never uses `down -v` or prunes persistent data.

Contributors can prepare and run the complete test suite with:

```bash
make setup-test-env
make test
```

## Further documentation

- [Architecture and data flow](docs/architecture.md)
- [Server deployment](docs/deployment-server.md)
- [Team clients and SSH tunnels](docs/deployment-team.md)
- [Git server ACLs](docs/git-server-acl.md)
- [Safe GitHub publication](docs/github-workflow.md)
- [First-publication checklist](docs/github-publish.md)
- [Contributing](CONTRIBUTING.md)
- [Release history](CHANGELOG.md)

## Contact

- Bugs and feature requests: [GitHub Issues](https://github.com/bkl2000/llmflask/issues)
- Private and business inquiries: git@isarlab.de

## License

MIT. See [LICENSE](LICENSE).
