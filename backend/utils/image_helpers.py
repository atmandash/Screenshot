"""
Utility helpers for image loading, conversion, and scoring.
"""

import io
import base64
import hashlib
from PIL import Image


def load_image(path: str) -> Image.Image:
    """Safely load and validate an image file."""
    try:
        img = Image.open(path)
        img.verify()  # Verify it's a valid image
        img = Image.open(path)  # Re-open after verify (verify closes the file)
        return img
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {e}")


def image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    """Convert a PIL Image to a base64 data URI string."""
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def file_md5(path: str) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def calculate_suspicion_score(results: dict) -> dict:
    """
    Calculate a weighted overall suspicion score from all analyzer results.
    
    Weights are tuned to be STRICT — we want to catch fakes aggressively.
    A higher score = more likely to be manipulated/fake.
    
    Returns dict with 'score' (0-100), 'verdict', and 'details'.
    """
    weights = {
        "metadata": 0.20,
        "ela": 0.35,       # ELA is the strongest signal
        "noise": 0.25,
        "hash": 0.05,
        "compression": 0.15,
    }

    total_score = 0.0
    detail_scores = {}

    for key, weight in weights.items():
        if key in results and "score" in results[key]:
            raw = results[key]["score"]
            weighted = raw * weight
            total_score += weighted
            detail_scores[key] = {
                "raw_score": round(raw, 1),
                "weight": weight,
                "weighted_score": round(weighted, 1),
            }

    # Normalize to 0-100
    final_score = min(100, max(0, round(total_score, 1)))

    # Strict thresholds — err on the side of flagging
    if final_score >= 60:
        verdict = "FAKE"
        confidence = "High"
        message = "This screenshot shows strong signs of manipulation or forgery."
    elif final_score >= 35:
        verdict = "SUSPICIOUS"
        confidence = "Medium"
        message = "This screenshot has notable anomalies. It may have been altered."
    elif final_score >= 15:
        verdict = "UNCERTAIN"
        confidence = "Low"
        message = "Minor anomalies detected. The screenshot may be authentic but has some irregularities."
    else:
        verdict = "AUTHENTIC"
        confidence = "High"
        message = "This screenshot appears to be genuine with no significant signs of tampering."

    return {
        "score": final_score,
        "verdict": verdict,
        "confidence": confidence,
        "message": message,
        "breakdown": detail_scores,
    }
