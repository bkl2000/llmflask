# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
import os
import tempfile
import shutil
from pathlib import Path

from flask import Blueprint, Response, after_this_request, current_app, request, jsonify, send_file
from werkzeug.exceptions import RequestEntityTooLarge

from ..config import (
    WORKBENCH_ENABLED,
    POOL_ROOT,
    SANDBOX_IMAGE,
    SANDBOX_TIMEOUT,
    SANDBOX_MEMORY,
    SANDBOX_CPUS,
    SANDBOX_PIDS_LIMIT,
    SANDBOX_REPAIR_ATTEMPTS,
    SANDBOX_MAX_STDOUT,
    SANDBOX_MAX_STDERR,
    SANDBOX_MAX_ARTIFACTS,
    SANDBOX_MAX_ARTIFACT_BYTES,
    SANDBOX_MAX_TOTAL_ARTIFACT_BYTES,
    MAX_UPLOAD_FILE_BYTES,
    MAX_UPLOAD_FILES,
    POOL_ARCHIVE_ROOT,
)
from ..workbench.orchestrator import Workbench
from ..workbench.pool_manager import PoolManager, UnsafePoolError

workbench_bp = Blueprint("workbench_routes", __name__)
_MAX_DEBUG_FILE_BYTES = 100_000


def _save_stream_limited(file_storage, destination: Path) -> None:
    written = 0
    with destination.open("wb") as output:
        while chunk := file_storage.stream.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_FILE_BYTES:
                raise RequestEntityTooLarge(
                    description=f"File exceeds {MAX_UPLOAD_FILE_BYTES} bytes"
                )
            output.write(chunk)


def _get_workbench() -> Workbench:
    return Workbench(
        pool_root=POOL_ROOT,
        sandbox_image=SANDBOX_IMAGE,
        sandbox_timeout=SANDBOX_TIMEOUT,
        sandbox_memory=SANDBOX_MEMORY,
        sandbox_cpus=SANDBOX_CPUS,
        sandbox_pids_limit=SANDBOX_PIDS_LIMIT,
        repair_attempts=SANDBOX_REPAIR_ATTEMPTS,
        max_stdout=SANDBOX_MAX_STDOUT,
        max_stderr=SANDBOX_MAX_STDERR,
        max_artifacts=SANDBOX_MAX_ARTIFACTS,
        max_artifact_bytes=SANDBOX_MAX_ARTIFACT_BYTES,
        max_total_artifact_bytes=SANDBOX_MAX_TOTAL_ARTIFACT_BYTES,
    )


def _debug_file_contents(pool_dir: Path) -> dict[str, str]:
    candidates: list[Path] = []
    for subdirectory in ("input", "scripts", "output", "logs"):
        root = pool_dir / subdirectory
        if root.is_dir():
            candidates.extend(
                path for path in sorted(root.rglob("*")) if path.is_file()
            )
    run_script = pool_dir / "run.sh"
    if run_script.is_file():
        candidates.append(run_script)

    contents: dict[str, str] = {}
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or len(contents) >= SANDBOX_MAX_ARTIFACTS:
            continue
        seen.add(path)
        relative = str(path.relative_to(pool_dir))
        file_bytes = path.stat().st_size
        if file_bytes > _MAX_DEBUG_FILE_BYTES:
            contents[relative] = f"(content omitted, {file_bytes} bytes)"
            continue
        try:
            contents[relative] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            contents[relative] = f"(binary, {file_bytes} bytes)"
    return contents


def _save_uploaded_file() -> tuple[str, str]:
    if "file" not in request.files:
        raise ValueError("No file uploaded (field 'file')")

    uploaded = request.files["file"]
    if not uploaded.filename:
        raise ValueError("Empty filename")

    filename = Path(uploaded.filename)
    if filename.is_absolute() or len(filename.parts) != 1 or filename.name in (".", ".."):
        raise ValueError("Invalid upload filename")
    tmp_dir = tempfile.mkdtemp(prefix="llmflask-pool-upload-")
    file_path = Path(tmp_dir) / filename.name
    try:
        _save_stream_limited(uploaded, file_path)
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return str(file_path), tmp_dir


def _save_uploaded_directory() -> tuple[str, str]:
    tmp_dir = tempfile.mkdtemp(prefix="llmflask-pool-upload-")
    uploaded_files = list(request.files.items(multi=True))
    if len(uploaded_files) > MAX_UPLOAD_FILES:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RequestEntityTooLarge(
            description=f"Upload contains more than {MAX_UPLOAD_FILES} files"
        )
    seen_paths = set()
    for key, file_storage in uploaded_files:
        rel_path = Path(key)
        if rel_path.is_absolute() or ".." in rel_path.parts or rel_path in (Path("."), Path("..")):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ValueError(f"Invalid upload path: {key!r}")
        if rel_path in seen_paths:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ValueError(f"Duplicate upload path: {key!r}")
        seen_paths.add(rel_path)
        dest = Path(tmp_dir) / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            _save_stream_limited(file_storage, dest)
        except BaseException:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

    if not any(Path(tmp_dir).iterdir()):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError("No files uploaded")
    return tmp_dir, tmp_dir


