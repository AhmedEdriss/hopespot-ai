"""
Email Agent Webhook Server

A thin HTTP layer over agent.py so Make.com or n8n can trigger it.

Run locally:
    python agents/email/webhook_server.py

Or deploy to Render, Fly.io, Railway, Google Cloud Run, etc.

Endpoints:
    POST /process   — main agent endpoint
    GET  /healthz   — health check
    GET  /          — usage info
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

# Make project modules importable regardless of where this is launched from.
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.email import agent  # noqa: E402
from shared import kb_loader  # noqa: E402
from shared import model_gateway  # noqa: E402

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("HSO_WEBHOOK_SECRET", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook")


def authorized(req) -> bool:
    if not WEBHOOK_SECRET:
        return True  # no auth configured
    return req.headers.get("X-Webhook-Secret", "") == WEBHOOK_SECRET


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "HSO Email Agent",
        "endpoints": {
            "POST /process": "Run agent on an email",
            "GET /healthz": "Health check",
        },
        "expected_payload": {
            "message_id": "string (Gmail message ID)",
            "thread_id": "string (Gmail thread ID)",
            "sender_email": "string",
            "sender_name": "string",
            "subject": "string",
            "body": "string (plain text email body)",
            "attachment_count": "integer (optional, default 0)",
        },
    })


@app.route("/healthz", methods=["GET"])
def healthz():
    """
    Lightweight health check: verifies KB is reachable and at least one
    model provider is configured. Does NOT make a real model call (that
    would burn money on every healthcheck).
    """
    kb_root = kb_loader.get_kb_root()
    providers_status = {}
    for name in ["openrouter", "anthropic", "openai"]:
        try:
            providers_status[name] = model_gateway.get_provider(name).is_configured()
        except Exception:
            providers_status[name] = False

    checks = {
        "kb_path_exists": kb_root.exists(),
        "kb_core_dir_exists": (kb_root / "00_Core").exists(),
        "any_provider_configured": any(providers_status.values()),
        "providers": providers_status,
    }
    healthy = checks["kb_path_exists"] and checks["any_provider_configured"]
    return jsonify({"healthy": healthy, "checks": checks}), 200 if healthy else 503


@app.route("/process", methods=["POST"])
def process():
    if not authorized(request):
        return jsonify({"error": "unauthorized"}), 401

    try:
        payload = request.get_json(force=True)
    except Exception as e:
        return jsonify({"error": f"invalid_json: {e}"}), 400

    required = ["message_id", "sender_email", "body"]
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return jsonify({"error": "missing_required_fields", "missing": missing}), 400

    try:
        result = agent.process_email_from_dict(payload)
        logger.info(
            "Processed %s outcome=%s tokens=%s cost=$%.4f",
            payload["message_id"],
            result["outcome"],
            result["total_tokens"],
            result["estimated_cost_usd"],
        )
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Process error")
        return jsonify({"error": "internal_error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
