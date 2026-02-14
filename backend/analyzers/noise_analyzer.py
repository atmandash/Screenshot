"""
Noise Analysis — Detects inconsistent noise patterns across image regions.

Genuine screenshots have uniform noise characteristics throughout.
Spliced or edited regions introduce noise discontinuities because
different source images have different sensor/compression noise profiles.
"""

import numpy as np
from PIL import Image, ImageFilter


GRID_DIVISIONS = 8  # Split image into 8x8 grid for noise analysis


def _estimate_noise(region_array: np.ndarray) -> float:
    """
    Estimate noise level in a region using the Laplacian method.
    Higher values = more noise.
    """
    if region_array.size == 0:
        return 0.0

    # Convert to grayscale if needed
    if len(region_array.shape) == 3:
        gray = np.mean(region_array, axis=2)
    else:
        gray = region_array.astype(np.float64)

    # Laplacian kernel for noise estimation
    h, w = gray.shape
    if h < 3 or w < 3:
        return 0.0

    # Apply Laplacian filter manually
    laplacian = (
        -gray[:-2, 1:-1] - gray[2:, 1:-1] - gray[1:-1, :-2] - gray[1:-1, 2:]
        + 4 * gray[1:-1, 1:-1]
    )

    # Noise estimate = standard deviation of Laplacian response
    noise = np.std(laplacian)
    return float(noise)


def analyze_noise(image_path: str) -> dict:
    """
    Analyze noise consistency across the image.
    
    Returns:
        dict with 'score', 'flags', and 'details'
    """
    flags = []
    score = 0

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        return {"score": 50, "flags": [f"Could not open image: {e}"], "details": {}}

    img_array = np.array(img, dtype=np.float64)
    height, width, _ = img_array.shape

    # --- 1. Global noise estimate ---
    global_noise = _estimate_noise(img_array)

    # --- 2. Grid-based regional noise analysis ---
    cell_h = height // GRID_DIVISIONS
    cell_w = width // GRID_DIVISIONS

    regional_noise = []
    noise_map = []

    for row in range(GRID_DIVISIONS):
        noise_row = []
        for col in range(GRID_DIVISIONS):
            y1 = row * cell_h
            y2 = (row + 1) * cell_h if row < GRID_DIVISIONS - 1 else height
            x1 = col * cell_w
            x2 = (col + 1) * cell_w if col < GRID_DIVISIONS - 1 else width

            region = img_array[y1:y2, x1:x2]
            n = _estimate_noise(region)
            regional_noise.append(n)
            noise_row.append(round(n, 2))
        noise_map.append(noise_row)

    regional_noise = np.array(regional_noise)
    noise_mean = np.mean(regional_noise)
    noise_std = np.std(regional_noise)
    noise_range = np.max(regional_noise) - np.min(regional_noise)

    # Coefficient of variation — normalized measure of noise inconsistency
    cv = (noise_std / noise_mean * 100) if noise_mean > 0 else 0

    details = {
        "global_noise": round(global_noise, 2),
        "regional_mean": round(float(noise_mean), 2),
        "regional_std": round(float(noise_std), 2),
        "regional_range": round(float(noise_range), 2),
        "coefficient_of_variation": round(cv, 2),
        "noise_map": noise_map,
    }

    # --- 3. Detect outlier regions ---
    if noise_std > 0:
        z_scores = (regional_noise - noise_mean) / noise_std
        outlier_count = int(np.sum(np.abs(z_scores) > 2.5))
        extreme_outlier_count = int(np.sum(np.abs(z_scores) > 3.5))
    else:
        outlier_count = 0
        extreme_outlier_count = 0

    details["outlier_regions"] = outlier_count
    details["extreme_outlier_regions"] = extreme_outlier_count

    # --- 4. Score based on inconsistencies ---
    if cv > 60:
        flags.append(f"Extreme noise inconsistency (CV={cv:.1f}%) — very likely spliced from multiple sources")
        score += 50
    elif cv > 40:
        flags.append(f"High noise inconsistency (CV={cv:.1f}%) — regions have different noise profiles")
        score += 35
    elif cv > 25:
        flags.append(f"Moderate noise inconsistency (CV={cv:.1f}%) — some regions differ")
        score += 20
    elif cv > 15:
        flags.append(f"Slight noise variation (CV={cv:.1f}%) — mostly consistent")
        score += 8

    if extreme_outlier_count >= 3:
        flags.append(f"{extreme_outlier_count} regions have extreme noise differences — strong splicing indicator")
        score += 25
    elif outlier_count >= 4:
        flags.append(f"{outlier_count} regions show abnormal noise levels")
        score += 15

    # --- 5. Check for artificially uniform noise (too perfect = synthetic) ---
    if noise_mean > 0 and cv < 3 and global_noise > 5:
        flags.append("Suspiciously uniform noise — may be a computer-generated or synthetic image")
        score += 20

    # --- 6. Very low noise check (smooth rendering vs real capture) ---
    if global_noise < 1.5 and noise_mean < 2:
        flags.append("Extremely low noise — could be a rendered/generated mockup rather than real screenshot")
        score += 15

    if not flags:
        flags.append("Noise analysis shows consistent patterns — no splicing indicators")

    return {
        "score": min(100, score),
        "flags": flags,
        "details": details,
    }
