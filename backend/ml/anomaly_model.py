"""
Loads model.joblib once at import time and scores tourist location
history against it. If the model file isn't there (forgot to run
train_model.py), this fails loud at startup instead of silently
skipping ML scoring - better to know immediately than wonder later why
nothing's ever flagged.
"""
from pathlib import Path

import joblib

from .features import build_features, FEATURE_NAMES

MODEL_PATH = Path(__file__).parent / "model.joblib"

try:
    _model = joblib.load(MODEL_PATH)
except FileNotFoundError as e:
    raise RuntimeError(
        f"{MODEL_PATH} not found. Run `python3 ml/train_model.py` from the "
        f"backend/ directory once before starting the server."
    ) from e


def score(points: list[dict], now, zone_entries_24h: int) -> tuple[bool, float, list[float]]:
    """Returns (is_anomaly, score, feature_vector). Lower score = more anomalous."""
    features = build_features(points, now, zone_entries_24h)
    pred = _model.predict([features])[0]
    raw_score = float(_model.decision_function([features])[0])
    return pred == -1, raw_score, features


__all__ = ["score", "FEATURE_NAMES"]
