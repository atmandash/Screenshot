"""
Screenshot Analyzers Package.

Orchestrates all analysis modules to produce a comprehensive authenticity report.
"""

from .metadata_analyzer import analyze_metadata
from .ela_analyzer import analyze_ela
from .noise_analyzer import analyze_noise
from .hash_analyzer import analyze_hash
from .compression_analyzer import analyze_compression


def run_all_analyzers(image_path: str) -> dict:
    """
    Run every analyzer on the image and return a combined results dict.
    Each key maps to an analyzer's output (including its own 'score').
    """
    results = {}

    results["metadata"] = analyze_metadata(image_path)
    results["ela"] = analyze_ela(image_path)
    results["noise"] = analyze_noise(image_path)
    results["hash"] = analyze_hash(image_path)
    results["compression"] = analyze_compression(image_path)

    return results