@workbench_bp.route("/pool", methods=["POST"])
def create_pool():
    if not WORKBENCH_ENABLED:
        return jsonify({"error": "Workbench is disabled"}), 403

    model_ref = request.form.get("model", "")
    user_request = request.form.get("request", "")
    pool_name = request.form.get("pool_name") or None
    reuse = request.form.get("reuse", "").lower() in ("1", "true", "yes")

    if not user_request.strip() or not model_ref.strip():
        return jsonify({"error": "Fields 'request' and 'model' are required"}), 400

    tmp_dir = None
    try:
        upload_count = sum(len(values) for _key, values in request.files.lists())
        if upload_count > MAX_UPLOAD_FILES:
            raise RequestEntityTooLarge(
                description=f"Upload contains more than {MAX_UPLOAD_FILES} files"
            )
        if "file" in request.files:
            if upload_count != 1:
                raise ValueError("Field 'file' cannot be combined with directory uploads")
            source_path, tmp_dir = _save_uploaded_file()
        elif request.files:
            source_path, tmp_dir = _save_uploaded_directory()
        else:
            tmp_dir = tempfile.mkdtemp(prefix="llmflask-pool-empty-")
            source_path = tmp_dir

        wb = _get_workbench()

        def generate():
            try:
                for event in wb.execute(source_path, user_request, model_ref, pool_name, reuse):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
            finally:
                if tmp_dir and os.path.isdir(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
            },
        )
    except RequestEntityTooLarge:
        if tmp_dir and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except ValueError as e:
        if tmp_dir and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        if tmp_dir and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500


@workbench_bp.route("/pools", methods=["GET", "DELETE"])
def list_pools():
    if not WORKBENCH_ENABLED:
        return jsonify({"error": "Workbench is disabled"}), 403

    if request.method == "DELETE":
        mgr = PoolManager(POOL_ROOT)
        pools = mgr.list_pools()
        count = len(pools)
        failed = []
        for p in pools:
            try:
                mgr.remove(p["name"])
            except Exception as exc:
                failed.append({"name": p["name"], "error": str(exc)})
        deleted = count - len(failed)
        payload = {"count": deleted, "failed": failed}
        return jsonify(payload), (500 if failed else 200)

    mgr = PoolManager(POOL_ROOT)
    return jsonify(mgr.list_pools())


@workbench_bp.route("/pools/<name>", methods=["GET"])
def pool_info(name):
    if not WORKBENCH_ENABLED:
        return jsonify({"error": "Workbench is disabled"}), 403

    wb = _get_workbench()
    try:
        return jsonify(wb.pool_info(name))
    except UnsafePoolError as e:
        return jsonify({"error": str(e)}), 422
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 404


@workbench_bp.route("/pools/<name>/run", methods=["POST"])
def rerun_pool(name):
    if not WORKBENCH_ENABLED:
        return jsonify({"error": "Workbench is disabled"}), 403

    data = request.get_json(silent=True) or {}
    model_ref = data.get("model", "")
    if not model_ref.strip():
        return jsonify({"error": "Field 'model' is required"}), 400

    wb = _get_workbench()
    try:
        wb.pool_manager.validate(name)
    except UnsafePoolError as e:
        return jsonify({"error": str(e)}), 422
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 404

    def generate():
        try:
            for event in wb.run_pool(name, model_ref):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )


@workbench_bp.route("/pools/<name>/pack", methods=["GET"])
def pack_pool(name):
    if not WORKBENCH_ENABLED:
        return jsonify({"error": "Workbench is disabled"}), 403

    without_input = request.args.get("without_input", "").lower() in ("1", "true", "yes")
    as_download = request.args.get("download", "").lower() in ("1", "true", "yes")
    wb = _get_workbench()
    try:
        wb.pool_manager.validate(name)
        archive_root = Path(POOL_ARCHIVE_ROOT).expanduser().resolve()
        archive_root.mkdir(parents=True, exist_ok=True)
        if as_download:
            fd, temporary_name = tempfile.mkstemp(
                prefix=f"{name}-", suffix=".tar.gz", dir=archive_root
            )
            os.close(fd)
            Path(temporary_name).unlink(missing_ok=True)
            archive_path = wb.pack_pool(
                name, without_input=without_input, output=temporary_name
            )
        else:
            archive_path = wb.pack_pool(
                name,
                without_input=without_input,
                output=str(archive_root / f"{name}.tar.gz"),
            )
        if as_download:
            @after_this_request
            def remove_temporary_archive(response):
                Path(archive_path).unlink(missing_ok=True)
                return response

            response = send_file(
                os.path.abspath(archive_path),
                mimetype="application/gzip",
                as_attachment=True,
                download_name=f"{name}.tar.gz",
            )
            return response
        return jsonify({"archive": archive_path})
    except UnsafePoolError as e:
        return jsonify({"error": str(e)}), 422
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 404


@workbench_bp.route("/pools/<name>/debug", methods=["GET"])
def debug_pool(name):
    if not WORKBENCH_ENABLED:
        return jsonify({"error": "Workbench is disabled"}), 403

    wb = _get_workbench()
    try:
        pool_dir = wb.pool_manager.validate(name)
        info = wb.pool_info(name)

        files_content = _debug_file_contents(pool_dir)

        return jsonify(
            {
                "name": name,
                "meta": info.get("meta", {}),
                "files": info.get("files", {}),
                "contents": files_content,
            }
        )
    except UnsafePoolError as e:
        return jsonify({"error": str(e)}), 422
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 404


@workbench_bp.route("/pools/<name>", methods=["DELETE"])
def delete_pool(name):
    if not WORKBENCH_ENABLED:
        return jsonify({"error": "Workbench is disabled"}), 403

    wb = _get_workbench()
    try:
        wb.remove_pool(name)
        return jsonify({"status": "deleted", "pool_name": name})
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 404
