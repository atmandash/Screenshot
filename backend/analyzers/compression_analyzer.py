"""
Compression Artifact Analyzer.

Analyzes JPEG compression artifacts and quantization table consistency.
Real screenshots saved as JPEG will have uniform compression.
Edited images often show double-compression or inconsistent quantization.
"""

import io
import struct
import numpy as np
from PIL import Image


def _extract_quantization_tables(image_path: str) -> list:
    """Extract JPEG quantization tables from the file."""
    tables = []
    try:
        with open(image_path, "rb") as f:
            data = f.read()

        i = 0
        while i < len(data) - 1:
            if data[i] == 0xFF and data[i + 1] == 0xDB:
                # DQT marker found
                i += 2
                if i + 2 > len(data):
                    break
                length = struct.unpack(">H", data[i:i + 2])[0]
                table_data = data[i + 2:i + length]
                
                j = 0
                while j < len(table_data):
                    precision_id = table_data[j]
                    precision = (precision_id >> 4) & 0x0F
                    table_id = precision_id & 0x0F
                    j += 1
                    
                    size = 64 * (2 if precision else 1)
                    if j + size <= len(table_data):
                        table_values = list(table_data[j:j + size])
                        tables.append({
                            "id": table_id,
                            "precision": precision,
                            "values": table_values[:64],  # First 64 values
                        })
                    j += size
                i += length
            else:
                i += 1
    except Exception:
        pass

    return tables


def _detect_double_compression(image_path: str) -> dict:
    """
    Detect signs of double JPEG compression by analyzing
    the distribution of DCT coefficients.
    """
    result = {"detected": False, "confidence": 0, "details": ""}
    
    try:
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img, dtype=np.float64)

        # Convert to grayscale for DCT analysis
        gray = np.mean(img_array, axis=2)
        h, w = gray.shape

        # Analyze 8x8 block boundaries (JPEG compression grid)
        # Double-compressed images show periodic artifacts at block boundaries
        block_boundary_diffs = []
        interior_diffs = []

        for y in range(1, h - 1):
            for x in range(1, w - 1):
                diff = abs(float(gray[y, x] - gray[y, x - 1]))
                if x % 8 == 0:  # Block boundary
                    block_boundary_diffs.append(diff)
                else:
                    interior_diffs.append(diff)

        if block_boundary_diffs and interior_diffs:
            boundary_mean = np.mean(block_boundary_diffs)
            interior_mean = np.mean(interior_diffs)

            # In double-compressed images, block boundaries show higher differences
            ratio = boundary_mean / interior_mean if interior_mean > 0 else 1.0
            
            result["boundary_interior_ratio"] = round(ratio, 3)

            if ratio > 1.3:
                result["detected"] = True
                result["confidence"] = min(100, int((ratio - 1.0) * 100))
                result["details"] = f"Block boundary artifacts detected (ratio: {ratio:.2f}) — indicates double JPEG compression"
            elif ratio > 1.15:
                result["confidence"] = int((ratio - 1.0) * 60)
                result["details"] = f"Mild block boundary artifacts (ratio: {ratio:.2f})"

    except Exception as e:
        result["details"] = f"Analysis error: {e}"

    return result


def analyze_compression(image_path: str) -> dict:
    """
    Analyze compression artifacts for signs of manipulation.
    
    Returns:
        dict with 'score', 'flags', and 'details'
    """
    flags = []
    score = 0

    try:
        img = Image.open(image_path)
    except Exception as e:
        return {"score": 50, "flags": [f"Could not open image: {e}"], "details": {}}

    details = {
        "format": img.format,
    }

    is_jpeg = img.format and img.format.upper() in ("JPEG", "JPG")

    # --- 1. Quantization table analysis (JPEG only) ---
    if is_jpeg:
        qtables = _extract_quantization_tables(image_path)
        details["quantization_tables_found"] = len(qtables)

        if qtables:
            # Check if tables match standard qualities
            for qt in qtables:
                values = qt["values"]
                if len(values) >= 64:
                    # Very high quantization values = heavy compression = suspicious re-save
                    max_qval = max(values[:64])
                    mean_qval = sum(values[:64]) / 64
                    details[f"qtable_{qt['id']}_max"] = max_qval
                    details[f"qtable_{qt['id']}_mean"] = round(mean_qval, 1)

                    if max_qval > 100:
                        flags.append(f"High quantization values in table {qt['id']} — heavy compression applied")
                        score += 10

        # --- 2. Double compression detection ---
        dc_result = _detect_double_compression(image_path)
        details["double_compression"] = dc_result

        if dc_result["detected"]:
            flags.append(dc_result["details"])
            score += 35
        elif dc_result.get("confidence", 0) > 30:
            flags.append(dc_result.get("details", "Possible double compression"))
            score += 15

    # --- 3. PNG saved from JPEG check ---
    if img.format and img.format.upper() == "PNG":
        # Check for JPEG artifacts in a PNG (re-save to hide JPEG origin)
        img_rgb = img.convert("RGB")
        img_array = np.array(img_rgb, dtype=np.float64)
        gray = np.mean(img_array, axis=2)
        h, w = gray.shape

        if h > 16 and w > 16:
            # Check 8x8 block boundary artifacts
            boundary_diffs = []
            interior_diffs = []

            sample_step = max(1, h // 100)  # Sample for performance
            for y in range(1, h - 1, sample_step):
                for x in range(1, w - 1):
                    diff = abs(float(gray[y, x] - gray[y, x - 1]))
                    if x % 8 == 0:
                        boundary_diffs.append(diff)
                    elif x % 8 == 4:
                        interior_diffs.append(diff)

            if boundary_diffs and interior_diffs:
                ratio = np.mean(boundary_diffs) / max(np.mean(interior_diffs), 0.01)
                details["png_jpeg_artifact_ratio"] = round(ratio, 3)

                if ratio > 1.25:
                    flags.append(f"PNG contains JPEG-like block artifacts (ratio: {ratio:.2f}) — image was likely saved as JPEG then converted to PNG to hide editing")
                    score += 30

    # --- 4. Re-compression quality estimation ---
    if is_jpeg:
        # Estimate original quality by re-saving at various qualities
        img_rgb = img.convert("RGB")
        original_size = len(open(image_path, "rb").read())

        quality_estimates = []
        for q in range(50, 100, 5):
            buf = io.BytesIO()
            img_rgb.save(buf, format="JPEG", quality=q)
            size_at_q = buf.tell()
            quality_estimates.append((q, size_at_q))

        # Find closest quality match
        closest_q = min(quality_estimates, key=lambda x: abs(x[1] - original_size))
        details["estimated_quality"] = closest_q[0]

        if closest_q[0] < 70:
            flags.append(f"Low estimated JPEG quality ({closest_q[0]}) — multiple re-saves may have occurred")
            score += 15

    if not flags:
        flags.append("No compression anomalies detected")

    return {
        "score": min(100, score),
        "flags": flags,
        "details": details,
    }
