"""
Minimal, dependency-light KML parsing.

We deliberately don't pull in a full KML library (fastkml, etc.) -- a hackathon
weekend judge's AOI file is almost always one or a few <Placemark><Polygon>
blocks, and a namespace-agnostic ElementTree walk handles that reliably without
adding a fragile dependency. If it can't find a polygon, it fails loudly with a
clear message rather than silently ignoring the file.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET
from typing import Optional

from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union


class KMLParseError(Exception):
    pass


def _local_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_coordinates_text(text: str):
    """KML coordinate strings look like 'lon,lat,alt lon,lat,alt ...' with
    arbitrary whitespace/newlines between tuples."""
    coords = []
    for chunk in text.split():
        parts = chunk.split(",")
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            coords.append((lon, lat))
    return coords


def parse_kml(path: str) -> MultiPolygon:
    """Return a shapely (Multi)Polygon in WGS84 lon/lat for every polygon boundary
    found anywhere in the KML file (Placemark, MultiGeometry, etc.)."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise KMLParseError(f"This doesn't look like a valid KML/XML file: {e}")

    root = tree.getroot()
    polygons = []
    for elem in root.iter():
        if _local_tag(elem.tag) != "Polygon":
            continue
        outer_ring = None
        for child in elem.iter():
            if _local_tag(child.tag) == "outerBoundaryIs":
                for coord_elem in child.iter():
                    if _local_tag(coord_elem.tag) == "coordinates" and coord_elem.text:
                        pts = _parse_coordinates_text(coord_elem.text)
                        if len(pts) >= 3:
                            outer_ring = pts
        if outer_ring:
            try:
                polygons.append(Polygon(outer_ring))
            except Exception:
                continue

    if not polygons:
        raise KMLParseError(
            "No polygon boundary found in this KML file. Only Polygon-based "
            "AOI boundaries are supported right now."
        )

    merged = unary_union(polygons)
    if isinstance(merged, Polygon):
        return MultiPolygon([merged])
    return merged


def overlaps_bounds(aoi: MultiPolygon, bounds_lonlat: Optional[tuple]) -> bool:
    """Whether the AOI polygon overlaps the image's geographic bounding box.
    If the image has no geographic bounds at all, we can't check -- caller
    should treat that as its own separate failure case (see raster.py)."""
    if bounds_lonlat is None:
        return False
    from shapely.geometry import box
    minlon, minlat, maxlon, maxlat = bounds_lonlat
    image_box = box(minlon, minlat, maxlon, maxlat)
    return aoi.intersects(image_box)
