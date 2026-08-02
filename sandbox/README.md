# llmflask-sandbox:1

Isolated Debian container image for experimental LLMFlask Workbench pools.

## Build

```bash
docker build -t llmflask-sandbox:1 -f sandbox/Containerfile sandbox/
```

Optional with Podman:

```bash
podman build -t llmflask-sandbox:1 -f sandbox/Containerfile sandbox/
```

## Contents

- Base image: `debian:13-slim`
- Python 3 virtual environment at `/opt/venv` (automatically added to `PATH`)
- Preinstalled Python packages: numpy, scipy, pandas, matplotlib, pillow,
  pypdf, python-docx, openpyxl
- System tools: bash, coreutils, file, findutils, gawk, grep, sed, jq,
  ripgrep, pandoc, texlive-xetex, imagemagick, ffmpeg, graphviz, zip/tar/gzip
- Unprivileged `sandbox` user (UID 10001)
- `/pool` working directory with `input/`, `scripts/`, `output/`, and `logs/`

## Security

The image runs without network access or root privileges, with CPU, memory,
and PID limits and a read-only input mount. See `SandboxRunner` in the
LLMFlask documentation.
