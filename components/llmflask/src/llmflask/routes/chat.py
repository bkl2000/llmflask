# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from flask import Blueprint, request, jsonify, Response, current_app
from ..chat_runtime import build_chat_messages, collect_stream, trailing_newline_delta
from ..database import (
    add_message,
    get_messages,
    get_session_for_user,
    normalize_user,
    update_session_title_for_user,
)
from ..config import MAX_CONTEXT_MESSAGES, DEFAULT_USER
from ..services.model_providers import chat_stream, provider_for_model
from ..services.search_client import search, format_results
import json

chat_bp = Blueprint("chat", __name__)


def _get_user():
    return normalize_user(request.args.get("user") or request.cookies.get("llmflask_user") or DEFAULT_USER)


def _user_error():
    return jsonify({"error": "invalid user name"}), 400


@chat_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    session_id = data.get("session_id")
    user_message = data.get("message", "")
    model = data.get("model", "")
    enable_search = data.get("search", False)
    system_prompt = data.get("system_prompt")
    try:
        user = _get_user()
    except ValueError:
        return _user_error()

    if not session_id or not user_message or not model:
        return jsonify({"error": "session_id, message, and model required"}), 400

    db_path = current_app.config["DB_PATH"]
    if not get_session_for_user(db_path, session_id, user):
        return jsonify({"error": "session not found"}), 404

    add_message(db_path, session_id, "user", user_message)

    messages = get_messages(db_path, session_id)
    history = [{"role": m["role"], "content": m["content"]} for m in messages]

    if system_prompt:
        history.insert(0, {"role": "system", "content": system_prompt})

    if user != "default":
        insert_at = 1 if system_prompt else 0
        history.insert(insert_at, {"role": "system", "content": f"The user chatting with you is named {user}. You may address them by name if appropriate."})

    if enable_search and user_message.strip():
        results = search(user_message)
        if results:
            search_context = format_results(results)
            history[-1] = {
                "role": "user",
                "content": f"{user_message}\n{search_context}",
            }

    # Auto-title on first message
    if len(messages) <= 1 and user_message.strip():
        title = user_message[:60] + ("..." if len(user_message) > 60 else "")
        update_session_title_for_user(db_path, session_id, user, title)

    # Sliding window: keep local Ollama models within their configured context.
    max_msgs = MAX_CONTEXT_MESSAGES
    if provider_for_model(model) == "ollama" and len(history) > max_msgs:
        history = history[-max_msgs:]

    def generate():
        full_response = ""
        try:
            for token, full_response in collect_stream(chat_stream(history, model)):
                if token:
                    yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True, 'session_id': session_id})}\n\n"
            return
        final_token = trailing_newline_delta(full_response)
        if final_token:
            yield f"data: {json.dumps({'token': final_token, 'done': False})}\n\n"
            full_response = f"{full_response}{final_token}"
        if full_response:
            add_message(db_path, session_id, "assistant", full_response)
        yield f"data: {json.dumps({'token': '', 'done': True, 'session_id': session_id})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@chat_bp.route("/batch", methods=["POST"])
def batch_chat():
    data = request.get_json() or {}
    user_message = data.get("message", "")
    model = data.get("model", "")
    system_prompt = data.get("system_prompt")
    session_id = data.get("session_id")
    batch_user = data.get("user", "default")
    enable_search = data.get("search", False)

    if not user_message or not model:
        return jsonify({"error": "message and model required"}), 400

    db_path = current_app.config["DB_PATH"]
    if session_id is not None:
        try:
            batch_user = normalize_user(batch_user)
        except ValueError:
            return _user_error()
        if not get_session_for_user(db_path, session_id, batch_user):
            return jsonify({"error": "session not found"}), 404

    history = build_chat_messages(user_message, system_prompt if system_prompt else None)

    if enable_search and user_message.strip():
        results = search(user_message)
        if results:
            search_context = format_results(results)
            history[-1] = {
                "role": "user",
                "content": f"{user_message}\n{search_context}",
            }

    app_logger = current_app.logger

    def generate():
        nonlocal session_id
        full_response = ""
        try:
            for token, full_response in collect_stream(chat_stream(history, model)):
                if token:
                    yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            return

        if session_id is not None and full_response:
            try:
                add_message(db_path, session_id, "user", user_message)
                add_message(db_path, session_id, "assistant", full_response)
                if len(get_messages(db_path, session_id)) <= 2:
                    title = user_message[:60] + ("..." if len(user_message) > 60 else "")
                    update_session_title_for_user(db_path, session_id, batch_user, title)
            except Exception:
                app_logger.exception(
                    "Could not persist batch response for session %s and user %s",
                    session_id,
                    batch_user,
                )

        final_token = trailing_newline_delta(full_response)
        if final_token:
            yield f"data: {json.dumps({'token': final_token, 'done': False})}\n\n"
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@chat_bp.route("/chat/<int:session_id>/messages", methods=["GET"])
def get_chat_messages(session_id):
    try:
        user = _get_user()
    except ValueError:
        return _user_error()
    db_path = current_app.config["DB_PATH"]
    if not get_session_for_user(db_path, session_id, user):
        return jsonify({"error": "session not found"}), 404
    messages = get_messages(db_path, session_id)
    return jsonify(messages)
