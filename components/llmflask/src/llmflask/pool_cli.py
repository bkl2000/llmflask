# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from .cli_http import api_request, iter_pool_events
from .config import MAX_UPLOAD_BYTES, MAX_UPLOAD_FILE_BYTES, MAX_UPLOAD_FILES, RESULT_DIR as DEFAULT_RESULT_DIR, is_safe_name
from .model_discovery import _validate_model_ref, _show_available_models





def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _run_pool_command(args, host: str, port: int) -> int:
    base = _base_url(host, port)
    action = args.pool_action
    result_dir = None if getattr(args, "no_result", False) else (getattr(args, "result_dir", None) or DEFAULT_RESULT_DIR)

    handlers = {
        "list":   lambda: _pool_list(base),
        "show":   lambda: _pool_show(base, args.name),
        "run":    lambda: _pool_run(base, args.name, args.model, result_dir),
        "path":   lambda: _pool_path(base, args.name),
        "pack":   lambda: _pool_pack(base, args.name),
        "remove": lambda: _pool_remove(base, args.name),
        "debug":  lambda: _pool_debug(base, args.name),
    }
    handler = handlers.get(action)
    if handler:
        if action == "run":
            model_ref = getattr(args, "model", "")
            if not model_ref:
                print("llmflask: error: pool run requires --model <MODELREF>", file=sys.stderr)
                _show_available_models(None, host, port, True)
                return 1
            if not _validate_model_ref(host, port, model_ref, use_server=True):
                return 1
        return handler()
    print("llmflask: error: Unknown pool action", file=sys.stderr)
    return 1


@dataclass(frozen=True)
class _UploadFile:
    field_name: str
    path: Path
    filename: str | None


def _collect_upload_files(source: str) -> list[_UploadFile]:
    upload_path = Path(source).expanduser()
    try:
        source_mode = upload_path.lstat().st_mode
    except FileNotFoundError:
        raise ValueError(f"Source not found: {source}") from None

    if stat.S_ISLNK(source_mode):
        raise ValueError(f"Symbolic-link inputs are not allowed: {source}")
    if stat.S_ISREG(source_mode):
        candidates = [_UploadFile("file", upload_path, upload_path.name)]
    elif stat.S_ISDIR(source_mode):
        candidates = []
        for path in upload_path.rglob("*"):
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"Symbolic-link inputs are not allowed: {path}")
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ValueError(f"Special-file inputs are not allowed: {path}")
            relative = path.relative_to(upload_path)
            candidates.append(_UploadFile(f"input/{relative}", path, None))
    else:
        raise ValueError(f"Source is not a regular file or directory: {source}")

    if len(candidates) > MAX_UPLOAD_FILES:
        raise ValueError(f"Upload contains more than {MAX_UPLOAD_FILES} files")

    total_bytes = 0
    for candidate in candidates:
        file_bytes = candidate.path.stat().st_size
        if file_bytes > MAX_UPLOAD_FILE_BYTES:
            raise ValueError(
                f"File exceeds {MAX_UPLOAD_FILE_BYTES} bytes: {candidate.path}"
            )
        total_bytes += file_bytes
        if total_bytes > MAX_UPLOAD_BYTES:
            raise ValueError(f"Upload exceeds {MAX_UPLOAD_BYTES} bytes")

    return candidates


