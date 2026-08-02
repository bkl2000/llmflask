# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors

import pytest

from llmflask import config
from llmflask.app import create_app


@pytest.fixture
def app_factory(tmp_path, monkeypatch):
    counter = 0

    def make_app(*, trusted_hosts="", bind_address="127.0.0.1", extra_trusted=None):
        nonlocal counter
        counter += 1
        monkeypatch.setattr(config, "DATABASE", str(tmp_path / f"test-{counter}.db"))
        monkeypatch.setattr(config, "TRUSTED_HOSTS", trusted_hosts)
        app = create_app(bind_address=bind_address, extra_trusted=extra_trusted)
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


# --- LAN-UX-01: --listen and --trusted-host ---

def test_default_bind_trusts_loopback_only(app_factory):
    app = app_factory()
    assert app.config["LLMFLASK_TRUSTED_HOSTS"] == frozenset({"localhost", "127.0.0.1", "::1"})
    client = app.test_client()
    for host in ("localhost", "127.0.0.1", "[::1]:5000"):
        assert client.get("/", headers={"Host": host}).status_code == 200


def test_specific_ipv4_bind_auto_trusts_that_ip(app_factory):
    app = app_factory(bind_address="192.0.2.5")
    assert "192.0.2.5" in app.config["LLMFLASK_TRUSTED_HOSTS"]


def test_specific_ipv4_trusts_loopback_too(app_factory):
    app = app_factory(bind_address="192.0.2.5")
    trusted = app.config["LLMFLASK_TRUSTED_HOSTS"]
    assert "127.0.0.1" in trusted
    assert "::1" in trusted
    assert "localhost" in trusted


def test_specific_ipv4_rejects_dns_names(app_factory):
    app = app_factory(bind_address="192.0.2.5")
    client = app.test_client()
    resp = client.get("/", headers={"Host": "server.example.test"})
    assert resp.status_code == 400


def test_ipv4_wildcard_permits_ip_literal_hosts(app_factory):
    app = app_factory(bind_address="0.0.0.0")
    client = app.test_client()
    assert client.get("/", headers={"Host": "192.0.2.5:5000"}).status_code == 200
    assert client.get("/", headers={"Host": "198.51.100.10"}).status_code == 200


def test_ipv4_wildcard_rejects_dns_names(app_factory):
    app = app_factory(bind_address="0.0.0.0")
    client = app.test_client()
    resp = client.get("/", headers={"Host": "myhost.local"})
    assert resp.status_code == 400


def test_ipv6_wildcard_permits_ipv6_literal_hosts(app_factory):
    app = app_factory(bind_address="::")
    client = app.test_client()
    assert client.get("/", headers={"Host": "[::1]:5000"}).status_code == 200
    assert client.get("/", headers={"Host": "[2001:db8::1]:5000"}).status_code == 200


def test_ipv6_wildcard_rejects_dns_names(app_factory):
    app = app_factory(bind_address="::")
    client = app.test_client()
    resp = client.get("/", headers={"Host": "myhost.local"})
    assert resp.status_code == 400


def test_ipv6_link_local_permitted_on_wildcard(app_factory):
    app = app_factory(bind_address="::")
    client = app.test_client()
    assert client.get("/", headers={"Host": "[fe80::1]:5000"}).status_code == 200


def test_ipv6_link_local_rejected_on_loopback(app_factory):
    app = app_factory(bind_address="::1")
    client = app.test_client()
    resp = client.get("/", headers={"Host": "[fe80::1]:5000"})
    assert resp.status_code == 400


def test_configured_trusted_host_adds_to_auto_trust(app_factory):
    app = app_factory(trusted_hosts="lan-host.local", bind_address="192.0.2.5")
    trusted = app.config["LLMFLASK_TRUSTED_HOSTS"]
    assert "lan-host.local" in trusted
    assert "192.0.2.5" in trusted


def test_cli_trusted_hosts_are_normalized_and_merged(app_factory):
    app = app_factory(
        trusted_hosts="service.internal",
        bind_address="192.0.2.5",
        extra_trusted=frozenset({"LAN-HOST.Local."}),
    )
    assert app.config["LLMFLASK_TRUSTED_HOSTS"] >= {
        "service.internal",
        "192.0.2.5",
        "lan-host.local",
    }


def test_invalid_cli_trusted_host_fails_at_startup(app_factory):
    with pytest.raises(ValueError, match="--trusted-host"):
        app_factory(extra_trusted=frozenset({"https://lan-host.local"}))


def test_loopback_bind_rejects_lan_ip_literal(app_factory):
    app = app_factory(bind_address="127.0.0.1")
    client = app.test_client()
    resp = client.get("/", headers={"Host": "192.0.2.5"})
    assert resp.status_code == 400


def test_rejected_host_response_names_the_rejected_value(app_factory):
    app = app_factory()
    client = app.test_client()
    resp = client.get("/", headers={"Host": "evil.example.test"})
    assert resp.status_code == 400
    body = resp.get_json()["error"]
    assert "evil.example.test" in body


def test_rejected_host_suggests_trusted_host_flag(app_factory):
    app = app_factory(bind_address="127.0.0.1")
    client = app.test_client()
    resp = client.get("/", headers={"Host": "mybox.local"})
    assert resp.status_code == 400
    body = resp.get_json()["error"].lower()
    assert "trusted" in body or "trusted-host" in body

    resp2 = client.get("/", headers={"Host": "evil.example.test"})
    assert resp2.status_code == 400
    body2 = resp2.get_json()["error"]
    assert "evil.example.test" in body2
