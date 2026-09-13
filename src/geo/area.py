"""
Turns raw crown detections into the numbers the UI shows -- canopy area,
coverage, reliability, review flags, size distribution. This module is
intentionally decoupled from the detector itself: it takes a plain pandas
DataFrame of boxes + scores + a per-crown brightness sample, so it can be
unit-tested against synthetic detections without ever loading a model
(see tests/test_area_calc.py).

Every number that reaches the UI is computed here from the actual detections
passed in. Nothing is hardcoded, and nothing here ever infers species,
biomass, carbon, or ecological health -- that's a hard boundary, not a
detail left for later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

CONFIDENCE_THRESHOLD = 0.30          # DeepForest's own documented default operating point
LOW_CONFIDENCE_THRESHOLD = 0.50      # below this, a detection is flagged for review
OVERLAP_IOU_THRESHOLD = 0.10         # above this with a neighbor, flagged as dense/ambiguous
SHADOW_BRIGHTNESS_PERCENTILE = 25    # crowns darker than the 25th percentile of the
                                     # scene are flagged as possibly shadow-affected


def _box_iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class ForestMetrics:
    tree_count: int
    analyzed_area_px2: float
    canopy_area_px2: float
    coverage_pct: float
    has_physical_units: bool
    analyzed_area_m2: Optional[float]
    canopy_area_m2: Optional[float]
    avg_crown_area_m2: Optional[float]
    avg_crown_area_px2: float
    size_distribution: dict           # {"small": pct, "medium": pct, "large": pct}
    reliability: str                  # "HIGH" | "MODERATE" | "LOW"
    reliability_reasons: list = field(default_factory=list)
    review_flags: dict = field(default_factory=dict)   # counts by category
    review_indices: dict = field(default_factory=dict) # detection indices by category
    unit_caveat: str = ""


def compute_forest_metrics(
    detections: pd.DataFrame,
    image_width: int,
    image_height: int,
    gsd_m: Optional[float],
    gray_image: Optional[np.ndarray] = None,
) -> ForestMetrics:
    """
    detections: DataFrame with columns xmin, ymin, xmax, ymax, score (0-1).
    gsd_m: meters-per-pixel if the source image is georeferenced, else None.
    gray_image: optional single-channel brightness array (same size as the
        source image), used only for the shadow heuristic.
    """
    n = len(detections)
    analyzed_area_px2 = float(image_width * image_height)

    if n == 0:
        return ForestMetrics(
            tree_count=0, analyzed_area_px2=analyzed_area_px2, canopy_area_px2=0.0,
            coverage_pct=0.0, has_physical_units=gsd_m is not None,
            analyzed_area_m2=(analyzed_area_px2 * gsd_m ** 2) if gsd_m else None,
            canopy_area_m2=0.0 if gsd_m else None, avg_crown_area_m2=None,
            avg_crown_area_px2=0.0, size_distribution={"small": 0, "medium": 0, "large": 0},
            reliability="LOW", reliability_reasons=["No crowns were detected in this image."],
            review_flags={"overlap": 0, "low_confidence": 0, "shadow": 0},
            review_indices={"overlap": [], "low_confidence": [], "shadow": []},
            unit_caveat=_unit_caveat(gsd_m),
        )

    boxes = detections[["xmin", "ymin", "xmax", "ymax"]].to_numpy(dtype=float)
    widths = boxes[:, 2] - boxes[:, 0]
    heights = boxes[:, 3] - boxes[:, 1]
    crown_areas_px2 = widths * heights
    scores = detections["score"].to_numpy(dtype=float)

    canopy_area_px2 = float(crown_areas_px2.sum())
    coverage_pct = min(100.0, 100.0 * canopy_area_px2 / analyzed_area_px2) if analyzed_area_px2 else 0.0
    avg_crown_area_px2 = float(crown_areas_px2.mean())

    has_physical = gsd_m is not None
    px2_to_m2 = (gsd_m ** 2) if gsd_m else None
    canopy_area_m2 = round(canopy_area_px2 * px2_to_m2, 0) if has_physical else None
    analyzed_area_m2 = round(analyzed_area_px2 * px2_to_m2, 0) if has_physical else None
    avg_crown_area_m2 = round(avg_crown_area_px2 * px2_to_m2, 1) if has_physical else None

    # --- size distribution by tertile of the *actual* observed crown-area
    # distribution, so "small/medium/large" always means something for *this*
    # scene rather than an arbitrary fixed cutoff that could be meaningless
    # for a stand of saplings or a stand of giants.
    size_distribution = _size_distribution(crown_areas_px2)

    # --- review flags ---------------------------------------------------
    low_conf_idx = list(np.where(scores < LOW_CONFIDENCE_THRESHOLD)[0])

    overlap_idx = set()
    for i in range(n):
        for j in range(i + 1, n):
            if _box_iou(boxes[i], boxes[j]) >= OVERLAP_IOU_THRESHOLD:
                overlap_idx.add(i)
                overlap_idx.add(j)
    overlap_idx = sorted(overlap_idx)

    shadow_idx = []
    if gray_image is not None and gray_image.size > 0:
        threshold = np.percentile(gray_image, SHADOW_BRIGHTNESS_PERCENTILE)
        h, w = gray_image.shape[:2]
        for i, (x1, y1, x2, y2) in enumerate(boxes):
            xi1, yi1 = max(0, int(x1)), max(0, int(y1))
            xi2, yi2 = min(w, int(x2)), min(h, int(y2))
            if xi2 <= xi1 or yi2 <= yi1:
                continue
            crop_mean = gray_image[yi1:yi2, xi1:xi2].mean()
            if crop_mean <= threshold:
                shadow_idx.append(i)

    review_flags = {
        "overlap": len(overlap_idx),
        "low_confidence": len(low_conf_idx),
        "shadow": len(shadow_idx),
    }
    review_indices = {
        "overlap": overlap_idx, "low_confidence": low_conf_idx, "shadow": shadow_idx,
    }

    reliability, reasons = _score_reliability(n, scores, review_flags, has_physical)

    return ForestMetrics(
        tree_count=n, analyzed_area_px2=analyzed_area_px2, canopy_area_px2=canopy_area_px2,
        coverage_pct=round(coverage_pct, 1), has_physical_units=has_physical,
        analyzed_area_m2=analyzed_area_m2, canopy_area_m2=canopy_area_m2,
        avg_crown_area_m2=avg_crown_area_m2, avg_crown_area_px2=round(avg_crown_area_px2, 1),
        size_distribution=size_distribution, reliability=reliability, reliability_reasons=reasons,
        review_flags=review_flags, review_indices=review_indices,
        unit_caveat=_unit_caveat(gsd_m),
    )


def _size_distribution(crown_areas_px2: np.ndarray) -> dict:
    if len(crown_areas_px2) < 3:
        return {"small": 100, "medium": 0, "large": 0} if len(crown_areas_px2) else \
               {"small": 0, "medium": 0, "large": 0}
    t1, t2 = np.percentile(crown_areas_px2, [33.3, 66.7])
    small = int(np.sum(crown_areas_px2 <= t1))
    large = int(np.sum(crown_areas_px2 > t2))
    medium = len(crown_areas_px2) - small - large
    n = len(crown_areas_px2)
    return {
        "small": round(100 * small / n),
        "medium": round(100 * medium / n),
        "large": round(100 * large / n),
    }


def _score_reliability(n, scores, review_flags, has_physical):
    reasons = []
    low_conf_frac = review_flags["low_confidence"] / n if n else 0
    overlap_frac = review_flags["overlap"] / n if n else 0
    shadow_frac = review_flags["shadow"] / n if n else 0

    concerns = 0
    if low_conf_frac > 0.35:
        reasons.append(f"⚠ {review_flags['low_confidence']} of {n} detections are below the "
                        f"confidence threshold ({LOW_CONFIDENCE_THRESHOLD:.0%}).")
        concerns += 1
    else:
        reasons.append(f"✓ Most detections ({n - review_flags['low_confidence']} of {n}) are "
                        f"above the confidence threshold.")

    if overlap_frac > 0.30:
        reasons.append(f"⚠ {review_flags['overlap']} crowns overlap heavily with a neighbor -- "
                        f"dense canopy makes individual crowns harder to separate.")
        concerns += 1
    else:
        reasons.append("✓ Most crowns are clearly separable from their neighbors.")

    if shadow_frac > 0.25:
        reasons.append(f"⚠ {review_flags['shadow']} crowns fall in the darker part of the "
                        f"image -- shadowed regions are harder to analyze from RGB alone.")
        concerns += 1

    if not has_physical:
        reasons.append("⚠ This image has no spatial reference, so area figures are "
                        "pixel-based estimates, not physical measurements.")
        concerns += 1

    if n < 5:
        reasons.append("⚠ Very few crowns were detected -- summary statistics (like size "
                        "distribution) are less meaningful on such a small sample.")
        concerns += 1

    if concerns == 0:
        level = "HIGH"
    elif concerns <= 2:
        level = "MODERATE"
    else:
        level = "LOW"
    return level, reasons


def _unit_caveat(gsd_m: Optional[float]) -> str:
    if gsd_m is None:
        return ("No spatial reference was found in this image, so canopy area is reported "
                "in pixel terms (% of the image), not square meters.")
    return (f"Physical area estimated from the image's spatial reference "
            f"(~{gsd_m:.3f} m/pixel). Treat as an approximation, not a survey-grade "
            f"measurement.")


def simulate_canopy_loss(metrics: ForestMetrics, loss_pct: float) -> dict:
    """Pure geometry -- explicitly NOT an ecological or carbon prediction.
    Scales down the currently-estimated canopy area/coverage by the given
    hypothetical loss percentage and returns the resulting numbers."""
    remaining_frac = max(0.0, 1.0 - loss_pct / 100.0)
    result = {
        "remaining_coverage_pct": round(metrics.coverage_pct * remaining_frac, 1),
        "affected_area_px2": round(metrics.canopy_area_px2 * (loss_pct / 100.0), 0),
    }
    if metrics.has_physical_units and metrics.canopy_area_m2 is not None:
        result["affected_area_m2"] = round(metrics.canopy_area_m2 * (loss_pct / 100.0), 0)
        result["remaining_area_m2"] = round(metrics.canopy_area_m2 * remaining_frac, 0)
    return result
