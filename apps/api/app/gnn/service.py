"""Shared GNN inference singleton — avoids circular imports."""
from __future__ import annotations

_gnn_instance = None


def get_gnn_inference():
    """Return the globally loaded GNNInference instance, or None if not yet loaded."""
    return _gnn_instance


def set_gnn_inference(instance) -> None:
    """Register the loaded GNNInference instance for use across the app."""
    global _gnn_instance
    _gnn_instance = instance
