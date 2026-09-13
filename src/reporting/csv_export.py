"""CSV export -- only ever includes fields that actually exist on the
detections, never invented columns like species or carbon."""
from __future__ import annotations

import io
import pandas as pd


def build_csv(detections: pd.DataFrame, review_indices: dict, gsd_m: float | None) -> str:
    df = detections.copy()
    df["width_px"] = df["xmax"] - df["xmin"]
    df["height_px"] = df["ymax"] - df["ymin"]
    df["crown_area_px2"] = df["width_px"] * df["height_px"]
    df["centroid_x_px"] = (df["xmin"] + df["xmax"]) / 2
    df["centroid_y_px"] = (df["ymin"] + df["ymax"]) / 2

    if gsd_m:
        df["crown_area_m2"] = (df["crown_area_px2"] * gsd_m ** 2).round(2)

    status = []
    overlap_set = set(review_indices.get("overlap", []))
    low_conf_set = set(review_indices.get("low_confidence", []))
    shadow_set = set(review_indices.get("shadow", []))
    for tid in df["tree_id"]:
        flags = []
        if tid in overlap_set:
            flags.append("dense_overlap")
        if tid in low_conf_set:
            flags.append("low_confidence")
        if tid in shadow_set:
            flags.append("shadow_affected")
        status.append("reliable" if not flags else "review:" + "+".join(flags))
    df["status"] = status

    cols = ["tree_id", "centroid_x_px", "centroid_y_px", "crown_area_px2"]
    if gsd_m:
        cols.append("crown_area_m2")
    cols += ["score", "status"]

    buf = io.StringIO()
    df[cols].to_csv(buf, index=False)
    return buf.getvalue()
