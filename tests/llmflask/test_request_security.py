# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

import pytest

from llmflask import config
from llmflask.app import create_app


@pytest.fixture
def app_factory(tmp_path, monkeypatch):
    counter = 0

    def make_app(*, trusted_hosts=""):
        nonlocal counter
        counter += 1
        monkeypatch.setattr(config, "DATABASE", str(tmp_path / f"test-{counter}.db"))
        monkeypatch.setattr(config, "TRUSTED_HOSTS", trusted_hosts)
        app = create_app()
        app.config["TESTING"] = True
        return app

    return make_app


def test_trusted_hosts_default_to_loopback_only(app_factory):
    app = app_factory()

    assert app.config["LLMFLASK_TRUSTED_HOSTS"] == frozenset(
        {"localhost", "127.0.0.1", "::1"}
    )

    client = app.test_client()
    for host in ("localhost", "localhost:5000", "127.0.0.1", "[::1]:5000"):
        assert client.get("/", headers={"Host": host}).status_code == 200


def test_configured_trusted_hosts_extend_loopback_defaults(app_factory):
    app = app_factory(trusted_hosts="server.example.test, 192.0.2.40")

    assert app.config["LLMFLASK_TRUSTED_HOSTS"] == frozenset(
        {"localhost", "127.0.0.1", "::1", "server.example.test", "192.0.2.40"}
    )

    client = app.test_client()
    assert client.get("/", headers={"Host": "server.example.test:5000"}).status_code == 200
    assert client.get("/", headers={"Host": "192.0.2.40:5000"}).status_code == 200


@pytest.mark.parametrize(
    "trusted_hosts",
    [
        "https://server.example.test",
        "server.example.test/path",
        "user@server.example.test",
        "*.example.test",
        "bad host",
    ],
)
def test_invalid_trusted_host_configuration_fails_at_startup(
    app_factory, trusted_hosts
):
    with pytest.raises(ValueError, match="LLMFLASK_TRUSTED_HOSTS"):
        app_factory(trusted_hosts=trusted_hosts)


@pytest.mark.parametrize("host", ["untrusted.example.test", "bad host"])
def test_untrusted_or_malformed_request_host_is_rejected(app_factory, host):
    client = app_factory().test_client()

    response = client.get("/", headers={"Host": host})

    assert response.status_code == 400
    assert "host" in response.get_json()["error"].lower()


@pytest.mark.parametrize("marker", [None, "", "0", "true", " 1", "1 "])
def test_unsafe_api_request_requires_exact_marker(app_factory, marker):
    client = app_factory().test_client()
    headers = {} if marker is None else {"X-LLMFlask-Request": marker}

    response = client.post(
        "/api/sessions?user=test",
        json={"title": "Test", "model": "ollama/qwen3:8b"},
        headers=headers,
    )

    assert response.status_code == 403


def test_exact_request_marker_allows_unsafe_api_request(app_factory):
    client = app_factory().test_client()

    response = client.post(
        "/api/sessions?user=test",
        json={"title": "Test", "model": "ollama/qwen3:8b"},
        headers={"X-LLMFlask-Request": "1"},
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/sessions"),
        ("PUT", "/api/sessions/999"),
        ("PATCH", "/api/sessions/999"),
        ("DELETE", "/api/sessions/999"),
    ],
)
def test_all_unsafe_api_methods_are_guarded(app_factory, method, path):
    client = app_factory().test_client()

    response = client.open(path, method=method, json={"title": "Test"})

    assert response.status_code == 403


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_safe_api_methods_do_not_require_request_marker(app_factory, method):
    client = app_factory().test_client()

    response = client.open(
        "/api/sessions",
        method=method,
        headers={"Origin": "https://different.example.test"},
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "origin",
    [
        "http://different.example.test:5000",
        "http://localhost:5001",
        "https://localhost:5000",
        "not-an-origin",
        "null",
        "http://user@localhost:5000",
    ],
)
def test_unsafe_api_request_rejects_mismatched_or_malformed_origin(
    app_factory, origin
):
    client = app_factory().test_client()

    response = client.post(
        "/api/sessions?user=test",
        json={"title": "Test", "model": "ollama/qwen3:8b"},
        headers={
            "Host": "localhost:5000",
            "Origin": origin,
            "X-LLMFlask-Request": "1",
        },
    )

    assert response.status_code == 403
    assert "origin" in response.get_json()["error"].lower()


@pytest.mark.parametrize(
    ("base_url", "origin"),
    [
        ("http://localhost:5000", "http://localhost:5000"),
        ("https://localhost:5000", "https://localhost:5000"),
    ],
)
def test_unsafe_api_request_accepts_matching_origin(app_factory, base_url, origin):
    client = app_factory().test_client()

    response = client.post(
        "/api/sessions?user=test",
        base_url=base_url,
        json={"title": "Test", "model": "ollama/qwen3:8b"},
        headers={
            "Origin": origin,
            "X-LLMFlask-Request": "1",
        },
    )

    assert response.status_code == 201


def test_workbench_is_disabled_by_default(app_factory, monkeypatch):
    monkeypatch.setattr("llmflask.routes.workbench.WORKBENCH_ENABLED", False)
    client = app_factory().test_client()

    response = client.get("/api/pools")

    assert response.status_code == 403
    assert "Workbench is disabled" in response.get_json()["error"]