def _download_result(base: str, pool_name: str, result_dir: str) -> Path | None:
    ts = datetime.now(timezone.utc).strftime("%y%m%d-%H%M%S")
    if not is_safe_name(pool_name):
        print(f"llmflask: error: Result download failed: invalid pool name {pool_name!r}", file=sys.stderr)
        return None
    root = Path(result_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    base_name = f"{pool_name}-{ts}"
    target = root / base_name
    counter = 2
    while target.exists() or target.is_symlink():
        target = root / f"{base_name}-{counter}"
        counter += 1
    staging = Path(tempfile.mkdtemp(prefix=".download-", dir=root))

    url = f"{base}/api/pools/{pool_name}/pack?download=1"
    try:
        with httpx.Client(timeout=httpx.Timeout(120, connect=10), follow_redirects=True) as client:
            extract_dir = staging / "extract"
            extract_dir.mkdir()
            with tempfile.NamedTemporaryFile(suffix=".tar.gz") as tmp:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_bytes():
                        tmp.write(chunk)
                tmp.flush()
                with tarfile.open(tmp.name, "r:gz") as tar:
                    for member in tar.getmembers():
                        member_path = Path(member.name)
                        if (
                            member_path.is_absolute()
                            or ".." in member_path.parts
                            or member.issym()
                            or member.islnk()
                            or member.isdev()
                        ):
                            raise ValueError(f"unsafe archive entry: {member.name!r}")
                    tar.extractall(path=extract_dir, filter="data")

            entries = list(extract_dir.iterdir())
            content_root = entries[0] if len(entries) == 1 and entries[0].is_dir() else extract_dir
            prepared = staging / "result"
            prepared.mkdir()
            for item in content_root.iterdir():
                shutil.move(str(item), str(prepared / item.name))
            metadata = prepared / "pool.json"
            if metadata.is_symlink() or not metadata.is_file():
                raise ValueError("downloaded archive does not contain a regular pool.json")
            prepared.rename(target)

            print(f"Results saved to {target}/")
            return target
    except Exception as e:
        print(f"llmflask: error: Result download failed: {e}", file=sys.stderr)
        return None
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _run_pool_cli(
    source: str | None,
    request_text: str,
    model_ref: str,
    host: str,
    port: int,
    pool_name: str | None = None,
    reuse: bool = False,
    result_dir: str | None = None,
) -> int:
    base = _base_url(host, port)
    try:
        upload_files = _collect_upload_files(source) if source is not None else []
    except (OSError, ValueError) as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1

    data: dict[str, str] = {
        "request": request_text,
        "model": model_ref,
    }
    if pool_name:
        data["pool_name"] = pool_name
    if reuse:
        data["reuse"] = "1"

    completed = False
    successful = False
    try:
        with ExitStack() as resources, httpx.Client(
            timeout=httpx.Timeout(600, connect=10)
        ) as client:
            files = {
                upload.field_name: (
                    upload.filename,
                    resources.enter_context(upload.path.open("rb")),
                    "application/octet-stream",
                )
                for upload in upload_files
            }
            with client.stream(
                "POST",
                f"{base}/api/pool",
                data=data,
                files=files,
            ) as resp:
                resp.raise_for_status()
                for event in iter_pool_events(resp):
                    status = event.get("status", "")
                    if status == "error":
                        print(f"llmflask: error: {event.get('message', 'Unknown error')}", file=sys.stderr)
                        return 1
                    if status == "done":
                        completed = True
                        successful = bool(event.get("success"))
                        downloaded = None
                        if result_dir is not None:
                            downloaded = _download_result(base, event.get("pool_name", "pool"), result_dir)
                            if downloaded is None:
                                return 1
                        _print_pool_result(
                            event,
                            model_ref,
                            downloaded.name if downloaded else None,
                        )
                    elif status == "pool_created":
                        print(f"Pool: {event.get('pool_name', '?')}")
                    elif status == "generated":
                        print(f"Generated files:\n{event.get('files', '')}")
                    elif status in ("creating_pool", "generating", "running", "repairing"):
                        print(event.get("message", ""))
    except httpx.ConnectError:
        print(f"llmflask: error: No server at {base}.", file=sys.stderr)
        print("Pool commands require a running LLMFlask server.", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1

    if not completed:
        print("llmflask: error: Pool stream ended before a done event.", file=sys.stderr)
        return 1
    return 0 if successful else 1


def _print_pool_result(event: dict, model_ref: str, result_name: str | None = None) -> None:
    success = event.get("success", False)
    status = "success" if success else "failed"
    print(f"\nStatus: {status}")
    if event.get("duration_ms"):
        print(f"Duration: {event['duration_ms']} ms")
    if event.get("stdout"):
        print(f"\n--- stdout ---\n{event['stdout']}")
    if event.get("stderr"):
        print(f"\n--- stderr ---\n{event['stderr']}")
    pool_name = event.get("pool_name", "?")
    print(f"\nRe-run pool:")
    print(f"  llmflask pool run {pool_name} --model {model_ref}")
    print(f"  llmflask pool debug {pool_name}")
    if result_name:
        print(f"\nInspect downloaded result:")
        print(f"  llmflask result inspect {result_name}")
        if success:
            print(f"  llmflask result run {result_name}")
    elif success:
        print("\nResult download was disabled.")
    else:
        print("\nInspect the server pool with:")
        print(f"  llmflask pool debug {pool_name}")


def _pool_list(base: str) -> int:
    resp = api_request(base, "GET", "/api/pools")
    if resp is None:
        return 1
    pools = resp.json()
    if not pools:
        print("No pools found.")
        return 0
    print(f"{'NAME':<30} {'CREATED':<20} {'LAST RUN':<15}")
    for p in pools:
        name = p.get("name", "")[:28]
        created = (p.get("created_at", "") or "")[:19]
        last = ""
        last_run = p.get("last_run")
        if last_run:
            last = "OK" if last_run.get("success") else "ERROR"
        print(f"{name:<30} {created:<20} {last:<15}")
    return 0


def _pool_show(base: str, name: str) -> int:
    resp = api_request(base, "GET", f"/api/pools/{name}")
    if resp is None:
        return 1
    info = resp.json()
    meta = info.get("meta", {})
    files = info.get("files", {})

    print(f"Pool: {name}")
    print(f"Input: {meta.get('source_path', '?')}")
    last = meta.get("last_run")
    if last:
        print(f"Last run: {last.get('timestamp', '')} — {'OK' if last.get('success') else 'ERROR'}")
        if last.get("repair_count"):
            print(f"Repair attempts: {last['repair_count']}")

    for section in ("input", "scripts", "output", "logs"):
        section_files = files.get(section, [])
        if section_files:
            print(f"\n{section}/:")
            for f_name in section_files[:20]:
                print(f"  {f_name}")
            if len(section_files) > 20:
                print(f"  ... ({len(section_files) - 20} more)")
    return 0


def _pool_run(base: str, name: str, model_ref: str, result_dir: str | None = None) -> int:
    completed = False
    successful = False
    try:
        with httpx.Client(timeout=httpx.Timeout(600, connect=10)) as client:
            with client.stream(
                "POST",
                f"{base}/api/pools/{name}/run",
                json={"model": model_ref},
            ) as resp:
                resp.raise_for_status()
                for event in iter_pool_events(resp):
                    if event.get("status") == "error":
                        print(f"llmflask: error: {event.get('message', 'Unknown error')}", file=sys.stderr)
                        return 1
                    if event.get("status") == "done":
                        completed = True
                        successful = bool(event.get("success"))
                        downloaded = None
                        if result_dir is not None:
                            downloaded = _download_result(base, name, result_dir)
                            if downloaded is None:
                                return 1
                        _print_pool_result(event, model_ref, downloaded.name if downloaded else None)
                    else:
                        print(event.get("message", ""))
        if not completed:
            print("llmflask: error: Pool stream ended before a done event.", file=sys.stderr)
            return 1
        return 0 if successful else 1
    except httpx.ConnectError:
        print(f"llmflask: error: No server at {base} reachable.", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1


def _pool_debug(base: str, name: str) -> int:
    resp = api_request(base, "GET", f"/api/pools/{name}/debug", timeout=30)
    if resp is None:
        return 1
    data = resp.json()
    meta = data.get("meta", {})
    files = data.get("files", {})
    contents = data.get("contents", {})

    print(f"=== Pool: {name} ===")
    last = meta.get("last_run", {}) or {}
    if last:
        print(f"Last run: {last.get('success', '?')} | exit={last.get('exit_code', '?')} | {last.get('duration_ms', 0)} ms")

    for section in ("input", "scripts", "output", "logs"):
        section_files = files.get(section, [])
        if section_files:
            print(f"\n--- {section}/ ---")
            for f_name in section_files:
                print(f"  {f_name}")

    if contents:
        print(f"\n--- FILE CONTENTS ---")
    for path, text in sorted(contents.items()):
        print(f"\n=== {path} ===")
        print(text[:2000])
    return 0


def _pool_path(base: str, name: str) -> int:
    resp = api_request(base, "GET", f"/api/pools/{name}")
    if resp is None:
        return 1
    info = resp.json()
    meta = info.get("meta", {})
    source = meta.get("source_path", "?")
    print(f"Pool path (server-side): {source}")
    print("Use SSH to access the server for direct shell access.")
    return 0


def _pool_pack(base: str, name: str) -> int:
    resp = api_request(base, "GET", f"/api/pools/{name}/pack", timeout=60)
    if resp is None:
        return 1
    result = resp.json()
    print(f"Archive created: {result.get('archive', result.get('error', '?'))}")
    return 0


def _pool_remove(base: str, name: str | None) -> int:
    if name in (None, "all"):
        return _pool_remove_all(base)
    if name == "failed":
        return _pool_remove_failed(base)
    resp = api_request(base, "DELETE", f"/api/pools/{name}")
    if resp is None:
        return 1
    result = resp.json()
    print(f"Pool deleted: {result.get('pool_name', name)}")
    return 0


def _pool_remove_all(base: str) -> int:
    resp = api_request(base, "DELETE", "/api/pools")
    if resp is None:
        return 1
    result = resp.json()
    count = result.get("count", 0)
    print(f"Deleted {count} pool{'s' if count != 1 else ''}.")
    return 0


def _pool_remove_failed(base: str) -> int:
    resp = api_request(base, "GET", "/api/pools")
    if resp is None:
        return 1
    pools = resp.json()
    count = 0
    failed = False
    for p in pools:
        last = p.get("last_run")
        if last and not last.get("success"):
            if api_request(base, "DELETE", f"/api/pools/{quote(p['name'], safe='')}") is not None:
                count += 1
            else:
                failed = True
    print(f"Deleted {count} failed pool{'s' if count != 1 else ''}.")
    return 1 if failed else 0
