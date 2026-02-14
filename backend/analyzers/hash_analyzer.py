"""
Hash Analyzer — Generates perceptual hash and MD5 digest for the image.

Perceptual hashing (pHash) creates a fingerprint based on visual content,
which is useful for detecting near-duplicate images and subtle edits.
"""

import hashlib
from PIL import Image

from utils.image_helpers import file_md5


PHASH_SIZE = 16  # Size of the hash matrix (16x16 = 256 bits)


def _compute_phash(img: Image.Image) -> str:
    """
    Compute a perceptual hash of the image.
    
    Steps:
    1. Resize to small square
    2. Convert to grayscale
    3. Compute DCT-like comparison (simplified: mean threshold)
    4. Generate binary hash string
    """
    # Resize to PHASH_SIZE x PHASH_SIZE
    small = img.resize((PHASH_SIZE, PHASH_SIZE), Image.LANCZOS).convert("L")
    pixels = list(small.getdata())
    mean_val = sum(pixels) / len(pixels)

    # Binary hash: 1 if pixel > mean, 0 otherwise
    bits = "".join("1" if p > mean_val else "0" for p in pixels)

    # Convert to hex
    hex_hash = hex(int(bits, 2))[2:].zfill(PHASH_SIZE * PHASH_SIZE // 4)
    return hex_hash


def _compute_dhash(img: Image.Image) -> str:
    """
    Compute a difference hash (dHash) — more robust to minor changes.
    
    Compares adjacent horizontal pixels.
    """
    size = PHASH_SIZE + 1
    small = img.resize((size, PHASH_SIZE), Image.LANCZOS).convert("L")
    pixels = list(small.getdata())

    bits = []
    for row in range(PHASH_SIZE):
        for col in range(PHASH_SIZE):
            idx = row * size + col
            bits.append("1" if pixels[idx] > pixels[idx + 1] else "0")

    hex_hash = hex(int("".join(bits), 2))[2:].zfill(PHASH_SIZE * PHASH_SIZE // 4)
    return hex_hash


def _hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hex hash strings."""
    if len(hash1) != len(hash2):
        return -1
    bin1 = bin(int(hash1, 16))[2:].zfill(len(hash1) * 4)
    bin2 = bin(int(hash2, 16))[2:].zfill(len(hash2) * 4)
    return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))


def analyze_hash(image_path: str) -> dict:
    """
    Generate hashes for the image and analyze for anomalies.
    
    Returns:
        dict with 'score', 'flags', and 'details' containing hashes
    """
    flags = []
    score = 0

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        return {"score": 50, "flags": [f"Could not open image: {e}"], "details": {}}

    md5 = file_md5(image_path)
    phash = _compute_phash(img)
    dhash = _compute_dhash(img)

    details = {
        "md5": md5,
        "phash": phash,
        "dhash": dhash,
        "hash_bits": PHASH_SIZE * PHASH_SIZE,
    }

    # Analyze hash characteristics
    # Very uniform hashes can indicate synthetic/solid-color images
    unique_chars_p = len(set(phash))
    unique_chars_d = len(set(dhash))

    details["phash_unique_chars"] = unique_chars_p
    details["dhash_unique_chars"] = unique_chars_d

    if unique_chars_p <= 3:
        flags.append("Perceptual hash has very low complexity — possibly a solid/gradient image, not a real screenshot")
        score += 20
    
    if unique_chars_d <= 3:
        flags.append("Difference hash has very low complexity — image lacks typical screenshot detail")
        score += 15

    if not flags:
        flags.append("Hash analysis nominal — image fingerprints generated successfully")

    return {
        "score": min(100, score),
        "flags": flags,
        "details": details,
    }
