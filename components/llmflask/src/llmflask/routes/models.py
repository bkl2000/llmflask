# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from flask import Blueprint, jsonify
from ..services.model_providers import list_models

models_bp = Blueprint("models", __name__)


@models_bp.route("/models", methods=["GET"])
def get_models():
    models = list_models()
    return jsonify(models)
