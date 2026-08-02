# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from . import config
from .database import init_db
from .routes.chat import chat_bp
from .routes.models import models_bp
from .routes.sessions import sessions_bp
from .routes.search import search_bp
from .routes.export import export_bp
from .routes.workbench import workbench_bp
from .request_security import install_request_security


def create_app(bind_address: str = "127.0.0.1", extra_trusted: frozenset[str] | None = None):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.config["DB_PATH"] = config.prepare_database_path(config.DATABASE)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES
    install_request_security(app, config.TRUSTED_HOSTS, bind_address, extra_trusted=extra_trusted)

    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(models_bp, url_prefix="/api")
    app.register_blueprint(sessions_bp, url_prefix="/api")
    app.register_blueprint(search_bp, url_prefix="/api")
    app.register_blueprint(export_bp, url_prefix="/api")
    app.register_blueprint(workbench_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return send_from_directory(app.template_folder, "index.html")

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Upload exceeds the configured size limit"}), 413
        return "Upload exceeds the configured size limit", 413

    with app.app_context():
        init_db(app.config["DB_PATH"])

    return app
