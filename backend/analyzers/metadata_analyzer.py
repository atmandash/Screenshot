"""
Metadata Analyzer — Inspects EXIF and image metadata for signs
of editing, re-saving, or generation by tools like Photoshop,
screenshot generators, or AI tools.
"""

from PIL import Image
from PIL.ExifTags import TAGS
import os
import datetime


# Software/tools commonly used to create or edit/fake screenshots
SUSPICIOUS_SOFTWARE = [
    "photoshop", "gimp", "paint.net", "affinity", "pixelmator",
    "lightroom", "capture one", "snapseed", "canva", "figma",
    "sketch", "illustrator", "inkscape", "corel", "acorn",
    "fake", "generator", "screenshot maker", "mockup", "browser frame",
    "chrome devtools", "inspect element", "web inspector",
    "midjourney", "dall-e", "stable diffusion", "ai",
    "screen capture pro", "greenshot edited",
]

# Expected screenshot dimensions (common device/screen resolutions)
COMMON_RESOLUTIONS = [
    (1920, 1080), (2560, 1440), (3840, 2160),  # Desktop
    (1366, 768), (1440, 900), (1536, 864),      # Laptop
    (2880, 1800), (3024, 1964), (2560, 1600),   # Retina Mac
    (1170, 2532), (1284, 2778), (1290, 2796),   # iPhone
    (1080, 2340), (1080, 2400), (1440, 3200),   # Android
    (2048, 2732), (2360, 1640),                  # iPad
    (750, 1334), (828, 1792), (1125, 2436),      # Older iPhone
    (1080, 1920), (1440, 2560),                  # Common Android
]

# Formats that are natural for screenshots
SCREENSHOT_FORMATS = ["PNG", "JPEG", "WEBP", "BMP", "TIFF"]


def analyze_metadata(image_path: str) -> dict:
    """Analyze image metadata for authenticity signals."""
    flags = []
    score = 0  # 0 = clean, 100 = definitely fake

    try:
        img = Image.open(image_path)
    except Exception as e:
        return {"score": 50, "flags": [f"Could not open image: {e}"], "details": {}}

    details = {
        "format": img.format,
        "mode": img.mode,
        "size": list(img.size),
        "file_size_bytes": os.path.getsize(image_path),
    }

    # --- 1. Format check ---
    if img.format and img.format.upper() not in SCREENSHOT_FORMATS:
        flags.append(f"Unusual format for a screenshot: {img.format}")
        score += 15

    # --- 2. EXIF analysis ---
    exif_data = {}
    try:
        raw_exif = img._getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag_name = TAGS.get(tag_id, tag_id)
                try:
                    exif_data[str(tag_name)] = str(value)
                except Exception:
                    pass
    except Exception:
        pass

    details["exif"] = exif_data

    if exif_data:
        # Screenshots typically have minimal or no EXIF data
        if len(exif_data) > 10:
            flags.append(f"Unusually rich EXIF data ({len(exif_data)} tags) — typical of camera photos, not screenshots")
            score += 20

        # Check for GPS data — screenshots don't have GPS
        gps_tags = [k for k in exif_data if "gps" in k.lower()]
        if gps_tags:
            flags.append("Contains GPS/location data — not expected in screenshots")
            score += 25

        # Check for camera model — screenshots don't come from cameras
        camera_tags = [k for k in exif_data if k.lower() in ("model", "make", "lensmodel")]
        if camera_tags:
            flags.append("Contains camera hardware metadata — this is a photo, not a screenshot")
            score += 30

        # Check for editing software
        software_value = exif_data.get("Software", "").lower()
        for suspect in SUSPICIOUS_SOFTWARE:
            if suspect in software_value:
                flags.append(f"Created/edited with suspicious software: {exif_data.get('Software')}")
                score += 35
                break

        # Check for modification timestamps
        if "DateTimeOriginal" in exif_data and "DateTime" in exif_data:
            if exif_data["DateTimeOriginal"] != exif_data["DateTime"]:
                flags.append("Original and modification timestamps differ — image was edited")
                score += 20
    else:
        # No EXIF is normal for PNG screenshots, but suspicious for JPEG
        if img.format and img.format.upper() == "JPEG":
            flags.append("JPEG with no EXIF data — metadata may have been stripped")
            score += 10

    # --- 3. Resolution check ---
    width, height = img.size
    dims = (width, height)
    dims_rotated = (height, width)

    is_common = dims in COMMON_RESOLUTIONS or dims_rotated in COMMON_RESOLUTIONS
    if not is_common:
        # Check if it's close to a common resolution (within 50px tolerance for UI chrome)
        is_close = False
        for cw, ch in COMMON_RESOLUTIONS:
            if (abs(width - cw) <= 50 and abs(height - ch) <= 200) or \
               (abs(width - ch) <= 50 and abs(height - cw) <= 200):
                is_close = True
                break
        if not is_close:
            flags.append(f"Non-standard resolution ({width}×{height}) — may be cropped or fabricated")
            score += 10

    # --- 4. Unusually small file check ---
    file_size = os.path.getsize(image_path)
    pixel_count = width * height
    bytes_per_pixel = file_size / max(pixel_count, 1)

    if img.format and img.format.upper() == "PNG" and bytes_per_pixel < 0.1:
        flags.append("Extremely low file size for PNG — possible synthetic/generated image")
        score += 15

    # --- 5. Color mode check ---
    if img.mode == "P":
        flags.append("Palette/indexed color mode — uncommon for genuine screenshots")
        score += 10
    elif img.mode == "L":
        flags.append("Grayscale image — unusual for a screenshot")
        score += 5

    # --- 6. DPI / resolution info ---
    dpi = img.info.get("dpi")
    if dpi:
        details["dpi"] = list(dpi)
        if dpi[0] != dpi[1]:
            flags.append(f"Asymmetric DPI ({dpi[0]}×{dpi[1]}) — sign of manipulation")
            score += 15

    # --- 7. Text chunks (PNG) ---
    if img.format and img.format.upper() == "PNG":
        text_chunks = {k: v for k, v in img.info.items() if isinstance(v, str)}
        if text_chunks:
            details["png_text_chunks"] = text_chunks
            for key, val in text_chunks.items():
                val_lower = val.lower()
                for suspect in SUSPICIOUS_SOFTWARE:
                    if suspect in val_lower:
                        flags.append(f"PNG text chunk '{key}' references suspicious software: {val}")
                        score += 25
                        break

    if not flags:
        flags.append("No metadata anomalies detected")

    return {
        "score": min(100, score),
        "flags": flags,
        "details": details,
    }
