from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Dict

from flask import Flask, jsonify, request, make_response

from query_runner import run_global_query

app = Flask(__name__)


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.after_request
def add_cors_headers(response):  # type: ignore[override]
    """Add minimal CORS headers for local dev and a separate React app."""
    response.headers["Access-Control-Allow-Origin"] = os.environ.get(
        "CORS_ALLOW_ORIGIN", "*"
    )
    response.headers["Access-Control-Allow-Headers"] = "content-type, authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/query", methods=["POST", "OPTIONS"])
def query_endpoint():
    # Handle CORS preflight quickly
    if request.method == "OPTIONS":
        return make_response(("", 204))
    try:
        payload: Dict[str, Any] = request.get_json(force=True, silent=False) or {}
    except Exception as e:  # bad json
        return jsonify({"error": f"invalid JSON: {e}"}), 400

    question = payload.get("question") or payload.get("query")
    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "missing 'question' (string) in request body"}), 400

    # Optional knobs (kept minimal for performance)
    community_level = payload.get("community_level")
    if community_level is not None:
        try:
            community_level = int(community_level)
        except Exception:
            return jsonify({"error": "community_level must be an integer"}), 400

    dynamic = payload.get("dynamic", True)
    if isinstance(dynamic, str):
        dynamic = dynamic.lower() not in ("false", "0", "no")

    try:
        result = run_global_query(
            query=question.strip(),
            root=None,  # auto-detects settings.yaml root and latest run dir
            community_level=community_level,
            dynamic_community_selection=bool(dynamic),
            response_type="multiple_paragraphs",
            verbose=bool(os.environ.get("GRAPHRAG_QUERY_VERBOSE")),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(
        {
            "answer": result.answer,
            "citations": result.citations.get("reports", []),
            "run_dir": result.run_dir,
        }
    ), 200


if __name__ == "__main__":
    # Bind to localhost by default. Customize via env if needed.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port)
