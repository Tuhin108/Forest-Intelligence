"""
Thin wrapper around DeepForest (Weinstein et al., MIT license, weecology/DeepForest).

DeepForest predicts axis-aligned bounding boxes (not crown-shaped polygons)
around individual tree crowns in RGB airborne/drone imagery, using a RetinaNet
detector pretrained on ~30M semi-supervised + ~10k hand-labeled crowns across
28 forests (see README for citation). We deliberately keep this module's
public surface to one function -- detect_crowns() -- that always returns a
plain pandas DataFrame with the same columns, so the rest of the app (and the
unit tests in tests/test_area_calc.py) never has to know DeepForest exists.

Model weights (~130 MB) download from Hugging Face Hub on first run and are
cached locally afterwards -- this requires outbound internet access to
huggingface.co the first time the app starts on a given host.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


class DetectionError(Exception):
    """Raised when detection can't be completed -- the caller should show the
    friendly 'Analysis could not be completed' message, never a raw traceback."""


_MODEL_NAME = "weecology/deepforest-tree"
_model = None  # process-level cache; the Streamlit layer also wraps this in
               # @st.cache_resource so it only loads once per running app


def get_model():
    """Load (and cache) the pretrained DeepForest tree-crown model."""
    global _model
    if _model is not None:
        return _model
    try:
        from deepforest import main
        m = main.deepforest()
        m.load_model(_MODEL_NAME)
        _model = m
        return _model
    except Exception as e:
        raise DetectionError(
            "Couldn't load the tree-crown detection model. This usually means "
            "the host couldn't reach Hugging Face Hub to download the pretrained "
            f"weights on first run. Original error: {e}"
        )


def detect_crowns(
    image_rgb: np.ndarray,
    patch_size: int = 400,
    patch_overlap: float = 0.15,
    confidence_threshold: float = 0.30,
    model=None,
) -> pd.DataFrame:
    """
    Run tiled tree-crown detection over an RGB image array.

    Returns a DataFrame with columns: tree_id, xmin, ymin, xmax, ymax, score
    (all in pixel coordinates of the input image), sorted by tree_id.
    Never returns fabricated detections -- an empty DataFrame means the model
    genuinely found nothing above threshold.
    """
    if image_rgb is None or image_rgb.size == 0:
        raise DetectionError("No image data to analyze.")

    m = model or get_model()

    try:
        h, w = image_rgb.shape[:2]
        # predict_image is more reliable than predict_tile for small images
        # (like our bundled 400x400 demo scene); predict_tile is used for
        # anything bigger than one patch.
        if max(h, w) <= patch_size:
            result = m.predict_image(image=image_rgb.astype(np.float32))
        else:
            result = m.predict_tile(
                image=image_rgb.astype(np.float32),
                patch_size=patch_size,
                patch_overlap=patch_overlap,
            )
    except Exception as e:
        raise DetectionError(f"Analysis could not be completed. Your original imagery "
                              f"has not been modified. ({e})")

    if result is None or len(result) == 0:
        return pd.DataFrame(columns=["tree_id", "xmin", "ymin", "xmax", "ymax", "score"])

    df = pd.DataFrame(result)
    # DeepForest's returned frame may include a `geometry` column (shapely boxes)
    # in newer versions; xmin/ymin/xmax/ymax are always present either way.
    required = {"xmin", "ymin", "xmax", "ymax", "score"}
    missing = required - set(df.columns)
    if missing:
        raise DetectionError(f"Unexpected model output format (missing columns: {missing}).")

    df = df[df["score"] >= confidence_threshold].reset_index(drop=True)
    df["tree_id"] = range(len(df))
    return df[["tree_id", "xmin", "ymin", "xmax", "ymax", "score"]].copy()
