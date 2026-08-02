# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


import httpx

from .batch import load_prompt, run_batch_command, run_server_batch_command
from .cli_http import api_request, iter_pool_events
from .pool_cli import (
    _download_result,
    _pool_debug,
    _pool_list,
    _pool_pack,
    _pool_path,
    _pool_remove,
    _pool_remove_all,
    _pool_remove_failed,
    _pool_run,
    _pool_show,
    _print_pool_result,
    _run_pool_cli,
    _run_pool_command,
)
from .session_cli import _run_session_command, _session_list, _session_remove
from .user_cli import _run_user_command, _user_list, _user_add, _user_rename, _user_remove
from .config import RESULT_DIR as DEFAULT_RESULT_DIR
from .server_runtime import gunicorn_base_application, gunicorn_options, run_gunicorn_app
from .services.api_keys import configure_api_keys, load_api_keys
from .services.model_providers import REMOTE_PROVIDERS, list_models, list_remote_models, ollama_reachable
from .result_cli import (
    _run_result_command, _result_root, _safe_result_path,
    _is_downloaded_result, _result_list, _result_inspect,
    _result_run, _result_remove,
)
from .model_discovery import (
    _local_server_available, _resolve_tui_provider, _server_models,
    _direct_provider_models, _show_available_models, print_models,
    _validate_model_ref,
)
from .cli_parser import ParsedArgs, parse, print_help  # noqa: E402


def _port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _positive_session_id(value: str) -> int:
    try:
        session_id = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("session ID must be an integer") from error
    if session_id < 1:
        raise argparse.ArgumentTypeError("session ID must be positive")
    return session_id


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


_gunicorn_options = gunicorn_options
_gunicorn_base_application = gunicorn_base_application
run_gunicorn = run_gunicorn_app



class _TeeWriter:
    """Writes to two file objects in sequence, flushing both."""

    def __init__(self, left, right) -> None:
        self._left = left
        self._right = right

    def write(self, s: str) -> None:
        self._left.write(s)
        self._right.write(s)

    def flush(self) -> None:
        self._left.flush()
        self._right.flush()


def _tee_writer(f1, f2):
    return _TeeWriter(f1, f2)



def _reset(host: str, port: int, user: str = "default") -> int:
    base = _base_url(host, port)
    print("Removing all pools...")
    pool_status = _pool_remove_all(base)
    print("Removing sessions for the selected user...")
    session_status = _session_remove(base, "all", user)
    print("Removing recognized local results...")
    result_status = _result_remove("all")
    if any((pool_status, session_status, result_status)):
        print("llmflask: error: Reset incomplete; see errors above.", file=sys.stderr)
        return 1
    print("Reset complete.")
    return 0


_TEXT_MODE_FLAGS: frozenset[str] = frozenset({"--cmd", "--usepool"})


def _extract_positional_text(argv: list[str]) -> tuple[list[str], str | None]:
    """When --cmd or --usepool is present, convert trailing positional text into --text.

    Returns (modified_argv, extracted_text_or_none).
    """
    if not _TEXT_MODE_FLAGS.intersection(argv):
        return argv, None

    VALUE_FLAGS: frozenset[str] = frozenset({
        "--host", "--port", "--user", "--model", "--provider",
        "--text", "--prompt", "--session", "--output", "--file",
        "--name", "--result-dir", "--server",
    })
    SUBCOMMANDS: frozenset[str] = frozenset({"pool", "result", "session", "user", "reset"})

    result = [argv[0]]
    trailing: list[str] = []
    has_text_flag = False
    i = 1

    while i < len(argv):
        arg = argv[i]

        if arg in SUBCOMMANDS:
            if trailing:
                trailing.append(arg)
                i += 1
                continue
            result.append(arg)
            result.extend(argv[i + 1 :])
            return result, None

        if arg in VALUE_FLAGS:
            if arg == "--text":
                has_text_flag = True
            result.append(arg)
            if i + 1 < len(argv):
                result.append(argv[i + 1])
                i += 1
            i += 1
            continue

        if arg.startswith("-"):
            result.append(arg)
            i += 1
            continue

        if not has_text_flag:
            trailing.append(arg)
        i += 1

    if trailing and not has_text_flag:
        result.extend(["--text", " ".join(trailing)])

    return result, " ".join(trailing) if trailing else None


