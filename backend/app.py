"""
Screenshot Checker — Flask Backend

Serves the frontend and provides the /api/analyze endpoint
for uploading and analyzing screenshots for authenticity.
"""

import os
import sys
import uuid
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Add backend to path so analyzers can import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzers import run_all_analyzers
from utils.image_helpers import calculate_suspicion_score

app = Flask(__name__, static_folder=None)
CORS(app)

# Config
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "screenshot_checker_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff", "tif"}

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Serve Frontend ──────────────────────────────────────────────

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "css"), filename)


@app.route("/jsAnd/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "jsAnd"), filename)


@app.route("/images/<path:filename>")
def serve_images(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ── API Endpoints ───────────────────────────────────────────────

@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Accept an image upload, run all analyzers, and return a full report.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Send a file with key 'file'."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # Save to temp file
    ext = file.filename.rsplit(".", 1)[1].lower()
    temp_filename = f"{uuid.uuid4().hex}.{ext}"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)

    try:
        file.save(temp_path)

        # Check file size
        if os.path.getsize(temp_path) > MAX_FILE_SIZE:
            os.remove(temp_path)
            return jsonify({"error": f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB."}), 400

        # Run all analyzers
        analyzer_results = run_all_analyzers(temp_path)

        # Calculate overall score
        overall = calculate_suspicion_score(analyzer_results)

        report = {
            "status": "success",
            "filename": file.filename,
            "overall": overall,
            "analyzers": analyzer_results,
        }

        return jsonify(report)

    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Screenshot Checker API is running"})


# ── Run ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n🔍 Screenshot Checker running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
