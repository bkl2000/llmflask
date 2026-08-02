# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from flask import Blueprint, request, Response, current_app
from ..config import DEFAULT_USER
from ..database import get_messages, get_session_for_user, normalize_user
from ..services.exporter import export_md, export_pdf, export_ipynb

export_bp = Blueprint("export", __name__)


def _get_user():
    return normalize_user(request.args.get("user") or request.cookies.get("llmflask_user") or DEFAULT_USER)


@export_bp.route("/chat/<int:session_id>/export", methods=["GET"])
def export_chat(session_id):
    fmt = request.args.get("fmt", "md")
    db_path = current_app.config["DB_PATH"]

    try:
        user = _get_user()
    except ValueError:
        return Response("Invalid user name", status=400)

    session = get_session_for_user(db_path, session_id, user)
    if not session:
        return Response("Session not found", status=404)

    title = session.get("title", "Chat")
    messages = get_messages(db_path, session_id)

    if fmt == "pdf":
        try:
            data = export_pdf(messages, title)
        except RuntimeError as e:
            return Response(f"PDF generation failed: {e}", status=500)
        return Response(
            data,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="chat-{session_id}.pdf"'},
        )

    elif fmt == "ipynb":
        data = export_ipynb(messages, title)
        return Response(
            data,
            mimetype="application/x-ipynb+json",
            headers={"Content-Disposition": f'attachment; filename="chat-{session_id}.ipynb"'},
        )

    else:
        data = export_md(messages, title)
        return Response(
            data,
            mimetype="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="chat-{session_id}.md"'},
        )
