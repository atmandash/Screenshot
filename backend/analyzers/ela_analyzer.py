"""
Error Level Analysis (ELA) Analyzer.

Re-saves the image at a known JPEG quality and computes pixel-level
differences. Edited/spliced regions will show significantly different
error levels compared to the rest of the image.

This is one of the strongest indicators of image manipulation.
"""

import io
import numpy as np
from PIL import Image, ImageChops, ImageEnhance

from utils.image_helpers import image_to_base64


ELA_QUALITY = 90       # JPEG quality for re-save comparison
ELA_SCALE = 20         # Amplification factor for difference visibility
BLOCK_SIZE = 8         # JPEG block size for grid analysis
GRID_THRESHOLD = 30    # Threshold for grid anomaly detection


def analyze_ela(image_path: str) -> dict:
    """
    Perform Error Level Analysis on the image.
    
    Returns:
        dict with 'score', 'flags', 'ela_image' (base64), and 'details'
    """
    flags = []
    score = 0

    try:
        original = Image.open(image_path).convert("RGB")
    except Exception as e:
        return {"score": 50, "flags": [f"Could not open image: {e}"], "ela_image": None, "details": {}}

    width, height = original.size

    # --- Step 1: Re-save at known quality and compute difference ---
    buffer = io.BytesIO()
    original.save(buffer, format="JPEG", quality=ELA_QUALITY)
    buffer.seek(0)
    resaved = Image.open(buffer).convert("RGB")

    # Compute pixel-level difference
    diff = ImageChops.difference(original, resaved)

    # Amplify for visibility
    extrema = diff.getextrema()
    max_diff = max([ex[1] for ex in extrema])
    if max_diff == 0:
        max_diff = 1

    scale = 255.0 / max_diff
    ela_image = Image.eval(diff, lambda x: min(255, int(x * scale)))

    # Convert to numpy for statistical analysis
    diff_array = np.array(diff, dtype=np.float64)
    ela_array = np.array(ela_image, dtype=np.float64)

    # --- Step 2: Global statistics ---
    mean_diff = np.mean(diff_array)
    std_diff = np.std(diff_array)
    max_pixel_diff = np.max(diff_array)

    details = {
        "mean_error_level": round(float(mean_diff), 2),
        "std_error_level": round(float(std_diff), 2),
        "max_error_level": round(float(max_pixel_diff), 2),
        "scale_factor": round(scale, 2),
    }

    # --- Step 3: Block-level analysis for inconsistencies ---
    # Divide image into blocks and check for variance
    block_means = []
    for y in range(0, height - BLOCK_SIZE, BLOCK_SIZE):
        for x in range(0, width - BLOCK_SIZE, BLOCK_SIZE):
            block = diff_array[y:y + BLOCK_SIZE, x:x + BLOCK_SIZE]
            block_means.append(np.mean(block))

    block_means = np.array(block_means)

    if len(block_means) > 0:
        block_std = np.std(block_means)
        block_mean = np.mean(block_means)
        details["block_mean"] = round(float(block_mean), 2)
        details["block_std"] = round(float(block_std), 2)

        # High block std = inconsistent error levels = likely manipulation
        if block_std > 12:
            flags.append(f"Very high block-level variance ({block_std:.1f}) — strong indicator of image splicing")
            score += 45
        elif block_std > 7:
            flags.append(f"Elevated block-level variance ({block_std:.1f}) — possible region manipulation")
            score += 25
        elif block_std > 4:
            flags.append(f"Slightly elevated block variance ({block_std:.1f}) — minor inconsistencies")
            score += 10

        # Check for outlier blocks (potential spliced regions)
        threshold = block_mean + 3 * block_std if block_std > 0 else block_mean + 10
        outlier_count = np.sum(block_means > threshold)
        outlier_ratio = outlier_count / len(block_means) if len(block_means) > 0 else 0

        details["outlier_blocks"] = int(outlier_count)
        details["outlier_ratio"] = round(float(outlier_ratio), 4)

        if outlier_ratio > 0.05:
            flags.append(f"Significant number of outlier blocks ({outlier_ratio:.1%}) — localized editing detected")
            score += 30
        elif outlier_ratio > 0.02:
            flags.append(f"Some outlier blocks detected ({outlier_ratio:.1%})")
            score += 15

    # --- Step 4: Check if original was already JPEG ---
    # If the image was PNG, the ELA should show uniform low error
    # (since PNG is lossless). High error in a PNG = suspicious.
    file_ext = image_path.lower().rsplit(".", 1)[-1] if "." in image_path else ""
    if file_ext == "png" and mean_diff > 5:
        flags.append("PNG image shows elevated ELA levels — may have been converted from edited JPEG")
        score += 20

    # --- Step 5: Edge consistency check ---
    # Sharp artificial edges in ELA often indicate copy-paste
    if max_pixel_diff > 200 and std_diff > 15:
        flags.append("Extreme pixel differences detected — possible content overlay or text addition")
        score += 20

    if not flags:
        flags.append("ELA shows consistent error levels — no manipulation detected")

    # Generate ELA visualization
    ela_b64 = image_to_base64(ela_image)

    return {
        "score": min(100, score),
        "flags": flags,
        "ela_image": ela_b64,
        "details": details,
    }
