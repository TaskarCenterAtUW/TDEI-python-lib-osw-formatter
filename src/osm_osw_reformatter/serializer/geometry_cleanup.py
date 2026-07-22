from copy import deepcopy
from typing import Iterable, Optional

from shapely.geometry import LineString, Polygon, mapping, shape


def _coord_key(coord):
    return tuple(coord[:2])


def coordinates_equal(first, second) -> bool:
    return _coord_key(first) == _coord_key(second)


def remove_consecutive_duplicate_coords(coords: Iterable) -> list:
    cleaned = []
    previous_key = None
    for coord in coords:
        current = list(coord)
        current_key = _coord_key(current)
        if current_key == previous_key:
            continue
        cleaned.append(current)
        previous_key = current_key
    return cleaned


def remove_consecutive_duplicate_ref_coords(ref_coords: Iterable) -> list:
    cleaned = []
    previous_key = None
    for ref, coord in ref_coords:
        current_key = _coord_key(coord)
        if current_key == previous_key:
            continue
        cleaned.append((ref, coord))
        previous_key = current_key
    return cleaned


def distinct_coordinate_count(coords: Iterable) -> int:
    return len({_coord_key(coord) for coord in coords})


def first_coordinate(coordinates):
    if coordinates is None:
        return None
    if not isinstance(coordinates, list) or not coordinates:
        return None
    if isinstance(coordinates[0], (int, float)):
        return coordinates
    for item in coordinates:
        coord = first_coordinate(item)
        if coord is not None:
            return coord
    return None


def collapsed_feature_to_point(feature: dict) -> Optional[dict]:
    coord = first_coordinate(feature.get("geometry", {}).get("coordinates"))
    if coord is None:
        return None

    cleaned = deepcopy(feature)
    cleaned["geometry"] = {
        "type": "Point",
        "coordinates": list(coord),
    }
    return cleaned


def clean_linestring_coords(coords: Iterable) -> Optional[list]:
    cleaned = remove_consecutive_duplicate_coords(coords)
    if len(cleaned) < 2 or distinct_coordinate_count(cleaned) < 2:
        return None

    line = LineString(cleaned)
    if line.is_empty or line.length == 0:
        return None

    return cleaned


def clean_linestring_geometry(coords: Iterable):
    cleaned_coords = clean_linestring_coords(coords)
    if cleaned_coords is None:
        return None
    return LineString(cleaned_coords)


def clean_polygon_ring(coords: Iterable) -> Optional[list]:
    cleaned = remove_consecutive_duplicate_coords(coords)
    if len(cleaned) > 1 and _coord_key(cleaned[0]) == _coord_key(cleaned[-1]):
        closing_coord = cleaned[-1]
        cleaned = cleaned[:-1]
    else:
        closing_coord = None

    if len(cleaned) < 3 or distinct_coordinate_count(cleaned) < 3:
        return None

    ring = cleaned + [closing_coord if closing_coord is not None else cleaned[0]]
    if Polygon(ring).is_empty or Polygon(ring).area == 0:
        return None

    return ring


def clean_polygon_coords(coords: Iterable) -> Optional[list]:
    rings = list(coords)
    if not rings:
        return None

    exterior = clean_polygon_ring(rings[0])
    if exterior is None:
        return None

    interiors = []
    for ring in rings[1:]:
        cleaned_ring = clean_polygon_ring(ring)
        if cleaned_ring is not None:
            interiors.append(cleaned_ring)

    polygon = Polygon(exterior, interiors)
    if polygon.is_empty or polygon.area == 0:
        return None

    return [exterior] + interiors


def clean_polygon_geometry(exterior_coords: Iterable, interior_rings: Iterable = ()):
    cleaned_coords = clean_polygon_coords([exterior_coords] + list(interior_rings))
    if cleaned_coords is None:
        return None
    return Polygon(cleaned_coords[0], cleaned_coords[1:])


def clean_referenced_polygon_geometry(ref_coords: Iterable, interior_rings: Iterable = ()):
    cleaned_ref_coords = remove_consecutive_duplicate_ref_coords(ref_coords)
    coords = [coord for _, coord in cleaned_ref_coords]
    if len(coords) > 1 and coordinates_equal(coords[0], coords[-1]):
        coords_for_validation = coords[:-1]
    else:
        coords_for_validation = coords
    if distinct_coordinate_count(coords_for_validation) < 3:
        return None, []

    geometry = clean_polygon_geometry(coords, interior_rings)
    if geometry is None:
        return None, []

    return geometry, [ref for ref, _ in cleaned_ref_coords]


def clean_feature_geometry(feature: dict, collapsed_to_point: bool = False) -> Optional[dict]:
    cleaned = deepcopy(feature)
    geometry = cleaned.get("geometry")
    if not geometry:
        return cleaned

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "LineString":
        cleaned_coords = clean_linestring_coords(coordinates or [])
        if cleaned_coords is None:
            return collapsed_feature_to_point(feature) if collapsed_to_point else None
        cleaned["geometry"]["coordinates"] = cleaned_coords
        return cleaned

    if geometry_type == "Polygon":
        cleaned_coords = clean_polygon_coords(coordinates or [])
        if cleaned_coords is None:
            return collapsed_feature_to_point(feature) if collapsed_to_point else None
        cleaned["geometry"]["coordinates"] = cleaned_coords
        return cleaned

    if geometry_type == "MultiLineString":
        cleaned_parts = []
        for part in coordinates or []:
            cleaned_part = clean_linestring_coords(part)
            if cleaned_part is not None:
                cleaned_parts.append(cleaned_part)
        if not cleaned_parts:
            return collapsed_feature_to_point(feature) if collapsed_to_point else None
        cleaned["geometry"]["coordinates"] = cleaned_parts
        return cleaned

    if geometry_type == "MultiPolygon":
        cleaned_parts = []
        for part in coordinates or []:
            cleaned_part = clean_polygon_coords(part)
            if cleaned_part is not None:
                cleaned_parts.append(cleaned_part)
        if not cleaned_parts:
            return collapsed_feature_to_point(feature) if collapsed_to_point else None
        cleaned["geometry"]["coordinates"] = cleaned_parts
        return cleaned

    return cleaned


def geometry_is_zero_length_or_area(geometry) -> bool:
    if geometry.is_empty:
        return True
    if geometry.geom_type in {"LineString", "MultiLineString"}:
        return geometry.length == 0
    if geometry.geom_type in {"Polygon", "MultiPolygon"}:
        return geometry.area == 0
    return False


def clean_shapely_geometry(geometry):
    feature = {"type": "Feature", "geometry": mapping(geometry), "properties": {}}
    cleaned = clean_feature_geometry(feature)
    if cleaned is None:
        return None
    cleaned_geometry = shape(cleaned["geometry"])
    if geometry_is_zero_length_or_area(cleaned_geometry):
        return None
    return cleaned_geometry
