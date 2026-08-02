# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
"""Data-driven CLI parser for LLMFlask.

Replaces argparse with a single-pass, grammar-driven parser that natively
understands free-form text after flags for --cmd and --usepool modes.

Every mode, flag, and constraint is declared in data tables. Adding a new
flag or mode requires only a table entry — no parser logic changes.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable


# ── Value converters ──────────────────────────────────────────────

def _int_positive(value: str) -> int:
    try:
        v = int(value)
    except ValueError:
        raise ValueError(f"expected an integer, got {value!r}")
    if v < 1:
        raise ValueError(f"expected a positive integer, got {v}")
    return v


def _port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise ValueError(f"port must be an integer, got {value!r}")
    if not 1 <= port <= 65535:
        raise ValueError(f"port must be between 1 and 65535, got {port}")
    return port


# ── Flag descriptors ──────────────────────────────────────────────

# Flags that consume exactly one following token as a value.
# Maps flag name → (attribute_name, converter_fn_or_None).
_VALUE_FLAGS: dict[str, tuple[str, Callable[[str], Any] | None]] = {
    "--text":         ("text", None),
    "--model":        ("model", None),
    "--host":         ("host", None),
    "--port":         ("port", _port_number),
    "--user":         ("user", None),
    "--provider":     ("provider", None),
    "--prompt":       ("prompt", None),
    "--session":      ("session", _int_positive),
    "--output":       ("output", None),
    "--file":         ("file", None),
    "--name":         ("pool_name", None),
    "--result-dir":   ("result_dir", None),
    "--server":       ("server", None),
}

# Boolean flags (presence sets attr to True).
_BOOL_FLAGS: dict[str, str] = {
    "--cmd":                 "cmd",
    "--tui":                 "tui",
    "--models":              "models",
    "--usepool":             "usepool",
    "--configure-api-keys":  "configure_api_keys",
    "--tui-trace":           "tui_trace",
    "--reuse-pool":          "reuse_pool",
    "--no-result":           "no_result",
    "--search":              "search",
}

# ── Mode identification ───────────────────────────────────────────

MODE_TOKENS: frozenset[str] = frozenset(
    {"--cmd", "--tui", "--models", "--usepool",
     "--configure-api-keys", "--server"}
)

SUBCOMMANDS: frozenset[str] = frozenset(
    {"pool", "result", "session", "user", "reset", "run"}
)


def _is_flag(token: str) -> bool:
    return token.startswith("-")


# ── Parser output ─────────────────────────────────────────────────

@dataclass
class ParsedArgs:
    mode: str | None = None
    # Boolean mode flags
    cmd: bool = False
    tui: bool = False
    models: bool = False
    usepool: bool = False
    configure_api_keys: bool = False
    # --server [production]
    server: str | None = None
    # Subcommand mode
    command: str | None = None
    pool_action: str | None = None
    result_action: str | None = None
    session_action: str | None = None
    user_action: str | None = None
    # Common flags
    text: str | None = None
    model: str | None = None
    host: str | None = None
    port: int | None = None
    user: str = "default"
    provider: str | None = None
    prompt: str | None = None
    output: str | None = None
    session: int | None = None
    tui_trace: bool = False
    # Pool flags
    file: str | None = None
    pool_name: str | None = None
    reuse_pool: bool = False
    result_dir: str | None = None
    no_result: bool = False
    search: bool = False
    # Subcommand positional args
    name: str | None = None
    old: str | None = None
    new: str | None = None


# ── Mode grammar ──────────────────────────────────────────────────

@dataclass
class ModeSpec:
    required: set[str] = field(default_factory=set)
    conflicts: set[str] = field(default_factory=set)
    accepts_text: bool = False
    subcommands: dict[str, ModeSpec] | None = None
    has_optional_value: bool = False  # e.g. --server [production]


_GRAMMAR: dict[str, ModeSpec] = {
    "--cmd": ModeSpec(
        required=set(),
        conflicts={"text"},
        accepts_text=True,
    ),
    "--tui": ModeSpec(required=set()),
    "--models": ModeSpec(required=set()),
    "--usepool": ModeSpec(
        required=set(),
        conflicts={"text"},
        accepts_text=True,
    ),
    "--configure-api-keys": ModeSpec(required=set()),
    "--server": ModeSpec(
        required=set(),
        has_optional_value=True,
    ),
}

_GRAMMAR_SUB: dict[str, ModeSpec] = {
    "pool": ModeSpec(
        required=set(),
        subcommands={
            "list":   ModeSpec(required=set()),
            "show":   ModeSpec(required={"name"}),
            "run":    ModeSpec(required={"name"}),
            "path":   ModeSpec(required={"name"}),
            "pack":   ModeSpec(required={"name"}),
            "remove": ModeSpec(required={"name"}),
            "debug":  ModeSpec(required={"name"}),
        },
    ),
    "result": ModeSpec(
        required=set(),
        subcommands={
            "list":    ModeSpec(required=set()),
            "inspect": ModeSpec(required={"name"}),
            "run":     ModeSpec(required={"name"}),
            "remove":  ModeSpec(required={"name"}),
        },
    ),
    "session": ModeSpec(
        required=set(),
        subcommands={
            "list":   ModeSpec(required=set()),
            "remove": ModeSpec(required={"name"}),
        },
    ),
    "user": ModeSpec(
        required=set(),
        subcommands={
            "list":   ModeSpec(required=set()),
            "add":    ModeSpec(required={"name"}),
            "rename": ModeSpec(required={"old", "new"}),
            "remove": ModeSpec(required={"name"}),
        },
    ),
    "reset": ModeSpec(required=set()),
    "run": ModeSpec(required=set()),  # "did you mean?" hint
}


# ── Parser ────────────────────────────────────────────────────────

def _print_error(msg: str) -> None:
    border = "─" * 62
    print(file=sys.stderr)
    print(f"  {msg}", file=sys.stderr)
    print(f"  {border}", file=sys.stderr)
    print(f"  Try: llmflask --help", file=sys.stderr)
    print(f"  {border}", file=sys.stderr)
    print(file=sys.stderr)


def _mode_error_hint(modes: list[str], parser: Any = None) -> None:
    parts = ", ".join(modes)
    _print_error(
        f"{parts} are different modes. Choose one.\n"
        "\n"
        "  For a direct question:\n"
        '    llmflask --cmd --model MODEL "your question"\n'
        "    llmflask --cmd --text \"your question\" --model MODEL\n"
        "    echo \"question\" | llmflask --cmd --model MODEL\n"
        "\n"
        "  For code generation / file processing:\n"
        '    llmflask --usepool --model MODEL "generate code"\n'
        "    llmflask --usepool --text \"generate code\" --model MODEL\n"
        '    llmflask --usepool --file data.csv "analyze" --model MODEL\n'
        "\n"
        "  To start the server:  llmflask --server\n"
        "  To start the TUI:      llmflask --tui\n"
    )
    sys.exit(2)


def _flag_requires_mode(flag: str, modes: str) -> None:
    _print_error(f"{flag} requires {modes}")
    sys.exit(2)


def parse(argv: list[str]) -> ParsedArgs:
    args = ParsedArgs()
    tokens = list(argv)
    if not tokens:
        return args

    if any(t in ("--help", "-h") for t in tokens):
        print_help()
        sys.exit(0)

    if "--version" in tokens:
        print("llmflask 0.1.0")
        sys.exit(0)

    i = 0
    active_modes: list[str] = []
    seen_text_flag = False

    # ── Pass 1: identify mode ─────────────────────────────────
    while i < len(tokens):
        t = tokens[i]

        # Subcommand start
        if t in SUBCOMMANDS:
            if t == "run":
                # "run" without --tui/--server/... should show hint
                _run_hint()
                sys.exit(2)
            args.command = t
            i += 1
            if t == "pool":
                args, i = _parse_subcommand(tokens, i, args,
                                            active_modes, seen_text_flag)
            elif t == "result":
                args, i = _parse_subcommand(tokens, i, args,
                                            active_modes, seen_text_flag)
            elif t == "session":
                args, i = _parse_subcommand(tokens, i, args,
                                            active_modes, seen_text_flag)
            elif t == "user":
                args, i = _parse_subcommand(tokens, i, args,
                                            active_modes, seen_text_flag)
            elif t == "reset":
                pass
            break

        # Mode flag (--cmd, --tui, etc.)
        if t in MODE_TOKENS:
            if t == "--server":
                # Optional value: --server [production]
                args.server = "dev"
                active_modes.append(t)
                i += 1
                if i < len(tokens) and tokens[i] in ("dev", "production"):
                    args.server = tokens[i]
                    i += 1
                continue
            elif t in _BOOL_FLAGS:
                attr = _BOOL_FLAGS[t]
                setattr(args, attr, True)
                active_modes.append(t)
                i += 1
                continue

        # Value flag (consumed as regular flag unless it's mode)
        if t in _VALUE_FLAGS:
            attr, conv = _VALUE_FLAGS[t]
            if t == "--text":
                seen_text_flag = True
            if i + 1 < len(tokens):
                val = tokens[i + 1]
                if conv:
                    try:
                        val = conv(val)
                    except ValueError as e:
                        _print_error(f"{t}: {e}")
                        sys.exit(2)
                if t == "--server":
                    args.server = val
                else:
                    setattr(args, attr, val)
                i += 2
            else:
                _print_error(f"{t} expects a value")
                sys.exit(2)
            continue

        # Bool flag (non-mode)
        if t in _BOOL_FLAGS:
            attr = _BOOL_FLAGS[t]
            setattr(args, attr, True)
            i += 1
            continue

        # Unknown token
        if t.startswith("-"):
            _print_error(f"unrecognized option: {t}")
            sys.exit(2)

        # Bare word — could be positional text
        break

    # ── Cross-flag validations (always checked, even without mode) ──
    if args.tui_trace and not args.tui:
        _print_error("--tui-trace requires --tui")
        sys.exit(2)

    if args.prompt is not None and not args.tui and not args.cmd:
        _print_error("--prompt requires --cmd or --tui")
        sys.exit(2)

    if args.text is not None and not args.cmd and not args.usepool:
        _print_error("--text requires --cmd or --usepool")
        sys.exit(2)

    if args.session is not None and not args.cmd:
        _print_error("--session requires --cmd")
        sys.exit(2)

    if args.provider not in (None, "server") and not args.tui and not args.cmd and not args.models:
        _print_error("--provider requires --tui, --cmd, or --models")
        sys.exit(2)

    if args.provider not in (None, "server") and (args.host is not None or args.port is not None):
        _print_error("--host/--port cannot be combined with a direct remote --provider")
        sys.exit(2)

    if args.output is not None and not args.cmd:
        _print_error("--output requires --cmd")
        sys.exit(2)

    model_allowed = args.cmd or args.usepool or args.pool_action == "run"
    if args.model is not None and not model_allowed:
        _print_error("--model requires --cmd, --usepool, or pool run")
        sys.exit(2)

    if args.model is not None and not args.model.strip():
        _print_error("--model requires a non-empty MODELREF; run llmflask --models first")
        sys.exit(2)

    if args.result_dir is not None and not (args.usepool or args.pool_action == "run"):
        _print_error("--result-dir is only valid with --usepool or pool run")
        sys.exit(2)

    if args.no_result and not (args.usepool or args.pool_action == "run"):
        _print_error("--no-result is only valid with --usepool or pool run")
        sys.exit(2)

    if args.pool_name is not None and not args.usepool:
        _print_error("--name is only valid with --usepool")
        sys.exit(2)

    if args.reuse_pool and not args.usepool:
        _print_error("--reuse-pool is only valid with --usepool")
        sys.exit(2)

    if args.search and not args.cmd:
        _print_error("--search is only valid with --cmd (requires --host/--port for server-side search)")
        sys.exit(2)

    if args.file is not None and not args.usepool:
        _print_error("--file is only valid with --usepool")
        sys.exit(2)

    if not active_modes and args.command is None:
        return args  # no mode, caller reports error

    # Validate mode count
    mode_count = len(active_modes) + (1 if args.command else 0)
    if mode_count > 1:
        _mode_error_hint(
            active_modes + ([args.command] if args.command else [])
        )

    # Determine primary mode
    if active_modes:
        args.mode = active_modes[0]
    elif args.command:
        args.mode = args.command

    # ── Pass 2: consume remaining flags ─────────────────────────
    i = _consume_remaining_flags(tokens, i, args, seen_text_flag)

    # ── Pass 3: collect trailing text for text-accepting modes ──
    grammar = _GRAMMAR.get(args.mode)
    if grammar and grammar.accepts_text and i < len(tokens) and not seen_text_flag:
        if args.text is None:
            args.text = " ".join(tokens[i:])

    # ── Validate required flags ─────────────────────────────────
    if grammar and grammar.required:
        missing = []
        for req in grammar.required:
            if req == "name" and args.name is None:
                missing.append("name")
            elif req == "old" and args.old is None:
                missing.append("old")
            elif req == "new" and args.new is None:
                missing.append("new")
            elif req.startswith("--"):
                attr = _BOOL_FLAGS.get(req, (req.lstrip("-"), None))
                if isinstance(attr, tuple):
                    attr = attr[0]
                attr = _BOOL_FLAGS.get(req) or _VALUE_FLAGS.get(req, (req.lstrip("-"), None))[0]
                if getattr(args, attr, None) is None:
                    missing.append(req)
        if missing:
            _print_error(f"{args.mode} requires {missing[0]}")
            sys.exit(2)

    return args


def _parse_subcommand(
    tokens: list[str],
    i: int,
    args: ParsedArgs,
    active_modes: list[str],
    seen_text_flag: bool,
) -> tuple[ParsedArgs, int]:
    cmd = args.command
    if cmd is None:
        return args, i

    grammar = _GRAMMAR_SUB.get(cmd)
    if grammar is None:
        return args, i

    # Parse sub-action (list, show, run, ...)
    if i < len(tokens) and tokens[i] in grammar.subcommands:
        action = tokens[i]
        i += 1
        sub = grammar.subcommands[action]
        # Store action on args
        action_map = {
            "pool": "pool_action",
            "result": "result_action",
            "session": "session_action",
            "user": "user_action",
        }
        attr = action_map.get(cmd)
        if attr:
            setattr(args, attr, action)

        # Consume positional args for the subcommand
        for req in sub.required:
            if req.startswith("--"):
                continue  # handled by flag parser
            if req == "name":
                if i < len(tokens) and not tokens[i].startswith("-"):
                    args.name = tokens[i]
                    i += 1
                else:
                    _print_error(f"pool {action} requires a name")
                    sys.exit(2)
            elif req == "old":
                if i < len(tokens) and not tokens[i].startswith("-"):
                    args.old = tokens[i]
                    i += 1
                    if "new" in sub.required:
                        if i < len(tokens) and not tokens[i].startswith("-"):
                            args.new = tokens[i]
                            i += 1
                        else:
                            _print_error("user rename requires old and new names")
                            sys.exit(2)
                else:
                    _print_error("user rename requires old and new names")
                    sys.exit(2)

        # Consume remaining flags after subcommand args
        i = _consume_remaining_flags(tokens, i, args, seen_text_flag)

    return args, i


def _consume_remaining_flags(
    tokens: list[str],
    i: int,
    args: ParsedArgs,
    seen_text_flag: bool,
) -> int:
    """Consume --flag [value] pairs and --flag (bool) from position i onward."""
    while i < len(tokens):
        t = tokens[i]
        if t in SUBCOMMANDS or t in MODE_TOKENS:
            break
        if t in _VALUE_FLAGS:
            attr, conv = _VALUE_FLAGS[t]
            if t == "--text":
                seen_text_flag = True
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                val = tokens[i + 1]
                if conv:
                    try:
                        val = conv(val)
                    except ValueError as e:
                        _print_error(f"{t}: {e}")
                        sys.exit(2)
                setattr(args, attr, val)
                i += 2
            else:
                _print_error(f"{t} expects a value")
                sys.exit(2)
            continue
        if t in _BOOL_FLAGS:
            attr = _BOOL_FLAGS[t]
            setattr(args, attr, True)
            i += 1
            continue
        if t.startswith("-"):
            _print_error(f"unrecognized option: {t}")
            sys.exit(2)
        break  # positional text
    return i


def _run_hint() -> None:
    _print_error(
        '"run" is not a standalone command.\n\n'
        "  Did you mean one of these?\n"
        "    llmflask pool run POOL --model MODEL   Re-run a pool\n"
        "    llmflask result run NAME                Run a downloaded result locally"
    )


def print_help() -> None:
    print(
        "LLMFlask — local LLM chat, batch queries, and pool workbench\n"
        "\n"
        "Quick Start:\n"
        "  llmflask --models                              List available models\n"
        "  llmflask --cmd --model ollama/qwen3:8b Hello   Single batch query\n"
        "  llmflask --cmd --model ollama/qwen3:8b          Read question from stdin\n"
        "  llmflask --tui                                  Terminal chat client\n"
        "\n"
        "Server:\n"
        "  llmflask --server                  Flask dev server, threaded (default)\n"
        "  llmflask --server production       Gunicorn, 1 worker x 16 threads\n"
        "\n"
        "Pool Workbench (code generation + sandbox execution):\n"
        '  llmflask --usepool --model MODELREF "task"      Generate & run code\n'
        "  llmflask --usepool --text \"task\" --model M       Same via explicit --text\n"
        '  llmflask --usepool --file data.csv "analyze" --model M  Upload + task\n'
        "  llmflask pool list\n"
        "  llmflask pool show NAME\n"
        "  llmflask pool run POOL --model MODELREF\n"
        "  llmflask pool pack NAME                        Archive pool as tar.gz\n"
        "  llmflask pool path NAME                        Show pool directory on server\n"
        "  llmflask pool remove {NAME | all | failed}\n"
        "  llmflask pool debug NAME                       Show full pool state\n"
        "\n"
        "Downloaded Results:\n"
        "  llmflask result list\n"
        "  llmflask result inspect NAME\n"
        "  llmflask result run NAME                        Auto-runs setup.sh then run.sh\n"
        "  llmflask result remove NAME\n"
        "\n"
        "Profile & Sessions:\n"
        "  llmflask user list\n"
        "  llmflask user add NAME\n"
        "  llmflask user rename OLD NEW\n"
        "  llmflask user remove NAME\n"
        "  llmflask session list --user USER\n"
        "  llmflask session remove ID --user USER\n"
        "\n"
        "Management:\n"
        "  llmflask --configure-api-keys                    Edit remote API keys\n"
        "  llmflask pool remove all --user USER             Delete all pools for user\n"
        "  llmflask reset                                   Reset local stored state\n"
        "\n"
        "Flags (use with modes listed above):\n"
        "  Connection:\n"
        "    --host HOST          Server address (default: 127.0.0.1)\n"
        "    --port PORT          Server port (default: 5000)\n"
        "  Provider:\n"
        "    --provider NAME          server or configured remote provider\n"
        "  Profile & Session:\n"
        "    --user USER          User profile (default: \"default\")\n"
        "    --session ID         Attach --cmd query to existing chat session\n"
        "  Prompt & Output:\n"
        '    --text "TEXT"         Question text (explicit; alternative to positional)\n'
        "    --prompt FILE         System prompt file (bare names looked up under prompts/)\n"
        "    --output FILE         Write response to file (with --cmd)\n"
        "  Pool Options (with --usepool or pool run):\n"
        "    --file PATH           Upload file/directory\n"
        "    --name NAME           Name for the generated pool\n"
        "    --reuse-pool          Reuse existing pool\n"
        "    --result-dir DIR      Directory for downloaded results\n"
        "    --no-result           Skip result download after pool completion\n"
        "  Other:\n"
        "    --search              Enable web search (requires --cmd --host/--port)\n"
        "    --tui-trace           Log TUI keystrokes to /tmp (requires --tui)\n"
        "\n"
        "Convenience Wrappers (installed via make install-tools):\n"
        '  llmflaskcmd "question"                            Direct batch query\n'
        "  llm-ask --model MODELREF \"question\"              Server batch query\n"
        "  llm-chat                                          TUI client\n"
        "  llm-pool NAME --model MODELREF                     Pool generation\n"
        "  llm-runresult NAME                                Run downloaded result\n"
    )
