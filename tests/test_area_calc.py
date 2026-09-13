"""
These tests exercise src/geo/area.py against hand-built synthetic detections --
no model, no image, no network. They exist to prove the math (area, coverage,
reliability, review flags) is correct in isolation from DeepForest, since the
sandbox this was built in cannot download the model's pretrained weights
(see docs/known_limitations.md). Run with: python -m pytest tests/ -v
"""
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.geo.area import compute_forest_metrics, simulate_canopy_loss


def make_detections(boxes, scores):
    return pd.DataFrame({
        "xmin": [b[0] for b in boxes], "ymin": [b[1] for b in boxes],
        "xmax": [b[2] for b in boxes], "ymax": [b[3] for b in boxes],
        "score": scores,
    })


def test_empty_detections():
    d = make_detections([], [])
    m = compute_forest_metrics(d, 1000, 1000, gsd_m=0.1)
    assert m.tree_count == 0
    assert m.coverage_pct == 0.0
    assert m.reliability == "LOW"


def test_simple_non_overlapping_grid():
    # 4 non-overlapping 10x10px boxes in a 100x100 image, high confidence.
    # Note: with only 4 detections and no spatial reference, the reliability
    # scorer is *expected* to land on MODERATE rather than HIGH -- a small
    # sample size and missing georeference are each their own honest caveat,
    # by design (see _score_reliability). That's covered separately below.
    boxes = [(0, 0, 10, 10), (20, 20, 30, 30), (40, 40, 50, 50), (60, 60, 70, 70)]
    scores = [0.9, 0.85, 0.92, 0.88]
    d = make_detections(boxes, scores)
    m = compute_forest_metrics(d, 100, 100, gsd_m=None)
    assert m.tree_count == 4
    assert m.canopy_area_px2 == 400  # 4 * 100
    assert m.coverage_pct == 4.0     # 400 / 10000 * 100
    assert m.review_flags["overlap"] == 0
    assert m.review_flags["low_confidence"] == 0
    assert m.has_physical_units is False
    assert m.canopy_area_m2 is None
    assert m.reliability == "MODERATE"


def test_high_reliability_needs_enough_trees_and_georeference():
    # Same clean, non-overlapping, high-confidence pattern, but with a
    # georeferenced image and a sample size above the small-n cutoff --
    # this is the actual "everything checks out" case.
    boxes = [(i * 15, i * 15, i * 15 + 10, i * 15 + 10) for i in range(8)]
    scores = [0.9] * 8
    d = make_detections(boxes, scores)
    m = compute_forest_metrics(d, 500, 500, gsd_m=0.1)
    assert m.reliability == "HIGH"


def test_physical_units_when_gsd_present():
    boxes = [(0, 0, 10, 10)]
    d = make_detections(boxes, [0.9])
    gsd = 0.1  # 0.1 m/pixel -> each pixel is 0.01 m^2
    m = compute_forest_metrics(d, 100, 100, gsd_m=gsd)
    assert m.has_physical_units is True
    # 100 px^2 crown * (0.1*0.1) m^2/px = 1.0 m^2
    assert m.canopy_area_m2 == 1.0
    assert m.analyzed_area_m2 == 100.0  # 10000 px^2 * 0.01


def test_overlap_flagging():
    # two heavily-overlapping boxes should both get flagged
    boxes = [(0, 0, 20, 20), (5, 5, 25, 25), (200, 200, 210, 210)]
    scores = [0.9, 0.9, 0.9]
    d = make_detections(boxes, scores)
    m = compute_forest_metrics(d, 500, 500, gsd_m=None)
    assert m.review_flags["overlap"] == 2
    assert 0 in m.review_indices["overlap"] and 1 in m.review_indices["overlap"]
    assert 2 not in m.review_indices["overlap"]


def test_low_confidence_flagging_and_reliability_drop():
    boxes = [(i * 15, i * 15, i * 15 + 10, i * 15 + 10) for i in range(10)]
    scores = [0.2] * 8 + [0.9, 0.9]  # 80% low-confidence
    d = make_detections(boxes, scores)
    m = compute_forest_metrics(d, 500, 500, gsd_m=None)
    assert m.review_flags["low_confidence"] == 8
    assert m.reliability in ("MODERATE", "LOW")


def test_size_distribution_sums_to_100():
    rng = np.random.default_rng(42)
    n = 30
    sizes = rng.uniform(5, 40, n)
    boxes = []
    x = 0
    for s in sizes:
        boxes.append((x, 0, x + s, s))
        x += s + 5
    scores = [0.8] * n
    d = make_detections(boxes, scores)
    m = compute_forest_metrics(d, int(x) + 10, 100, gsd_m=None)
    total = sum(m.size_distribution.values())
    assert 99 <= total <= 101  # rounding tolerance


def test_scenario_explorer_is_pure_geometry():
    boxes = [(0, 0, 10, 10)] * 10
    d = make_detections(boxes, [0.9] * 10)
    m = compute_forest_metrics(d, 1000, 1000, gsd_m=0.5)
    base_area = m.canopy_area_m2
    result = simulate_canopy_loss(m, 20)
    assert result["remaining_area_m2"] == round(base_area * 0.8, 0)
    assert result["remaining_coverage_pct"] == round(m.coverage_pct * 0.8, 1)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
