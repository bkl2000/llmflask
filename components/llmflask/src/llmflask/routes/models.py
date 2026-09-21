# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from flask import Blueprint, jsonify
from ..services.model_providers import list_models, model_selection

models_bp = Blueprint("models", __name__)


@models_bp.route("/models", methods=["GET"])
def get_models():
    models = list_models()
    return jsonify(models)


@models_bp.route("/model-selection", methods=["GET"])
def get_model_selection():
    return jsonify(model_selection())
