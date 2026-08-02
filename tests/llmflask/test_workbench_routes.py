# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import pytest
from llmflask.app import create_app
import json
from pathlib import Path


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("llmflask.config.DATABASE", db_path)
    monkeypatch.setattr("llmflask.routes.workbench.POOL_ROOT", str(tmp_path / "pools"))
    monkeypatch.setattr(
        "llmflask.routes.workbench.POOL_ARCHIVE_ROOT", str(tmp_path / "archives")
    )
    app = create_app()
    app.config["DB_PATH"] = db_path
    with app.app_context():
        from llmflask.database import init_db
        init_db(db_path)
    with app.test_client() as c:
        yield c


def test_pools_list_empty(client):
    resp = client.get("/api/pools")
    assert resp.status_code == 200
    assert resp.json == []


def test_pool_not_found(client):
    resp = client.get("/api/pools/nonexistent")
    assert resp.status_code == 404


def test_pool_create_no_request(client):
    resp = client.post("/api/pool", data={})
    assert resp.status_code == 400


def test_pool_create_requires_explicit_model(client):
    resp = client.post("/api/pool", data={"request": "test"})
    assert resp.status_code == 400
    assert "model" in resp.get_json()["error"]


def test_pool_delete_not_found(client):
    resp = client.delete("/api/pools/nonexistent")
    assert resp.status_code == 404


def test_pool_delete_all_empty(client):
    resp = client.delete("/api/pools")
    assert resp.status_code == 200
    assert resp.json == {"count": 0, "failed": []}


def test_pool_debug_endpoint(client):
    resp = client.get("/api/pools/nonexistent/debug")
    assert resp.status_code == 404


def test_pool_list_resilient_to_empty_pools(client):
    resp = client.get("/api/pools")
    assert resp.status_code == 200
    assert resp.json == []


def test_pool_create_rejects_traversal_filename(client):
    import io

    resp = client.post(
        "/api/pool",
        data={
            "request": "test",
            "model": "ollama/qwen3:8b",
            "file": (io.BytesIO(b"data"), "../escape.txt"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_pool_create_rejects_file_over_limit(client, monkeypatch):
    import io

    monkeypatch.setattr("llmflask.routes.workbench.MAX_UPLOAD_FILE_BYTES", 3)
    resp = client.post(
        "/api/pool",
        data={
            "request": "test",
            "model": "ollama/qwen3:8b",
            "file": (io.BytesIO(b"four"), "data.txt"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 413
    assert "limit" in resp.get_json()["error"].lower()


def test_pool_create_rejects_too_many_files(client, monkeypatch):
    import io

    monkeypatch.setattr("llmflask.routes.workbench.MAX_UPLOAD_FILES", 1)
    resp = client.post(
        "/api/pool",
        data={
            "request": "test",
            "model": "ollama/qwen3:8b",
            "a.txt": (io.BytesIO(b"a"), "a.txt"),
            "b.txt": (io.BytesIO(b"b"), "b.txt"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 413


def test_debug_and_pack_reject_output_symlink(client, tmp_path):
    from llmflask.workbench.pool_manager import PoolManager

    source = tmp_path / "source.txt"
    source.write_text("input")
    manager = PoolManager(str(tmp_path / "pools"))
    name = manager.create(str(source), pool_name="unsafe-pool")
    secret = tmp_path / "host-secret.txt"
    secret.write_text("host secret")
    (tmp_path / "pools" / name / "output" / "leak").symlink_to(secret)

    debug = client.get(f"/api/pools/{name}/debug")
    packed = client.get(f"/api/pools/{name}/pack")
    assert debug.status_code == 422
    assert packed.status_code == 422
    assert b"host secret" not in debug.data


def test_debug_omits_oversized_file_content(client, tmp_path, monkeypatch):
    from llmflask.workbench.pool_manager import PoolManager
    from llmflask.routes import workbench

    source = tmp_path / "source.txt"
    source.write_text("input", encoding="utf-8")
    name = PoolManager(str(tmp_path / "pools")).create(
        str(source), pool_name="large-debug"
    )
    large_log = tmp_path / "pools" / name / "logs" / "llm_response.txt"
    large_log.write_text("secret-payload", encoding="utf-8")
    monkeypatch.setattr(workbench, "_MAX_DEBUG_FILE_BYTES", 3)

    response = client.get(f"/api/pools/{name}/debug")

    assert response.status_code == 200
    contents = response.get_json()["contents"]
    assert contents["logs/llm_response.txt"].startswith("(content omitted,")
    assert "secret-payload" not in response.get_data(as_text=True)


def test_total_upload_limit_returns_json_413(client):
    client.application.config["MAX_CONTENT_LENGTH"] = 32
    resp = client.post("/api/pool", data={"payload": "x" * 100})
    assert resp.status_code == 413
    assert "limit" in resp.get_json()["error"].lower()


def test_workbench_factory_forwards_all_sandbox_limits(monkeypatch):
    from llmflask.routes import workbench

    captured = {}

    class FakeWorkbench:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(workbench, "Workbench", FakeWorkbench)
    monkeypatch.setattr(workbench, "SANDBOX_MAX_STDOUT", 11)
    monkeypatch.setattr(workbench, "SANDBOX_MAX_STDERR", 12)
    monkeypatch.setattr(workbench, "SANDBOX_MAX_ARTIFACTS", 13)
    monkeypatch.setattr(workbench, "SANDBOX_MAX_ARTIFACT_BYTES", 14)

    workbench._get_workbench()

    assert captured["max_stdout"] == 11
    assert captured["max_stderr"] == 12
    assert captured["max_artifacts"] == 13
    assert captured["max_artifact_bytes"] == 14


def test_delete_all_reports_partial_failure(client, tmp_path, monkeypatch):
    from llmflask.workbench.pool_manager import PoolManager

    source = tmp_path / "source.txt"
    source.write_text("input")
    manager = PoolManager(str(tmp_path / "pools"))
    manager.create(str(source), pool_name="ok")
    manager.create(str(source), pool_name="broken")
    real_remove = PoolManager.remove

    def fail_one(self, name):
        if name == "broken":
            raise OSError("busy")
        return real_remove(self, name)

    monkeypatch.setattr(PoolManager, "remove", fail_one)
    resp = client.delete("/api/pools")
    assert resp.status_code == 500
    assert resp.json["count"] == 1
    assert resp.json["failed"][0]["name"] == "broken"


def test_pack_uses_controlled_root_and_download_is_removed(client, tmp_path):
    from llmflask.workbench.pool_manager import PoolManager

    source = tmp_path / "source.txt"
    source.write_text("input")
    PoolManager(str(tmp_path / "pools")).create(
        str(source), pool_name="archive-pool"
    )

    packed = client.get("/api/pools/archive-pool/pack")
    assert packed.status_code == 200
    archive_path = Path(packed.json["archive"])
    assert archive_path.parent == tmp_path / "archives"
    assert archive_path.is_file()

    downloaded = client.get("/api/pools/archive-pool/pack?download=1")
    assert downloaded.status_code == 200
    assert downloaded.data
    downloaded.close()
    assert not set((tmp_path / "archives").glob("archive-pool-*.tar.gz"))
