# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import re
import sys

import httpx

from .services.api_keys import load_api_keys
from .services.model_providers import REMOTE_PROVIDERS, list_models, list_remote_models


_VRAM_TIERS = (
    (5.0, "4 GB"),
    (10.0, "8 GB"),
    (20.0, "12 GB"),
)


def _human_size(size_bytes: int) -> str:
    if not size_bytes:
        return ""
    if size_bytes >= 1024**3:
        return f"{size_bytes / 1024**3:.1f}G"
    return f"{size_bytes / 1024**2:.0f}M"


def _parse_params(param_size: str) -> float | None:
    match = re.search(r"([0-9.]+)B", param_size or "")
    return float(match.group(1)) if match else None


def _params_from_name(model_id: str) -> float | None:
    match = re.search(r"([0-9.]+)b", model_id or "")
    return float(match.group(1)) if match else None


def _vram_fit(model: dict) -> str:
    details = model.get("details") or {}
    params = _parse_params(details.get("parameter_size", ""))
    if params is None:
        params = _parse_params(details.get("param_size", ""))
    if params is None:
        params = _params_from_name(model.get("id", "") or model.get("name", ""))
    if params is None:
        return ""
    for limit, label in _VRAM_TIERS:
        if params < limit:
            return label
    return "16+ GB"


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _local_server_available(host: str, port: int) -> bool:
    try:
        response = httpx.get(f"{_base_url(host, port)}/api/users", timeout=1)
        response.raise_for_status()
        return isinstance(response.json(), list)
    except Exception:
        return False


def _resolve_tui_provider(
    requested_provider: str | None,
    host: str,
    port: int,
    explicit_server_target: bool,
) -> str:
    if requested_provider is not None:
        return requested_provider
    if explicit_server_target or _local_server_available(host, port):
        return "server"

    keys = load_api_keys()
    configured = [
        provider.name
        for provider in REMOTE_PROVIDERS.values()
        if keys.get(provider.api_key_name)
    ]
    if len(configured) == 1:
        return configured[0]

    server = _base_url(host, port)
    if configured:
        providers = " or ".join(f"--provider {name}" for name in configured)
        raise ValueError(
            f"No local LLMFlask server at {server}; multiple remote API keys "
            f"are configured. Choose {providers}."
        )
    raise ValueError(
        f"No local LLMFlask server at {server} and no remote API key is configured. "
        "Run llmflask --configure-api-keys or start llmflask --server."
    )


def _server_models(host: str, port: int) -> list[dict]:
    resp = httpx.get(f"{_base_url(host, port)}/api/models", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def _direct_provider_models(provider_name: str) -> list[dict]:
    provider = REMOTE_PROVIDERS[provider_name]
    api_key = load_api_keys().get(provider.api_key_name)
    if not api_key:
        raise RuntimeError(f"{provider.api_key_name} is not configured")
    return list_remote_models(provider, api_key)


def print_models(host: str, port: int, provider: str = "server", use_server: bool = False) -> int:
    try:
        if provider == "server":
            models = _server_models(host, port) if use_server else list_models()
        else:
            models = _direct_provider_models(provider)
    except Exception as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1

    if not models:
        print(
            "No models found. Is Ollama running? Remote models need OPENAI_API_KEY/DEEPSEEK_API_KEY.",
            file=sys.stderr,
        )
        return 1

    print("MODELREF\tPROVIDER\tLABEL\tSIZE\tVRAM")
    for model in models:
        print(
            "\t".join(
                [
                    model.get("name", ""),
                    model.get("provider", ""),
                    model.get("label", ""),
                    _human_size(model.get("size") or 0),
                    _vram_fit(model),
                ]
            )
        )
    return 0


def _validate_model_ref(host: str, port: int, model_ref: str, use_server: bool = False) -> bool:
    try:
        if use_server:
            models = _server_models(host, port)
        else:
            models = list_models()
    except Exception:
        if use_server:
            print(f"llmflask: error: Cannot reach LLMFlask server at {host}:{port}", file=sys.stderr)
            return False
        print("llmflask: error: Cannot reach Ollama to verify model; proceeding with request.", file=sys.stderr)
        return True

    model_names = {m.get("name", "") for m in models}
    if not model_names:
        return True
    if model_ref in model_names:
        return True

    print(f"llmflask: error: Model '{model_ref}' not found on this server.", file=sys.stderr)
    if any("/" in ref for ref in model_names):
        print("         Available models (copy one as MODELREF):", file=sys.stderr)
    else:
        print("         Run llmflask --models --host ... to see available models.", file=sys.stderr)
    for model in models:
        print(f"           {model.get('name', '?')}  ({model.get('label', '?')})", file=sys.stderr)
    return False


def _show_available_models(provider: str | None, host: str, port: int, target: bool) -> None:
    try:
        print_models(host, port, provider=provider or "server", use_server=target)
    except Exception:
        pass
