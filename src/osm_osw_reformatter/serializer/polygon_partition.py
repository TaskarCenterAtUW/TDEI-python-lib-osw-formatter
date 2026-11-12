"""Partition custom OSW polygons without simplifying their boundaries."""

from math import isclose

from shapely import intersection, set_precision, union_all
from shapely.geometry import Polygon, box


def polygon_vertex_count(polygon: Polygon) -> int:
    """Match OSW validation: count all rings, excluding closure coordinates."""
    return len(polygon.exterior.coords) - 1 + sum(
        len(ring.coords) - 1 for ring in polygon.interiors
    )


def _polygon_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        return [part for child in geometry.geoms for part in _polygon_parts(child)]
    # A clipping boundary can also return points or lines; neither has area.
    return []


def _rounded_polygon(polygon, precision):
    # GEOS grid arithmetic can serialize as e.g. 1.2000000000000002. Round the
    # floats explicitly so generated GeoJSON meets decimal-place validation.
    def ring_coords(ring):
        return [tuple(round(value, precision) for value in coord) for coord in ring.coords]

    return Polygon(
        ring_coords(polygon.exterior),
        [ring_coords(r) for r in polygon.interiors],
    )


def partition_polygon(polygon: Polygon, max_vertices: int, coordinate_precision: int):
    """Return valid polygons within the configured vertex budget.

    Split along coordinate-grid-aligned cuts, retaining holes through geometric
    intersection. Fixed-precision overlay makes adjoining cut boundaries agree;
    new intersections are snapped to the configured coordinate precision. Input
    polygons within budget are returned unchanged. Invalid oversized geometry or
    a budget that cannot be achieved on this grid raises rather than losing area
    silently or looping indefinitely.
    """
    if polygon_vertex_count(polygon) <= max_vertices:
        return [polygon]
    if not polygon.is_valid or polygon.is_empty:
        raise ValueError("Cannot partition an invalid or empty polygon.")
    if max_vertices < 4:
        raise ValueError("Partitioning oversized polygons requires max_geometry_vertices >= 4.")

    grid_size = 10.0 ** -coordinate_precision
    snapped = set_precision(polygon, grid_size)
    if (
        snapped.geom_type != "Polygon"
        or snapped.is_empty
        or len(snapped.interiors) != len(polygon.interiors)
    ):
        raise ValueError("Polygon topology cannot be preserved at the configured coordinate precision.")

    pending = [(snapped, 0)]
    result = []
    while pending:
        current, depth = pending.pop()
        count = polygon_vertex_count(current)
        if count <= max_vertices:
            rounded = _rounded_polygon(current, coordinate_precision)
            if not rounded.is_valid or rounded.is_empty:
                raise ValueError("Partition produced invalid geometry at the configured coordinate precision.")
            result.append(rounded)
            continue
        if depth >= 64:
            raise ValueError("Polygon partitioning exceeded the safe subdivision depth.")

        minx, miny, maxx, maxy = current.bounds
        rings = [current.exterior, *current.interiors]
        # Prefer the longer axis. A median-vertex cut also handles polygons whose
        # detail is concentrated near one corner better than repeated midpoints.
        axes = sorted(
            (0, 1), key=lambda axis: (maxx - minx, maxy - miny)[axis], reverse=True,
        )
        children = None
        for axis in axes:
            low, high = (minx, maxx) if axis == 0 else (miny, maxy)
            values = sorted(coord[axis] for ring in rings for coord in list(ring.coords)[:-1])
            candidates = [values[len(values) // 2], (low + high) / 2]
            for value in dict.fromkeys(round(v, coordinate_precision) for v in candidates):
                if not low < value < high:
                    continue
                if axis == 0:
                    cutters = [box(minx, miny, value, maxy), box(value, miny, maxx, maxy)]
                else:
                    cutters = [box(minx, miny, maxx, value), box(minx, value, maxx, maxy)]
                parts = [
                    part for cutter in cutters
                    for part in _polygon_parts(intersection(current, cutter, grid_size=grid_size))
                ]
                # A cut across a hole may leave a notch with the same number of
                # vertices. Permit that only when every child gets smaller;
                # the depth bound also protects pathological narrow geometries.
                if len(parts) > 1 and all(
                    polygon_vertex_count(part) <= count and part.area < current.area * 0.99
                    for part in parts
                ):
                    children = parts
                    break
            if children is not None:
                break
        if children is None:
            raise ValueError(
                "Cannot partition polygon within max_geometry_vertices at the configured coordinate precision."
            )
        pending.extend((child, depth + 1) for child in reversed(children))

    # New grid-rounded intersections can introduce small kinks in a sloping
    # source edge. Bound that displacement to one coordinate-grid unit rather
    # than claiming exact equality, and verify that interiors do not overlap.
    combined = union_all(result)
    # Check in floating precision: buffering a fixed-precision geometry would
    # snap the tolerance buffer itself back to the grid.
    reference = set_precision(snapped, 0)
    if (
        not reference.buffer(grid_size).covers(combined)
        or not combined.buffer(grid_size).covers(reference)
        or reference.symmetric_difference(combined).area > reference.length * grid_size
    ):
        raise ValueError("Polygon partitioning changed coverage at the configured coordinate precision.")
    if not isclose(sum(part.area for part in result), combined.area, rel_tol=1e-12, abs_tol=grid_size ** 2):
        raise ValueError("Polygon partitioning produced overlapping pieces.")
    return result
