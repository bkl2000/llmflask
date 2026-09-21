# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
import logging
import os
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx

from ..config import NUM_CTX, OLLAMA_URL
from .api_keys import load_api_keys


_PROVIDER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_API_KEY_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*_API_KEY$")


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    base_url: str
    api_key_name: str
    requires_auth: bool = True
    api_style: str = "openai"


def _default_providers_path() -> Path:
    return Path(__file__).parent / "providers.json"


def _user_providers_path() -> Path:
    configured_home = os.getenv("XDG_CONFIG_HOME")
    config_home = (
        Path(configured_home).expanduser()
        if configured_home
        else Path.home() / ".config"
    )
    return config_home / "llmflask" / "providers.json"


def _load_providers() -> dict:
    user_path = _user_providers_path()
    try:
        return _parse_providers_json(user_path, fallback_on_error=False)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, json.JSONDecodeError):
        print(
            f"llmflask: warning: invalid providers file {user_path}, "
            f"falling back to defaults",
            file=sys.stderr,
        )

    return _parse_providers_json(_default_providers_path())


_FALLBACK_PROVIDERS = {
    "openai": Provider(
        "openai", "OpenAI", "https://api.openai.com/v1", "OPENAI_API_KEY"
    ),
    "deepseek": Provider(
        "deepseek",
        "DeepSeek",
        "https://api.deepseek.com",
        "DEEPSEEK_API_KEY",
    ),
    "zen": Provider(
        "zen",
        "OpenCode Zen",
        "https://opencode.ai/zen/v1",
        "ZEN_API_KEY",
        requires_auth=True,
    ),
}


def _parse_providers_json(
    path: Path,
    *,
    fallback_on_error: bool = True,
) -> dict:
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        if fallback_on_error:
            return dict(_FALLBACK_PROVIDERS)
        raise

    if not isinstance(data, dict) or not isinstance(data.get("providers"), list):
        if fallback_on_error:
            return dict(_FALLBACK_PROVIDERS)
        raise ValueError("providers must be a JSON object containing a providers list")

    providers: dict = {}
    for entry in data["providers"]:
        try:
            provider = Provider(
                name=entry["name"],
                label=entry["label"],
                base_url=entry["base_url"],
                api_key_name=entry.get("api_key_name", ""),
                requires_auth=entry.get("requires_auth", True),
                api_style=entry.get("api_style", "openai"),
            )
        except (KeyError, TypeError) as error:
            if fallback_on_error:
                continue
            raise ValueError("provider entries require name, label, and base_url") from error
        if not all(
            isinstance(value, str) and value
            for value in (provider.name, provider.label, provider.base_url)
        ):
            if fallback_on_error:
                continue
            raise ValueError("provider name, label, and base_url must be non-empty strings")
        if not _PROVIDER_NAME_RE.fullmatch(provider.name):
            if fallback_on_error:
                continue
            raise ValueError(f"invalid provider name: {provider.name!r}")
        if not isinstance(provider.requires_auth, bool):
            if fallback_on_error:
                continue
            raise ValueError(f"provider {provider.name!r} requires_auth must be boolean")
        if provider.api_style != "openai":
            if fallback_on_error:
                continue
            raise ValueError(f"unsupported provider api_style: {provider.api_style!r}")
        if not isinstance(provider.api_key_name, str) or (
            provider.api_key_name
            and not _API_KEY_NAME_RE.fullmatch(provider.api_key_name)
        ):
            if fallback_on_error:
                continue
            raise ValueError(f"invalid api_key_name for provider {provider.name!r}")
        if provider.requires_auth and not provider.api_key_name:
            if fallback_on_error:
                continue
            raise ValueError(f"provider {provider.name!r} requires api_key_name")
        providers[provider.name] = provider
    if providers:
        return providers
    if fallback_on_error:
        return dict(_FALLBACK_PROVIDERS)
    raise ValueError("providers list contains no valid providers")


REMOTE_PROVIDERS = _load_providers()

MODEL_GROUPS = (("local", "Local"), ("free", "Free"), ("api", "API"))
ZEN_KEY_HINT = (
    "Free models require a Zen key.\n"
    "Configure: llmflask --configure-api-keys"
)


def _model_ref(provider: str, model_id: str) -> str:
    return f"{provider}/{model_id}"


def _split_model_ref(model_ref: str) -> tuple[str, str]:
    if "/" not in model_ref:
        return "ollama", model_ref
    provider, model_id = model_ref.split("/", 1)
    if provider in ("ollama", *REMOTE_PROVIDERS.keys()) and model_id:
        return provider, model_id
    return "ollama", model_ref


def provider_for_model(model_ref: str) -> str:
    provider_name, _ = _split_model_ref(model_ref)
    return provider_name


def _model_entry(provider: str, model_id: str, label_prefix: str | None = None) -> dict:
    name = _model_ref(provider, model_id)
    label = f"{label_prefix}: {model_id}" if label_prefix else model_id
    if provider == "ollama":
        group = "local"
    elif provider == "zen" and model_id.endswith("-free"):
        group = "free"
    else:
        group = "api"
    return {"name": name, "provider": provider, "id": model_id, "label": label, "group": group}


