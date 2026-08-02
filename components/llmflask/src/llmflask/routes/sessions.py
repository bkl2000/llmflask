# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from flask import Blueprint, request, jsonify, current_app
from ..database import (
    create_session,
    delete_user,
    delete_session_for_user,
    ensure_user,
    get_sessions,
    list_users as list_users_from_db,
    normalize_user,
    rename_user,
    update_session_title_for_user,
)
from ..config import DEFAULT_USER

sessions_bp = Blueprint("sessions", __name__)


def _get_user():
    return normalize_user(request.args.get("user") or request.cookies.get("llmflask_user") or DEFAULT_USER)


def _user_error():
    return jsonify({"error": "invalid user name"}), 400


@sessions_bp.route("/sessions", methods=["POST"])
def new_session():
    data = request.get_json() or {}
    title = data.get("title", "New Chat")
    model = data.get("model", "")
    try:
        user = _get_user()
    except ValueError:
        return _user_error()
    sid = create_session(current_app.config["DB_PATH"], user=user, title=title, model=model)
    return jsonify({"id": sid, "title": title, "user": user}), 201


@sessions_bp.route("/sessions", methods=["GET"])
def list_sessions():
    try:
        user = _get_user()
    except ValueError:
        return _user_error()
    sessions = get_sessions(current_app.config["DB_PATH"], user)
    return jsonify(sessions)


@sessions_bp.route("/users", methods=["GET"])
def list_users():
    return jsonify(list_users_from_db(current_app.config["DB_PATH"]))


@sessions_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json() or {}
    if data.get("name") is None:
        return _user_error()
    try:
        user = ensure_user(current_app.config["DB_PATH"], data.get("name"))
    except ValueError:
        return _user_error()
    return jsonify({"name": user}), 201


@sessions_bp.route("/users/<string:name>", methods=["PUT"])
def update_user(name):
    data = request.get_json() or {}
    if data.get("name") is None:
        return _user_error()
    try:
        user = rename_user(current_app.config["DB_PATH"], name, data.get("name"))
    except FileExistsError:
        return jsonify({"error": "user already exists"}), 409
    except LookupError:
        return jsonify({"error": "user not found"}), 404
    except ValueError:
        return _user_error()
    return jsonify({"name": user})


@sessions_bp.route("/users/<string:name>", methods=["DELETE"])
def remove_user(name):
    try:
        deleted_chats = delete_user(current_app.config["DB_PATH"], name)
    except LookupError:
        return jsonify({"error": "user not found"}), 404
    except ValueError:
        return _user_error()
    return jsonify({"deleted": name, "deleted_chats": deleted_chats})


@sessions_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
def remove_session(session_id):
    try:
        user = _get_user()
    except ValueError:
        return _user_error()
    if not delete_session_for_user(current_app.config["DB_PATH"], session_id, user):
        return jsonify({"error": "session not found"}), 404
    return jsonify({"deleted": session_id})


@sessions_bp.route("/sessions/<int:session_id>", methods=["PUT"])
def rename_session(session_id):
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    try:
        user = _get_user()
    except ValueError:
        return _user_error()
    if not update_session_title_for_user(current_app.config["DB_PATH"], session_id, user, title):
        return jsonify({"error": "session not found"}), 404
    return jsonify({"id": session_id, "title": title})
