"""
Image loading + georeference detection.

The single most important honesty decision in this whole app lives here:
we only ever report physical (m^2) areas when we can actually derive a
ground sample distance (GSD) from real spatial-reference metadata. If an
image has no CRS/transform (a plain photo, a screenshot, a non-georeferenced
export), we say so explicitly and fall back to pixel-based reporting rather
than inventing a scale.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np
import rasterio
from rasterio.errors import RasterioIOError, NotGeoreferencedWarning
from PIL import Image

# Rasterio warns loudly when a file has no geotransform -- we handle that case
# explicitly and deliberately (has_crs=False), so the warning is expected noise,
# not a sign something's wrong. Silencing it keeps deploy logs readable.
warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)


class UnsupportedImageError(Exception):
    """Raised when an uploaded file can't be read as an image at all."""


@dataclass
class LoadedImage:
    array: np.ndarray            # H x W x 3 uint8, RGB
    width: int
    height: int
    has_crs: bool
    gsd_x_m: Optional[float]     # meters per pixel, x direction
    gsd_y_m: Optional[float]     # meters per pixel, y direction
    crs: Optional[str]
    bounds_lonlat: Optional[tuple]  # (minlon, minlat, maxlon, maxlat), for KML overlap checks
    source_note: str             # human-readable explanation of the georeference status

    @property
    def gsd_m(self) -> Optional[float]:
        """A single representative GSD (meters/pixel), averaged, for simple area math."""
        if self.gsd_x_m is None or self.gsd_y_m is None:
            return None
        return (self.gsd_x_m + self.gsd_y_m) / 2.0


_MIN_PIXELS_TO_ATTEMPT = 64   # floor below which we won't even try (too small to be a real scene)
_GOOD_GSD_M = 0.3             # <= this, comparable to the imagery the model was trained on
_COARSE_GSD_M = 1.0           # <= this, crown separation gets marginal; above it, satellite-like


def _degrees_to_meters(gsd_x_deg: float, gsd_y_deg: float, center_lat_deg: float):
    """Approximate conversion from a geographic (lon/lat degree) pixel size to meters,
    using the standard WGS84 approximation (111,320 m per degree latitude, scaled by
    cos(latitude) for longitude). This is a defensible approximation for a rough area
    estimate, not a survey-grade transform -- documented as such in the UI/technical view.
    """
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(center_lat_deg))
    return abs(gsd_x_deg * m_per_deg_lon), abs(gsd_y_deg * m_per_deg_lat)


def load_image(path: str) -> LoadedImage:
    """Load an image file, trying rasterio first (so GeoTIFFs keep their spatial
    reference), falling back to plain Pillow for ordinary JPG/PNG screenshots.
    """
    try:
        with rasterio.open(path) as src:
            arr = src.read()  # bands, H, W
            if arr.shape[0] == 1:
                arr = np.repeat(arr, 3, axis=0)
            elif arr.shape[0] > 3:
                arr = arr[:3]
            arr = np.transpose(arr, (1, 2, 0))
            if arr.dtype != np.uint8:
                # Stretch to 8-bit for display / detection; keep it simple & defensible.
                arr = arr.astype(np.float32)
                lo, hi = np.percentile(arr, 2), np.percentile(arr, 98)
                if hi <= lo:
                    hi = lo + 1
                arr = np.clip((arr - lo) / (hi - lo), 0, 1)
                arr = (arr * 255).astype(np.uint8)

            has_crs = src.crs is not None and src.transform is not None and not src.transform.is_identity
            gsd_x_m = gsd_y_m = None
            bounds_lonlat = None
            crs_str = str(src.crs) if src.crs else None

            if has_crs:
                px_w = abs(src.transform.a)
                px_h = abs(src.transform.e)
                if src.crs.is_geographic:
                    # Units are degrees -- approximate using image center latitude.
                    b = src.bounds
                    center_lat = (b.top + b.bottom) / 2.0
                    gsd_x_m, gsd_y_m = _degrees_to_meters(px_w, px_h, center_lat)
                    bounds_lonlat = (b.left, b.bottom, b.right, b.top)
                else:
                    # Already projected in linear units -- assume meters (the common case
                    # for UTM-projected orthomosaics, which is what airborne/drone
                    # collections almost always use).
                    gsd_x_m, gsd_y_m = px_w, px_h
                    try:
                        from rasterio.warp import transform_bounds
                        bounds_lonlat = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
                    except Exception:
                        bounds_lonlat = None

            note = (
                f"Georeferenced ({crs_str}); ~{gsd_x_m:.3f} m/pixel"
                if has_crs and gsd_x_m
                else "No spatial reference found in this file -- physical-area estimates "
                     "will not be available, only pixel-based measurements."
            )
            return LoadedImage(
                array=arr, width=arr.shape[1], height=arr.shape[0],
                has_crs=has_crs, gsd_x_m=gsd_x_m, gsd_y_m=gsd_y_m,
                crs=crs_str, bounds_lonlat=bounds_lonlat, source_note=note,
            )
    except RasterioIOError:
        pass  # not a raster rasterio understands as georeferenced -- fall back to Pillow
    except Exception:
        pass

    try:
        img = Image.open(path).convert("RGB")
        arr = np.array(img)
        return LoadedImage(
            array=arr, width=arr.shape[1], height=arr.shape[0],
            has_crs=False, gsd_x_m=None, gsd_y_m=None, crs=None, bounds_lonlat=None,
            source_note="Plain image file with no spatial reference -- physical-area "
                        "estimates will not be available, only pixel-based measurements.",
        )
    except Exception as e:
        raise UnsupportedImageError(f"Could not read this file as an image: {e}")


def resolution_quality(loaded: LoadedImage) -> tuple[str, str]:
    """Returns (quality, reason) where quality is one of "good" / "coarse" / "too_low".

    The honest signal here is *ground* resolution (meters/pixel), not raw pixel
    dimensions -- a 400x400 image at 0.1 m/pixel (like our bundled demo scene)
    resolves individual crowns just fine, while a 4000x4000 image at 5 m/pixel
    (cropped satellite imagery) fundamentally can't, regardless of how many
    pixels it has. So:
      - If we know the GSD (georeferenced image), classify on GSD.
      - If we don't (a plain photo with no spatial reference), we genuinely
        cannot verify ground resolution from pixel count alone -- we only
        reject images too small to be a real scene at all, and otherwise
        say plainly that ground resolution is unverified.
    """
    smaller_dim = min(loaded.width, loaded.height)
    if smaller_dim < _MIN_PIXELS_TO_ATTEMPT:
        return "too_low", "This image is too small to analyze."

    if loaded.gsd_m is not None:
        if loaded.gsd_m <= _GOOD_GSD_M:
            return "good", f"Ground resolution ~{loaded.gsd_m:.2f} m/pixel is well within " \
                           f"the range individual crowns can be resolved at."
        if loaded.gsd_m <= _COARSE_GSD_M:
            return "coarse", f"Ground resolution ~{loaded.gsd_m:.2f} m/pixel is borderline -- " \
                              f"crown detection may miss smaller or closely-spaced trees."
        return "too_low", f"Ground resolution ~{loaded.gsd_m:.1f} m/pixel is too coarse for " \
                           f"individual tree crowns (this is satellite-scale, not airborne/drone-scale)."

    return "coarse", ("This image has no spatial reference, so true ground resolution can't be "
                       "verified -- results should be treated with extra caution.")
