"""Compatibility shim: the enforcement pipeline moved to detections.pipeline.

Kept so existing imports (`from detections.finalize import ...`) keep working.
"""
from detections.pipeline import (  # noqa: F401
    process_detection,
    finalize_detection_from_ai,
    issue_challan,
    frame_tracking,
    build_evidence,
    build_evidence_hash,
    opposite_direction,
)
