"""
Trains the anomaly detection model on synthetic data and saves it to
model.joblib. Rerun this any time features.py or the sample generation
below changes shape.

There's no real tourist movement dataset to train on (obviously - this
is a hackathon prototype, not a deployed system with a year of GPS
logs), so this generates synthetic "normal" tourist behavior and mixes
in a smaller set of the anomaly types the problem statement calls out:
prolonged inactivity, implausible speed jumps, erratic route deviation,
and repeated risk-zone entries. IsolationForest is the right model for
this - it's built for exactly this "learn what normal looks like, flag
what doesn't fit" setup, and it doesn't need labeled anomalies to train
on, just an assumed contamination rate.

This is explicitly a placeholder for real training data. Swap in actual
anonymized location logs the moment there's enough of them and this
becomes a real model instead of a reasonable simulation of one.

Usage:
    python3 train_model.py
"""
import random
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from features import FEATURE_NAMES

random.seed(42)
np.random.seed(42)


def normal_sample():
    """A tourist doing ordinary sightseeing: walking pace to light traffic,
    checks in every several minutes, sticks to a small area, rarely
    wanders into a flagged zone."""
    avg_speed = max(0, np.random.normal(12, 8))       # walking to auto-rickshaw pace
    max_speed = avg_speed + max(0, np.random.normal(8, 6))
    gap_minutes = max(0, np.random.normal(12, 8))       # checks in fairly often
    path_std = max(0, np.random.normal(0.8, 0.5))       # sticks to a small area
    zone_entries = np.random.choice([0, 0, 0, 0, 1], p=[0.6, 0.15, 0.1, 0.1, 0.05])
    return [avg_speed, max_speed, gap_minutes, path_std, float(zone_entries)]


def anomaly_sample():
    """One of the anomaly types the problem statement names, picked at random."""
    kind = random.choice(["inactivity", "speed_spoof", "route_deviation", "zone_pattern"])

    if kind == "inactivity":
        avg_speed = max(0, np.random.normal(5, 4))
        max_speed = avg_speed + max(0, np.random.normal(3, 2))
        gap_minutes = np.random.uniform(90, 400)          # gone dark for a long stretch
        path_std = max(0, np.random.normal(0.5, 0.3))
        zone_entries = np.random.choice([0, 1])

    elif kind == "speed_spoof":
        avg_speed = np.random.uniform(150, 600)            # not a real travel speed
        max_speed = avg_speed + np.random.uniform(50, 300)
        gap_minutes = max(0, np.random.normal(10, 5))
        path_std = np.random.uniform(5, 20)
        zone_entries = np.random.choice([0, 1])

    elif kind == "route_deviation":
        avg_speed = max(0, np.random.normal(20, 10))
        max_speed = avg_speed + max(0, np.random.normal(15, 8))
        gap_minutes = max(0, np.random.normal(15, 10))
        path_std = np.random.uniform(8, 30)                 # wandering way off any normal radius
        zone_entries = np.random.choice([0, 1, 2])

    else:  # zone_pattern
        avg_speed = max(0, np.random.normal(12, 6))
        max_speed = avg_speed + max(0, np.random.normal(8, 5))
        gap_minutes = max(0, np.random.normal(12, 6))
        path_std = max(0, np.random.normal(1.5, 1))
        zone_entries = np.random.uniform(4, 10)              # repeatedly walking into flagged zones

    return [avg_speed, max_speed, gap_minutes, path_std, float(zone_entries)]


def build_dataset(n_normal=1900, n_anomaly=100):
    X = [normal_sample() for _ in range(n_normal)] + [anomaly_sample() for _ in range(n_anomaly)]
    return np.array(X)


def main():
    X = build_dataset()
    contamination = 100 / (1900 + 100)  # matches the mix ratio above

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
    )
    model.fit(X)

    joblib.dump(model, "model.joblib")

    # quick sanity check against a few obvious cases, printed so it's
    # visible right after training instead of trusting it blindly
    checks = {
        "ordinary sightseeing": [10, 15, 8, 0.6, 0],
        "gone dark 3 hours": [4, 6, 180, 0.4, 0],
        "gps teleport": [300, 450, 5, 10, 0],
        "wandering off itinerary": [18, 25, 12, 20, 1],
        "camping near border zone repeatedly": [10, 14, 10, 1.2, 6],
    }
    print(f"Trained on {len(X)} samples (contamination={contamination:.3f})")
    print(f"Features: {FEATURE_NAMES}")
    print("-" * 60)
    for label, features in checks.items():
        pred = model.predict([features])[0]        # -1 = anomaly, 1 = normal
        score = model.decision_function([features])[0]  # lower = more anomalous
        flag = "ANOMALY" if pred == -1 else "normal"
        print(f"{label:35s} -> {flag:8s} (score={score:+.3f})")


if __name__ == "__main__":
    main()
