# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path


KEY_NAMES = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ZEN_API_KEY")
KEY_FILE_TEMPLATE = """# Add only the providers you use.
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
ZEN_API_KEY=
"""
_KEY_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*_API_KEY$")


def default_api_keys_path() -> Path:
    config_home = os.getenv("XDG_CONFIG_HOME")
    root = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return root / "llmflask" / "api.txt"


def configured_api_keys_path() -> Path:
    configured = os.getenv("LLMFLASK_API_KEYS_FILE")
    return Path(configured).expanduser() if configured else default_api_keys_path()


def api_keys_path() -> Path:
    configured = os.getenv("LLMFLASK_API_KEYS_FILE")
    if configured:
        return Path(configured).expanduser()

    default_path = default_api_keys_path()
    if default_path.exists():
        return default_path
    return Path("api.txt")


def _prepare_key_file(path: Path, *, protect_directory: bool) -> None:
    directory = path.parent
    directory_created = False
    try:
        directory_mode = directory.lstat().st_mode
    except FileNotFoundError:
        directory.mkdir(mode=0o700, parents=True)
        directory_created = True
    else:
        if stat.S_ISLNK(directory_mode) or not stat.S_ISDIR(directory_mode):
            raise ValueError(f"API key directory is not a regular directory: {directory}")
    if directory_created or protect_directory:
        directory.chmod(0o700)

    try:
        file_mode = path.lstat().st_mode
    except FileNotFoundError:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
            key_file.write(KEY_FILE_TEMPLATE)
    else:
        if stat.S_ISLNK(file_mode) or not stat.S_ISREG(file_mode):
            raise ValueError(f"API key file is not a regular file: {path}")
    path.chmod(0o600)


def configure_api_keys() -> int:
    path = configured_api_keys_path()
    try:
        _prepare_key_file(
            path,
            protect_directory=not bool(os.getenv("LLMFLASK_API_KEYS_FILE")),
        )
        editor_value = os.getenv("VISUAL") or os.getenv("EDITOR") or "vi"
        editor = shlex.split(editor_value)
        if not editor:
            raise ValueError("VISUAL/EDITOR does not contain an editor command")
        result = subprocess.run([*editor, str(path)], check=False)
    except (OSError, ValueError) as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1

    if result.returncode == 0:
        print(f"API key file: {path}")
    return result.returncode


def _parse_key_file(path: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return keys

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if _KEY_NAME_RE.fullmatch(name) and value:
            keys[name] = value
    return keys


def load_api_keys() -> dict[str, str]:
    keys = _parse_key_file(api_keys_path())
    configured_names = {
        name for name in os.environ if _KEY_NAME_RE.fullmatch(name)
    }
    for name in set(KEY_NAMES) | set(keys) | configured_names:
        env_value = os.getenv(name)
        if env_value:
            keys[name] = env_value
    return keys