def ollama_reachable(timeout: float = 3.0) -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        resp.raise_for_status()
        return True
    except Exception:
        return False


def list_ollama_models() -> list[dict]:
    endpoint = f"{OLLAMA_URL}/api/tags"
    try:
        resp = httpx.get(endpoint, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as error:
        logging.getLogger(__name__).warning(
            "Ollama model discovery failed at %s (%s). Check OLLAMA_URL and "
            "the Ollama daemon; remote providers remain available.",
            endpoint,
            type(error).__name__,
        )
        return []

    models = []
    seen = set()
    for item in data.get("models", []):
        model_id = item.get("name", "")
        if model_id and model_id not in seen:
            seen.add(model_id)
            entry = dict(item)
            entry.update(_model_entry("ollama", model_id, "Ollama"))
            models.append(entry)
    if not models:
        logging.getLogger(__name__).warning(
            "No Ollama models found at %s. Register a model with ollama pull; "
            "remote providers remain available.",
            endpoint,
        )
    return models


def _remote_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def list_remote_models(provider: Provider, api_key: str) -> list[dict]:
    if provider.requires_auth and not api_key:
        return []
    try:
        resp = httpx.get(
            f"{provider.base_url}/models",
            headers=_remote_headers(api_key),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    models = []
    seen = set()
    for item in data.get("data", []):
        model_id = item.get("id", "")
        if model_id and model_id not in seen:
            seen.add(model_id)
            models.append(_model_entry(provider.name, model_id, provider.label))
    return models


def order_models(models: list[dict]) -> list[dict]:
    """Keep discovery order within Local, Free, and API groups."""
    group_order = {name: index for index, (name, _) in enumerate(MODEL_GROUPS)}
    return sorted(models, key=lambda model: group_order.get(model.get("group"), 2))


def normalize_legacy_models(models: list[dict]) -> list[dict]:
    """Add current group metadata to models from an older server."""
    normalized = []
    for model in models:
        name = model.get("name", "")
        prefix, separator, suffix = name.partition("/")
        provider = model.get("provider") or (prefix if separator else "ollama")
        model_id = model.get("id") or (suffix if separator else name)
        normalized.append({**model, "group": _model_entry(provider, model_id)["group"]})
    return order_models(normalized)


def list_models() -> list[dict]:
    keys = load_api_keys()
    models = list_ollama_models()
    # Stable groups: Ollama, keyless providers, then configured key providers.
    providers = sorted(REMOTE_PROVIDERS.values(), key=lambda provider: provider.requires_auth)
    for provider in providers:
        api_key = keys.get(provider.api_key_name, "")
        if api_key or not provider.requires_auth:
            models.extend(list_remote_models(provider, api_key))
    return order_models(models)


def model_selection(models: list[dict] | None = None, *, include_key_hint: bool = True) -> dict:
    """Return selectable models and setup guidance for the model pickers."""
    keys = load_api_keys()
    zen = REMOTE_PROVIDERS.get("zen")
    available = list_models() if models is None else models
    return {
        "models": available,
        "groups": [{"id": name, "label": label} for name, label in MODEL_GROUPS],
        "free_hint": ZEN_KEY_HINT if include_key_hint and zen and not keys.get(zen.api_key_name) else "",
        "default_model": next(
            (model["name"] for model in available if model.get("group") in ("local", "free")),
            "",
        ),
    }


def ollama_chat_stream(messages: list[dict], model: str) -> Iterator[str]:
    body = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"num_ctx": NUM_CTX},
    }
    with httpx.stream("POST", f"{OLLAMA_URL}/api/chat", json=body, timeout=300) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get("done"):
                break
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content


def _parse_openai_sse(line: str) -> str:
    if isinstance(line, bytes):
        line = line.decode("utf-8", errors="replace")
    if not line.startswith("data: "):
        return ""
    payload = line[6:].strip()
    if payload == "[DONE]":
        return ""
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    return content if isinstance(content, str) else ""


def openai_compatible_chat_stream(
    messages: list[dict],
    model: str,
    provider: Provider,
    api_key: str,
) -> Iterator[str]:
    body = {"model": model, "messages": messages, "stream": True}
    with httpx.stream(
        "POST",
        f"{provider.base_url}/chat/completions",
        headers=_remote_headers(api_key),
        json=body,
        timeout=300,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            token = _parse_openai_sse(line)
            if token:
                yield token


def chat_stream(messages: list[dict], model_ref: str) -> Iterator[str]:
    provider_name, model_id = _split_model_ref(model_ref)
    if provider_name == "ollama":
        yield from ollama_chat_stream(messages, model_id)
        return

    provider = REMOTE_PROVIDERS[provider_name]
    api_key = load_api_keys().get(provider.api_key_name, "")
    if not api_key and provider.requires_auth:
        raise RuntimeError(f"{provider.label} API key is not configured. Run: llmflask --configure-api-keys")
    yield from openai_compatible_chat_stream(messages, model_id, provider, api_key)
