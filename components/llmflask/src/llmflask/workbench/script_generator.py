# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
import re
from pathlib import Path

from ..chat_runtime import build_chat_messages
from ..services.model_providers import chat_stream
from ._utils import strip_code_fences


_DELIMITER_RE = re.compile(
    r"^---\s+([^\n]+?)\s*\n(.*?)(?=\n---\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_MD_BLOCK_RE = re.compile(r"```(?:python|bash|shell|sh|text)?\s*(?:#\s*)?(\S+\.(?:py|sh|txt|md))\n(.*?)```", re.DOTALL)
_MD_BLOCK_NOFILE_RE = re.compile(r"```(?:python|bash|shell|sh)?\n(.*?)```", re.DOTALL)
_VALID_FILENAME = re.compile(r"^[\w./-]+\.(?:py|sh|txt|md)$")
_ROOT_ARTIFACTS = {"requirements.txt", "apt-packages.txt", "setup.sh", "run.sh", "README.md"}


def _is_valid_filename(name: str) -> bool:
    if not _VALID_FILENAME.fullmatch(name) or "\\" in name:
        return False
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    return name in _ROOT_ARTIFACTS or (len(path.parts) >= 2 and path.parts[0] == "scripts")


def _parse_delimiter_sections(response: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    ambiguous: tuple[str | None, str | None] = (None, None)

    for match in _DELIMITER_RE.finditer(response):
        raw_name = match.group(1).strip()
        content = match.group(2).strip()
        if not content:
            continue

        if "main.py" in raw_name and "main.sh" in raw_name:
            ambiguous = (raw_name, content)
            continue

        name = _normalize_name(raw_name)
        if not _is_valid_filename(name):
            continue
        sections[name] = content

    if ambiguous[0] is not None:
        _, content = ambiguous
        if content and content.strip().startswith("#!/") and "sh" in content[:30].lower():
            sections["scripts/main.sh"] = content
        else:
            sections["scripts/main.py"] = content

    return sections


def _parse_markdown_blocks(response: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for match in _MD_BLOCK_RE.finditer(response):
        filename = match.group(1)
        code = match.group(2).strip()
        if not code:
            continue
        if filename.startswith("scripts/") or filename.startswith("."):
            target_name = filename
        elif filename in _ROOT_ARTIFACTS:
            target_name = filename
        else:
            target_name = f"scripts/{filename}"
        if _is_valid_filename(target_name):
            sections[target_name] = code

    if not sections:
        for match in _MD_BLOCK_NOFILE_RE.finditer(response):
            code = match.group(1).strip()
            if code and len(code) > 20:
                sections["scripts/main.py"] = code
                break

    return sections


def _normalize_name(raw: str) -> str:
    if "main.py" in raw and ("main.sh" in raw or "oder" in raw):
        return "scripts/main.py"
    clean = raw.rstrip("):")
    if clean.endswith((".py", ".sh", ".txt", ".md")):
        return clean
    return raw


def _inventory(pool_path: Path) -> str:
    input_dir = pool_path / "input"
    if not input_dir.is_dir():
        return "(keine Eingabedateien)"

    lines: list[str] = []
    for path in sorted(input_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(input_dir)
            size = path.stat().st_size
            lines.append(f"  {rel} ({_format_size(size)})")

    if not lines:
        return "(leeres Eingabeverzeichnis)"
    return "\n".join(lines)


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _fill_prompt(template: str, request: str, inventory_text: str) -> str:
    return (
        template
        .replace("{{request}}", request)
        .replace("{{inventory}}", inventory_text)
    )


def _parse_response(response: str) -> dict[str, str]:
    sections = _parse_delimiter_sections(response)
    if sections:
        return sections

    sections = _parse_markdown_blocks(response)
    if sections:
        return sections

    return {}


def generate_pool(
    pool_path: str,
    request: str,
    model_ref: str,
    prompt_template: str,
) -> str:
    pool_dir = Path(pool_path).expanduser().resolve()
    if not pool_dir.is_dir():
        raise FileNotFoundError(f"Pool not found: {pool_path}")

    inv = _inventory(pool_dir)
    prompt = _fill_prompt(prompt_template, request, inv)
    messages = build_chat_messages(prompt, system_prompt=prompt_template)

    response = ""
    for token in chat_stream(messages, model_ref):
        response += token

    log_dir = pool_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    raw_log = log_dir / "llm_response.txt"
    raw_log.write_text(response, encoding="utf-8")

    sections = _parse_response(response)
    if not sections:
        sections = _fallback_sections(response, request, inv)

    for key in list(sections):
        if key.endswith('.py'):
            sections[key] = _wrap_with_args(sections[key])

    return _write_sections(pool_dir, sections)


_DEFAULT_SETUP_SH = """\
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
if [[ -f "$ROOT_DIR/requirements.txt" ]] && [[ -s "$ROOT_DIR/requirements.txt" ]]; then
    "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"
fi
"""

def _ensure_run_sh(pool_dir: Path) -> str:
    scripts = pool_dir / "scripts"
    has_py = (scripts / "main.py").is_file()
    has_sh = (scripts / "main.sh").is_file()

    if has_sh:
        content = _RUN_SH_BASH
    elif has_py:
        content = _RUN_SH_PYTHON
    else:
        content = _RUN_SH_NONE

    run_sh = pool_dir / "run.sh"
    run_sh.write_text(content, encoding="utf-8")
    try:
        os.chmod(run_sh, 0o755)
    except OSError:
        pass
    return "run.sh"


_RUN_SH_PYTHON = """\
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x /opt/venv/bin/python ]]; then
    PYTHON=/opt/venv/bin/python
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
else
    echo "No Python found. Create venv: python3 -m venv .venv && source .venv/bin/activate" >&2
    exit 1
fi
exec "$PYTHON" "$ROOT_DIR/scripts/main.py" --input "$ROOT_DIR/input" --output "$ROOT_DIR/output"
"""

_RUN_SH_BASH = """\
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$ROOT_DIR/scripts/main.sh" "$ROOT_DIR/input" "$ROOT_DIR/output"
"""

_RUN_SH_NONE = """\
#!/usr/bin/env bash
echo "No executable script in pool (neither main.py nor main.sh)." >&2
exit 1
"""


_HARDCODED_INPUT_QUOTED_RE = re.compile(r"""["']/pool/input["']""")
_HARDCODED_OUTPUT_QUOTED_RE = re.compile(r"""["']/pool/output["']""")
_HARDCODED_INPUT_BARE_RE = re.compile(r"(?<!\w)/pool/input")
_HARDCODED_OUTPUT_BARE_RE = re.compile(r"(?<!\w)/pool/output")


def _wrap_with_args(code: str) -> str:
    code = _HARDCODED_INPUT_QUOTED_RE.sub("INPUT", code)
    code = _HARDCODED_OUTPUT_QUOTED_RE.sub("OUTPUT", code)
    code = _HARDCODED_INPUT_BARE_RE.sub("INPUT", code)
    code = _HARDCODED_OUTPUT_BARE_RE.sub("OUTPUT", code)

    has_argv = "sys.argv" in code
    has_argparse = "argparse" in code
    has_import_sys = "import sys" in code

    if has_argparse:
        return code
    if has_argv:
        if has_import_sys:
            return code
        return "import sys\n" + code

    return (
        "import sys, os\n"
        "def _arg(flag, default):\n"
        "    try: return sys.argv[sys.argv.index(flag) + 1]\n"
        "    except (ValueError, IndexError): return default\n"
        "INPUT = _arg('--input', 'input')\n"
        "OUTPUT = _arg('--output', 'output')\n"
        + code
    )


def _fallback_sections(response: str, request: str, inventory: str) -> dict[str, str]:
    response = strip_code_fences(response)
    script_name = _script_filename(response)
    if script_name.endswith((".py", ".sh")):
        response = _wrap_with_args(response)
    readme = (
        f"# Pool\n\n"
        f"## Ziel\n\n{request}\n\n"
        f"## Eingaben\n\n{inventory}\n\n"
        f"## Ausfuehrung\n\n./run.sh\n\n"
    )
    sections = {
        f"scripts/{script_name}": response,
        "requirements.txt": "",
        "setup.sh": _DEFAULT_SETUP_SH,
        "README.md": readme,
    }
    return sections


def _script_filename(response: str) -> str:
    text = strip_code_fences(response).strip()
    if text.startswith("#!/") and "sh" in text[:30].lower():
        return "main.sh"
    if text.startswith("#!/usr/bin/env python") or text.startswith("#!/usr/bin/python"):
        return "main.py"
    if any(keyword in text[:200] for keyword in ("import ", "def ", "class ", "print(", "if __name__")):
        return "main.py"
    if any(keyword in text[:200] for keyword in ("#!/bin/bash", "#!/usr/bin/env bash", "set -euo pipefail", "set -eu")):
        return "main.sh"
    return "main.txt"


def _write_sections(pool_dir: Path, sections: dict[str, str]) -> str:
    scripts_dir = pool_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)

    written: list[str] = []

    for filename, content in sections.items():
        if not _is_valid_filename(filename):
            continue
        target = pool_dir / filename
        if pool_dir not in target.resolve().parents:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if not content.endswith("\n"):
            content += "\n"
        target.write_text(content, encoding="utf-8")
        try:
            os.chmod(target, 0o644)
        except OSError:
            pass
        written.append(filename)

    if "run.sh" in sections:
        written.remove("run.sh")
    written.append(_ensure_run_sh(pool_dir))

    for sub in ("scripts", "output", "logs"):
        d = pool_dir / sub
        if d.is_dir():
            try:
                os.chmod(d, 0o777 if sub in ("output", "logs") else 0o755)
            except OSError:
                pass

    return "\n".join(f"  - {f}" for f in sorted(written))
