# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from flask import Blueprint, request, jsonify
from ..services.search_client import search, format_results

search_bp = Blueprint("search", __name__)


@search_bp.route("/search", methods=["POST"])
def search_web():
    data = request.get_json()
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "query required"}), 400
    results = search(query)
    return jsonify({"results": results, "formatted": format_results(results)})
