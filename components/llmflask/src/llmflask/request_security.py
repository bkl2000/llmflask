# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
"""Request-boundary checks for the trusted local LLMFlask server."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from urllib.parse import urlsplit

from flask import Flask, jsonify, request


UNSAFE_API_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
REQUEST_HEADER_NAME = "X-LLMFlask-Request"
REQUEST_HEADER_VALUE = "1"
DEFAULT_TRUSTED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_HOST_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _normalize_hostname(value: str) -> str:
    hostname = value.strip().lower().rstrip(".")
    if not hostname:
        raise ValueError("host is empty")
    try:
        return ipaddress.ip_address(hostname).compressed
    except ValueError:
        pass
    if len(hostname) > 253 or any(
        not _HOST_LABEL_RE.fullmatch(label) for label in hostname.split(".")
    ):
        raise ValueError(f"invalid hostname {value!r}")
    return hostname


def _parse_exact_hosts(values: Iterable[str], source: str) -> frozenset[str]:
    trusted: set[str] = set()
    for raw_entry in values:
        entry = raw_entry.strip()
        if not entry:
            continue
        if any(marker in entry for marker in ("://", "/", "@", "*")):
            raise ValueError(
                f"{source} entries must be exact hostnames or IP addresses "
                "without a scheme, path, port, user information, or wildcard"
            )
        try:
            trusted.add(_normalize_hostname(entry))
        except ValueError as error:
            raise ValueError(
                f"Invalid {source} entry {entry!r}: {error}"
            ) from error
    return frozenset(trusted)


def parse_trusted_hosts(configured: str) -> frozenset[str]:
    """Return built-in loopback hosts plus validated configured hostnames/IPs."""
    configured_hosts = _parse_exact_hosts(
        configured.split(","), "LLMFLASK_TRUSTED_HOSTS"
    )
    return DEFAULT_TRUSTED_HOSTS | configured_hosts


def _parse_authority(authority: str, scheme: str) -> tuple[str, int | None]:
    if not authority or any(character.isspace() for character in authority):
        raise ValueError("authority is empty or malformed")
    parsed = urlsplit(f"//{authority}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("user information is not allowed")
    if parsed.path or parsed.query or parsed.fragment or parsed.hostname is None:
        raise ValueError("authority is malformed")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("port is invalid") from error
    if port is None:
        port = {"http": 80, "https": 443}.get(scheme.lower())
    return _normalize_hostname(parsed.hostname), port


def _origin_matches_request(origin: str) -> bool:
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.scheme != request.scheme:
        return False
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return False
    try:
        origin_authority = _parse_authority(parsed.netloc, parsed.scheme)
        request_authority = _parse_authority(request.host, request.scheme)
    except ValueError:
        return False
    return origin_authority == request_authority


def _is_ip_literal(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


def _derive_trusted_from_bind(bind_address: str) -> frozenset[str]:
    bind = bind_address.strip()
    if not bind:
        return frozenset()
    try:
        addr = ipaddress.ip_address(bind)
    except ValueError:
        return frozenset({_normalize_hostname(bind)})
    if addr.is_loopback or addr.is_unspecified:
        return frozenset()
    return frozenset({addr.compressed})


def install_request_security(
    app: Flask,
    configured_hosts: str,
    bind_address: str = "127.0.0.1",
    extra_trusted: frozenset[str] | None = None,
) -> None:
    """Install Host, unsafe-method marker, and browser Origin checks."""
    trusted_hosts = parse_trusted_hosts(configured_hosts)
    auto_trusted = _derive_trusted_from_bind(bind_address)
    trusted_hosts = trusted_hosts | auto_trusted
    if extra_trusted:
        trusted_hosts = trusted_hosts | _parse_exact_hosts(
            extra_trusted, "--trusted-host"
        )
    app.config["LLMFLASK_TRUSTED_HOSTS"] = trusted_hosts
    app.config["LLMFLASK_BIND_ADDRESS"] = bind_address

    @app.before_request
    def validate_request_boundary():
        try:
            request_hostname, _port = _parse_authority(request.host, request.scheme)
        except ValueError:
            return jsonify({"error": "Request host is malformed"}), 400

        allowed = request_hostname in trusted_hosts
        if not allowed:
            bind = app.config.get("LLMFLASK_BIND_ADDRESS", "")
            if bind in ("0.0.0.0", "::"):
                allowed = _is_ip_literal(request_hostname)

        if not allowed:
            repair = f"llmflask --server --listen {bind_address} --trusted-host {request_hostname}"
            return jsonify(
                {
                    "error": (
                        f"Request host {request_hostname!r} is not allowed. "
                        f"Restart the server with: {repair}"
                    )
                }
            ), 400

        if not request.path.startswith("/api/") or request.method not in UNSAFE_API_METHODS:
            return None
        if request.headers.get(REQUEST_HEADER_NAME) != REQUEST_HEADER_VALUE:
            return jsonify(
                {
                    "error": (
                        "State-changing API requests require "
                        f"{REQUEST_HEADER_NAME}: {REQUEST_HEADER_VALUE}"
                    )
                }
            ), 403
        origin = request.headers.get("Origin")
        if origin and not _origin_matches_request(origin):
            return jsonify({"error": "Request Origin does not match the request Host"}), 403
        return None
