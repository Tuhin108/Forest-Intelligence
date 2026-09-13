"""
Reusable, framework-agnostic UI helpers: drawing annotated images and
generating template-based natural-language summaries.

Nothing in this file calls an LLM. The "forest story" text is assembled from
an explicit template filled in with numbers computed elsewhere (src/geo/area.py)
-- it never invents a species, a cause, or an outcome. This mirrors the
brief's own rule: an LLM (if used at all) may narrate structured, verified
measurements, but is never the source of the measurements themselves.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

COLOR_RELIABLE = (46, 125, 50)      # green
COLOR_LOW_CONF = (255, 179, 0)      # amber
COLOR_OVERLAP = (211, 47, 47)       # red
COLOR_SHADOW = (30, 136, 229)       # blue


def _status_color(tree_id: int, review_indices: dict) -> tuple:
    if tree_id in set(review_indices.get("overlap", [])):
        return COLOR_OVERLAP
    if tree_id in set(review_indices.get("low_confidence", [])):
        return COLOR_LOW_CONF
    if tree_id in set(review_indices.get("shadow", [])):
        return COLOR_SHADOW
    return COLOR_RELIABLE


def draw_annotated_image(
    image_rgb: np.ndarray,
    detections: pd.DataFrame,
    mode: str = "detected",
    review_indices: Optional[dict] = None,
    highlight_tree_id: Optional[int] = None,
) -> Image.Image:
    """
    mode:
      "original" -- returns the image untouched
      "detected" -- every crown outlined in a single neutral color
      "review"   -- crowns colored by their review-flag status (green = clean,
                    amber/red/blue = flagged), so the flags are visually legible
    highlight_tree_id: if set, draws that one box thicker/brighter regardless of mode
    """
    img = Image.fromarray(image_rgb.astype(np.uint8)).convert("RGB")
    if mode == "original" or detections is None or len(detections) == 0:
        return img

    draw = ImageDraw.Draw(img)
    review_indices = review_indices or {"overlap": [], "low_confidence": [], "shadow": []}

    for _, row in detections.iterrows():
        tid = int(row["tree_id"])
        box = (row["xmin"], row["ymin"], row["xmax"], row["ymax"])
        if mode == "review":
            color = _status_color(tid, review_indices)
        else:
            color = COLOR_RELIABLE
        width = 1
        if highlight_tree_id is not None and tid == highlight_tree_id:
            color = (255, 235, 59)  # bright yellow highlight, overrides status color
            width = 4
        draw.rectangle(box, outline=color, width=width)
    return img


def crown_status(tree_id: int, review_indices: dict) -> str:
    if tree_id in set(review_indices.get("overlap", [])):
        return "Review — dense overlap"
    if tree_id in set(review_indices.get("low_confidence", [])):
        return "Review — low confidence"
    if tree_id in set(review_indices.get("shadow", [])):
        return "Review — shadow-affected"
    return "Reliable"


def why_was_this_counted(tree_id: int, score: float, review_indices: dict) -> str:
    status = crown_status(tree_id, review_indices)
    base = (f"The model identified a distinct crown-shaped region here with "
            f"{score:.0%} confidence")
    if status == "Reliable":
        return base + " and enough separation from neighboring crowns to count it on its own."
    if "overlap" in status:
        return base + ", but it overlaps heavily with a neighboring detection — treat the " \
                       "boundary between the two as uncertain."
    if "low confidence" in status:
        return base + ", which is below the threshold this tool treats as reliable — worth " \
                       "a second look."
    if "shadow" in status:
        return base + ", though part of this crown falls in a darker region of the image, " \
                       "which can hide its true edges."
    return base + "."


def generate_forest_story(metrics, has_kml: bool = False) -> str:
    """Template-based natural-language summary from *already-computed* numbers.
    No invented facts: species, health, biodiversity, and carbon are never
    mentioned here because this tool has no basis to claim them."""
    if metrics.tree_count == 0:
        return ("No reliable tree crowns were detected in the analyzed area. This could mean "
                "the scene genuinely has little tree cover, or that the imagery is unsuitable "
                "for crown detection (see Limitations below).")

    area_phrase = (f"about {metrics.canopy_area_m2:,.0f} m²" if metrics.has_physical_units
                   else f"about {metrics.coverage_pct:.0f}% of the analyzed image (in pixel terms — "
                        f"no physical scale is available for this image)")
    reliability_phrase = {
        "HIGH": "The detections are consistently confident and well-separated.",
        "MODERATE": "Some regions are less certain — see the flagged review areas below.",
        "LOW": "A meaningful share of this result needs manual review before you rely on it.",
    }[metrics.reliability]

    return (
        f"The analyzed area contains {metrics.tree_count} detected tree crowns covering "
        f"{area_phrase}, roughly {metrics.coverage_pct:.0f}% of the analyzed area. "
        f"{reliability_phrase}"
    )


WHY_SHOULD_I_CARE = {
    "tree_count": (
        "Counting trees from imagery is genuinely difficult — crowns overlap, shadows hide "
        "edges, and small or young trees can be missed entirely. That's why this number is "
        "presented as an estimate with a reliability rating, not a ground-truth inventory."
    ),
    "canopy_coverage": (
        "How much of an area is covered by tree canopy affects shade, how rainfall moves "
        "through a landscape, and the physical structure available for habitat — it's a "
        "meaningful landscape-scale number on its own, independent of species or health."
    ),
    "canopy_loss_scenario": (
        "This slider shows the geometric effect of losing a share of the currently-detected "
        "canopy — it is not a prediction of what would actually happen ecologically, and it "
        "does not imply any particular cause."
    ),
}

LIMITATIONS = [
    "Crown detections are bounding boxes, not hand-segmented crown outlines — reported "
    "\"canopy area\" is the extent of each box, which tends to slightly overstate the true "
    "irregular shape of a crown.",
    "Physical-unit area figures (m²) are only available when the source image carries usable "
    "spatial reference metadata; otherwise figures are pixel-based.",
    "Dense, overlapping canopy and heavily shadowed regions are flagged, but flagged ≠ fixed — "
    "those counts are still estimates.",
    "The pretrained model was trained primarily on specific forest sites and sensor types; "
    "performance on a very different forest type, altitude, or camera can vary and hasn't been "
    "independently validated here.",
    "This tool does not and cannot determine species, age, biomass, ecological health, "
    "biodiversity, or carbon stock/sequestration from crown imagery alone — those require "
    "additional data and validated methodology this tool does not have.",
    "The shadow-affected flag is a brightness heuristic, not true shadow detection — it's a "
    "useful signal, not a certainty.",
]

FAILURE_MESSAGES = {
    "no_image": "Please upload a forest image.",
    "unsupported_format": "This image format isn't supported.",
    "no_georeference": "We can detect crowns, but physical area estimates aren't available "
                        "without spatial reference information — here are the pixel-based "
                        "numbers instead.",
    "too_coarse": "This image looks too low-resolution for reliable individual crown detection.",
    "no_crowns": "No reliable crowns were detected. Try a clearer or higher-resolution image.",
    "kml_no_overlap": "The boundary you uploaded doesn't overlap the image.",
    "model_error": "Analysis could not be completed. Your original image hasn't been modified.",
}
