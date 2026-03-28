import logging
import traceback

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
try:
    logger.info("Initializing Flask application...")
    app = Flask(__name__)
    logger.info("Flask application initialized successfully.")
except Exception as exc:
    logger.critical("Failed to initialize Flask application: %s", exc)
    logger.critical(traceback.format_exc())
    raise


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(Exception)
def handle_unhandled_exception(exc):
    if isinstance(exc, HTTPException):
        raise  # Let Flask handle HTTP exceptions normally
    logger.error("Unhandled exception: %s", exc)
    logger.error(traceback.format_exc())
    return jsonify({"error": "Internal server error", "detail": str(exc)}), 500


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    logger.info("GET / called")
    print("GET / called", flush=True)
    return "OK HOME"


@app.route("/health")
def health():
    logger.info("GET /health called")
    print("GET /health called", flush=True)
    return "OK HEALTH"


# ---------------------------------------------------------------------------
# Entrypoint (development only — production uses Gunicorn)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting Flask development server on 0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, debug=True)