def _error_hint(msg: str, suggestion: str) -> None:
    border = "─" * 62
    print(f"\n  {msg}", file=sys.stderr)
    print(f"  {border}", file=sys.stderr)
    for line in suggestion.split("\n"):
        print(f"  {line}", file=sys.stderr)
    print(f"  {border}\n", file=sys.stderr)
    sys.exit(2)


def _validate_mode(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    command_mode = args.command is not None
    mode_count = sum([
        args.tui,
        args.cmd,
        args.usepool,
        args.models,
        args.configure_api_keys,
        args.server is not None,
        command_mode,
    ])

    if mode_count > 1:
        parts = []
        if args.tui: parts.append("--tui")
        if args.cmd: parts.append("--cmd")
        if args.usepool: parts.append("--usepool")
        if args.models: parts.append("--models")
        if args.configure_api_keys: parts.append("--configure-api-keys")
        if args.server is not None: parts.append("--server")
        if command_mode: parts.append(args.command)
        _error_hint(
            f"{', '.join(parts)} are different modes. Choose one.",
            "\n".join([
                "For a direct question:",
                "  llmflask --cmd --model MODEL \"your question\"",
                "  llmflask --cmd --text \"your question\" --model MODEL",
                "  echo \"question\" | llmflask --cmd --model MODEL",
                "",
                "For code generation / file processing:",
                "  llmflask --usepool --model MODEL \"generate code\"",
                "  llmflask --usepool --text \"generate code\" --model MODEL",
                "  llmflask --usepool --file data.csv \"analyze\" --model MODEL",
                "",
                "To start the server:  llmflask --server",
                "To start the TUI:      llmflask --tui",
            ]),
        )

    if args.tui_trace and not args.tui:
        parser.error("--tui-trace requires --tui")

    pool_run = args.command == "pool" and getattr(args, "pool_action", None) == "run"

    if args.result_dir is not None and not (args.usepool or pool_run):
        _error_hint("--result-dir is only valid with --usepool or pool run.",
            "  llmflask pool run POOL --model MODEL --result-dir DIR")

    if args.no_result and not (args.usepool or pool_run):
        _error_hint("--no-result is only valid with --usepool or pool run.",
            "  llmflask pool run POOL --model MODEL --no-result")

    if args.pool_name is not None and not args.usepool:
        _error_hint("--name is only valid with --usepool.",
            "  llmflask --usepool --file data.csv --text \"analyze\" --model MODEL --name my-pool")

    if args.reuse_pool and not args.usepool:
        _error_hint("--reuse-pool is only valid with --usepool.",
            "  llmflask --usepool --file data.csv --text \"analyze\" --model MODEL --reuse-pool")

    if args.file is not None and not args.usepool:
        _error_hint("--file is only valid with --usepool.",
            "  llmflask --usepool --file data.csv --text \"analyze\" --model MODEL")

    if args.prompt is not None and not args.tui and not args.cmd:
        parser.error("--prompt requires --cmd or --tui")

    if args.text is not None and not args.cmd and not args.usepool:
        _error_hint("--text requires --cmd or --usepool.",
            "\n".join([
                "  For a direct question:",
                "    llmflask --cmd --model MODEL \"your question\"",
                "    llmflask --cmd --text \"your question\" --model MODEL",
                "",
                "  For code generation / file processing:",
                "    llmflask --usepool --text \"generate code\" --model MODEL",
                "    llmflask --usepool --file data.csv --text \"analyze\" --model MODEL",
            ]))

    if args.session is not None and not args.cmd:
        parser.error("--session requires --cmd")

    if args.provider not in (None, "server") and not args.tui and not args.cmd and not args.models:
        parser.error("--provider requires --tui, --cmd, or --models")

    if args.provider not in (None, "server") and (args.host is not None or args.port is not None):
        parser.error("--host/--port cannot be combined with a direct remote --provider")

    if args.output is not None and not args.cmd:
        parser.error("--output requires --cmd")

    model_allowed = args.cmd or args.usepool or pool_run
    if args.model is not None and not model_allowed:
        parser.error("--model requires --cmd, --usepool, or pool run")

    if args.model is not None and not args.model.strip():
        parser.error("--model requires a non-empty MODELREF; run llmflask --models and copy an exact value")

    if (args.usepool or pool_run) and not args.model:
        _error_hint(
            "--usepool and pool run require --model <MODELREF>",
            "\n".join([
                "Run llmflask --models first to see available model references:",
                "  llmflask --models",
                "  llmflask --models --host SERVER_IP",
                "",
                "Then copy a MODELREF into your command:",
                "  llmflask --usepool --model ollama/qwen3:14b \"your task\"",
                "  llmflask --usepool --model deepseek/deepseek-chat \"your task\"",
            ]),
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmflask",
        description=(
            "LLMFlask — local LLM chat, batch queries, and pool workbench\n"
            "\n"
            "Quick Start:\n"
            "  llmflask --models                              List available models (copy a MODELREF)\n"
            "  llmflask --cmd --model ollama/qwen3:8b Hello   Single batch query (local Ollama)\n"
            "  llmflask --cmd --model ollama/qwen3:8b          Read question from stdin\n"
            "  llmflask --tui                                  Terminal chat client (local)\n"
            "\n"
            "Pool Workbench (code generation + sandbox execution):\n"
            "  llmflask --usepool --model MODELREF \"task\"      Generate & run code (positional text)\n"
            "  llmflask --usepool --text \"task\" --model M       Same via explicit --text\n"
            "  llmflask --usepool --file data.csv \"analyze\" --model M  Upload + task\n"
            "  llmflask pool list\n"
            "  llmflask pool run POOL --model MODELREF\n"
            "\n"
            "Downloaded Results (run locally after download):\n"
            "  llmflask result list\n"
            "  llmflask result run NAME                        (auto-runs setup.sh then run.sh)\n"
            "\n"
            "Management:\n"
            "  llmflask --server                                Start chat server\n"
            "  llmflask --configure-api-keys                    Edit remote API keys\n"
            "  llmflask session list --user USER                List chat sessions\n"
            "  llmflask pool remove all --user USER             Remove all pools\n"
            "\n"
            "Convenience Wrappers (installed in ~/bin via make install-tools):\n"
            "  llmflaskcmd \"question\"                            Direct batch query (local defaults)\n"
            "  llm-ask --model MODELREF \"question\"              Server batch query\n"
            "  llm-chat                                          TUI client with server defaults\n"
            "  llm-runresult NAME                                Run downloaded result locally"
        ),
        epilog=(
            "Examples:\n"
            "  llmflask --server                                   Start chat server\n"
            "  llmflask --cmd --model ollama/qwen3:8b Hello        Single batch query\n"
            "  llmflask --cmd --text \"Hello\" --model ollama/qwen3:8b  Same via --text\n"
            "  llmflask --tui --host SERVER_IP                       Terminal client\n"
            "  llmflask --models                                   List available MODELREF values\n"
            "  llmflask --configure-api-keys                       Securely edit remote API keys\n"
            "  llmflask --usepool --model M \"generate a todo app\"   Generate & execute code\n"
            "  llmflask --usepool --file data.csv \"analyze csv\" --model M  Upload file + task"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version="llmflask 0.2.0",
    )
    parser.add_argument(
        "--tui", action="store_true",
        help="Start terminal client instead of server",
    )
    parser.add_argument(
        "--cmd", action="store_true",
        help="Send a batch question. Usage: --cmd --model MODEL [TEXT|--text TEXT|stdin]; same positional pattern for --usepool",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help=(
            "Question text for --cmd or --usepool mode (also accepted as "
            "trailing positional text)"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save the streamed --cmd response to a file",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model reference for --cmd, --usepool, or pool run; copy one from --models",
    )
    parser.add_argument(
        "--session",
        type=_positive_session_id,
        default=None,
        help="Session ID to append --cmd messages to (visible in TUI/GUI)",
    )
    parser.add_argument(
        "--models",
        action="store_true",
        help="List available MODELREF values for commands that require --model",
    )
    parser.add_argument(
        "--configure-api-keys",
        action="store_true",
        help="Securely create and edit the OpenAI/DeepSeek API key file",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Prompt file for --cmd or --tui (bare names searched under prompts/)",
    )
    parser.add_argument(
        "--tui-trace", action="store_true",
        help="Write TUI debug trace to /tmp",
    )
    parser.add_argument(
        "--host", type=str, default=None,
        help="Client target or server bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=_port_number, default=None,
        help="Server port (default: 5000)",
    )
    parser.add_argument(
        "--user", type=str, default="default",
        help="Username for TUI, CMD sessions, session commands, server default, or reset",
    )
    parser.add_argument(
        "--provider",
        choices=("server", *REMOTE_PROVIDERS),
        default=None,
        help=(
            "Backend for --tui, --cmd, or --models; accepts server or a "
            "configured remote provider and auto-detects when omitted"
        ),
    )
    parser.add_argument(
        "--server",
        nargs="?",
        const="dev",
        default=None,
        choices=("dev", "production"),
        help="Start server: --server (Flask dev) or --server production (Gunicorn)",
    )

    pool_group = parser.add_argument_group("Pool options")
    pool_group.add_argument(
        "--usepool", action="store_true",
        help=(
            "Process a request in a pool sandbox. Accepts positional text after flags "
            "(use --text or stdin instead)"
        ),
    )
    pool_group.add_argument(
        "--file",
        type=str,
        default=None,
        help="Input file or directory for --usepool (optional)",
    )
    pool_group.add_argument(
        "--name",
        dest="pool_name",
        type=str,
        default=None,
        help="Name for new pool (optional, auto-generated if omitted)",
    )
    pool_group.add_argument(
        "--reuse-pool",
        action="store_true",
        help="Reuse existing pool instead of creating a new one",
    )
    pool_group.add_argument(
        "--result-dir",
        type=str,
        default=None,
        help="Directory for auto-downloaded results (env: LLMFLASK_RESULT_DIR, default: ~/llmflask-results)",
    )
    pool_group.add_argument(
        "--no-result",
        action="store_true",
        help="Skip automatic result download after a completed pool run",
    )

    subparsers = parser.add_subparsers(dest="command")
    pool_p = subparsers.add_parser("pool", help="Pool management")
    pool_sp = pool_p.add_subparsers(dest="pool_action", required=True)
    pool_sp.add_parser("list", help="List all pools")
    show_p = pool_sp.add_parser("show", help="Show pool details")
    show_p.add_argument("name", help="Pool name")
    run_p = pool_sp.add_parser("run", help="Re-run pool")
    run_p.add_argument("name", help="Pool name")
    run_p.add_argument("--model", default=argparse.SUPPRESS, help="Model reference (required; copy from --models)")
    run_p.add_argument("--result-dir", default=argparse.SUPPRESS, help="Directory for downloaded results")
    run_p.add_argument("--no-result", action="store_true", default=argparse.SUPPRESS, help="Skip result download")
    path_p = pool_sp.add_parser("path", help="Show pool directory on server")
    path_p.add_argument("name", help="Pool name")
    pack_p = pool_sp.add_parser("pack", help="Archive pool as tar.gz")
    pack_p.add_argument("name", help="Pool name")
    remove_p = pool_sp.add_parser("remove", help="Delete pool(s)")
    remove_p.add_argument("name", help="Pool name, 'failed', or 'all'")
    debug_p = pool_sp.add_parser("debug", help="Show full pool state incl. file contents for diagnostics")
    debug_p.add_argument("name", help="Pool name")

    result_p = subparsers.add_parser("result", help="Manage downloaded pool results")
    result_sp = result_p.add_subparsers(dest="result_action", required=True)
    result_sp.add_parser("list", help="List all downloaded results")
    inspect_r = result_sp.add_parser("inspect", help="Show result structure")
    inspect_r.add_argument("name", help="Result directory name")
    run_r = result_sp.add_parser("run", help="Run result locally (auto-runs setup.sh, then run.sh)")
    run_r.add_argument("name", help="Result directory name")
    remove_r = result_sp.add_parser("remove", help="Delete result(s)")
    remove_r.add_argument("name", help="Result name or 'all'")

    hint_p = subparsers.add_parser(
        "run",
        help="Hint — did you mean pool run or result run?",
        add_help=False,
    )

    session_p = subparsers.add_parser("session", help="Manage chat sessions")
    session_sp = session_p.add_subparsers(dest="session_action", required=True)
    session_sp.add_parser("list", help="List sessions for a user")
    session_remove = session_sp.add_parser("remove", help="Delete session(s)")
    session_remove.add_argument("name", help="Session ID or 'all'")

    user_p = subparsers.add_parser("user", help="Manage users")
    user_sp = user_p.add_subparsers(dest="user_action", required=True)
    user_sp.add_parser("list", help="List all users")
    user_add = user_sp.add_parser("add", help="Add a user")
    user_add.add_argument("name", help="Username")
    user_rename = user_sp.add_parser("rename", help="Rename a user")
    user_rename.add_argument("old", help="Current username")
    user_rename.add_argument("new", help="New username")
    user_remove = user_sp.add_parser("remove", help="Delete a user and their chats")
    user_remove.add_argument("name", help="Username")

    subparsers.add_parser(
        "reset",
        help="Remove all pools, selected user's sessions, and recognized local results",
    )

    return parser


def _run_hint() -> int:
    _error_hint(
        "'run' is not a standalone command. Did you mean pool run or result run?",
        "\n".join([
            "Server-side sandbox execution:",
            "  llmflask pool run POOL --model MODELREF",
            "",
            "Local execution of downloaded result:",
            "  llmflask result run NAME",
        ]),
    )


def _dispatch_management_command(
    args: argparse.Namespace,
    host: str,
    port: int,
) -> int | None:
    handlers = {
        "pool": lambda: _run_pool_command(args, host, port),
        "result": lambda: _run_result_command(args),
        "run": lambda: _run_hint(),
        "session": lambda: _run_session_command(args, host, port),
        "user": lambda: _run_user_command(args, host, port),
        "reset": lambda: _reset(host, port, args.user),
    }
    handler = handlers.get(args.command)
    return handler() if handler is not None else None


def _handle_api_keys() -> int:
    return configure_api_keys()


def _handle_models(args: ParsedArgs, host: str, port: int, target: bool) -> int:
    return print_models(host, port, provider=args.provider or "server", use_server=target)


def _handle_usepool(args: ParsedArgs, host: str, port: int, target: bool) -> int:
    source_file = args.file
    try:
        request_text = args.text if args.text is not None else sys.stdin.read()
    except KeyboardInterrupt:
        print(file=sys.stderr)
        print("llmflask: interrupted", file=sys.stderr)
        return 130
    if not request_text.strip():
        print("llmflask: error: --usepool requires non-empty --text or stdin", file=sys.stderr)
        sys.exit(2)
    if not args.model:
        print("llmflask: error: --usepool requires --model <MODELREF>", file=sys.stderr)
        _show_available_models(args.provider, host, port, target)
        sys.exit(2)
    model_ref = args.model
    if not _validate_model_ref(host, port, model_ref, use_server=target):
        return 1
    result_dir = None if args.no_result else (args.result_dir or DEFAULT_RESULT_DIR)
    try:
        return _run_pool_cli(
            source=source_file, request_text=request_text, model_ref=model_ref,
            host=host, port=port, pool_name=args.pool_name,
            reuse=args.reuse_pool, result_dir=result_dir,
        )
    except Exception as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1


def _handle_cmd(args: ParsedArgs, host: str, port: int, target: bool) -> int:
    provider = args.provider or "server"
    try:
        question = args.text if args.text is not None else sys.stdin.read()
    except KeyboardInterrupt:
        print(file=sys.stderr)
        print("llmflask: interrupted", file=sys.stderr)
        return 130
    if not question.strip():
        print("llmflask: error: --cmd requires non-empty --text or stdin", file=sys.stderr)
        sys.exit(2)
    if not args.model:
        print("llmflask: error: --cmd requires --model <MODELREF>", file=sys.stderr)
        _show_available_models(provider, host, port, target)
        sys.exit(2)
    model_ref = args.model
    if "/" not in model_ref and provider != "server":
        model_ref = f"{provider}/{model_ref}"
    elif provider != "server" and not model_ref.startswith(f"{provider}/"):
        print(f"llmflask: error: --provider {provider} requires a {provider}/... model reference", file=sys.stderr)
        sys.exit(2)
    if not _validate_model_ref(host, port, model_ref, use_server=target):
        return 1
    if args.session is not None and not (target and provider == "server"):
        from .config import DATABASE
        from .database import get_session_for_user
        if get_session_for_user(DATABASE, args.session, args.user) is None:
            print(f"llmflask: error: Session {args.session} not found for user {args.user!r}", file=sys.stderr)
            return 1
    stdout: TextIO = sys.stdout
    output_file = None
    try:
        if args.output:
            output_file = open(args.output, "w", encoding="utf-8")
            stdout = _tee_writer(sys.stdout, output_file)
        if target and provider == "server":
            result = run_server_batch_command(
                question, model_ref, _base_url(host, port),
                prompt_ref=args.prompt, session_id=args.session,
                user=args.user, stdout=stdout, search=args.search,
            )
        else:
            result = run_batch_command(
                question, model_ref, prompt_ref=args.prompt,
                session_id=args.session, user=args.user, stdout=stdout,
            )
        return result
    except ValueError as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        sys.exit(2)
    except Exception as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        if "/" not in args.model and provider == "server":
            print("Hint: Copy model ref from --models, or use --provider for remote APIs.", file=sys.stderr)
            print("  Example: llmflask --cmd --text \"...\" --model deepseek/deepseek-chat", file=sys.stderr)
        elif "api key" in str(error).lower() or "not configured" in str(error).lower():
            print("Hint: Run llmflask --configure-api-keys to set up your API keys.", file=sys.stderr)
        return 1
    finally:
        if output_file:
            output_file.close()


def _handle_tui(args: ParsedArgs, host: str, port: int, target: bool) -> int:
    try:
        provider = _resolve_tui_provider(args.provider, host, port, target)
    except ValueError as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        sys.exit(2)
    if args.prompt:
        try:
            system_prompt = load_prompt(args.prompt)
        except ValueError as error:
            print(f"llmflask: error: {error}", file=sys.stderr)
            sys.exit(2)
    else:
        system_prompt = None
    from .cli import run_tui
    run_tui(host=host, port=port, user=args.user, trace=args.tui_trace,
            provider=provider, system_prompt=system_prompt)
    return 0


def _verify_server_requirements() -> bool:
    from .config import OLLAMA_URL

    if os.getenv("LLMFLASK_SKIP_REQUIREMENTS", "") not in ("", "0"):
        return True
    if ollama_reachable():
        return True
    print(
        f"llmflask: error: Ollama is required but not reachable at {OLLAMA_URL}",
        file=sys.stderr,
    )
    print("  Install:    make install-ai   (or https://ollama.com/download)", file=sys.stderr)
    print("  Start:      systemctl start ollama   (or sudo systemctl enable --now ollama)", file=sys.stderr)
    print("  Verify:     ollama list", file=sys.stderr)
    print("  Override:   OLLAMA_URL env for a non-default endpoint", file=sys.stderr)
    print("  Skip:       LLMFLASK_SKIP_REQUIREMENTS=1 to start without local Ollama", file=sys.stderr)
    return False


def _handle_server(args: ParsedArgs, host: str, port: int) -> int:
    from .app import create_app
    from .config import HOST, PORT
    if not _verify_server_requirements():
        return 2
    os.environ["LLMFLASK_USER"] = args.user
    host = args.host if args.host is not None else HOST
    port = args.port if args.port is not None else PORT
    app = create_app()
    if args.server == "production":
        run_gunicorn(app, host, port)
    else:
        app.run(host=host, port=port, debug=False, threaded=True)
    return 0


_MODE_HANDLERS = {
    "--configure-api-keys": _handle_api_keys,
    "--models":             _handle_models,
    "--usepool":            _handle_usepool,
    "--cmd":                _handle_cmd,
    "--tui":                _handle_tui,
    "--server":             _handle_server,
}


def _dispatch_mode(args: ParsedArgs, host: str, port: int, target: bool) -> int | None:
    handler = _MODE_HANDLERS.get(args.mode) if args.mode else None
    if handler is None:
        return None
    if args.mode == "--server":
        return handler(args, host, port)
    if args.mode == "--configure-api-keys":
        return handler()
    return handler(args, host, port, target)


def main() -> int:
    if len(sys.argv) == 1:
        print_help()
        return 0

    args = parse(list(sys.argv[1:]))

    if args.mode is None:
        print("llmflask: error: No mode selected.", file=sys.stderr)
        print("  Use --server, --tui, --cmd, --usepool, --models,", file=sys.stderr)
        print("  --configure-api-keys, or pool.", file=sys.stderr)
        print_help()
        sys.exit(2)

    explicit_server_target = args.host is not None or args.port is not None
    host = args.host or "127.0.0.1"
    port = args.port or 5000

    if args.command is not None:
        result = _dispatch_management_command(args, host, port)
        if result is not None:
            return result

    result = _dispatch_mode(args, host, port, explicit_server_target)
    if result is not None:
        return result

    print(
        "llmflask: error: No mode selected. Use --server, --tui, --cmd, "
        "--usepool, --models, --configure-api-keys, or pool.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
