import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


COORDINATE_PRECISION_WARNING_TEMPLATE = (
    "Input dataset contains coordinates with more than {coordinate_precision} decimal places."
)
ZERO_LENGTH_GEOMETRY_WARNING = (
    "Input dataset contains duplicate or collapsed coordinate geometry. "
    "The formatter removed duplicate coordinate vertices, omitted geometries "
    "that could not form a valid line or polygon, preserved zero-length "
    "LineStrings only when allow_zero_length_lines=True, or converted collapsed "
    "features to point output when possible."
)


class WarningCollector:
    def __init__(self, coordinate_precision: int):
        self.coordinate_precision = coordinate_precision
        self.has_excess_coordinate_precision = False
        self.has_zero_length_geometry = False

    def add_coordinate_precision(self) -> None:
        self.has_excess_coordinate_precision = True

    def add_zero_length_geometry(self) -> None:
        self.has_zero_length_geometry = True

    def to_string(self) -> str:
        warnings = []
        if self.has_excess_coordinate_precision:
            warnings.append(
                COORDINATE_PRECISION_WARNING_TEMPLATE.format(
                    coordinate_precision=self.coordinate_precision,
                )
            )
        if self.has_zero_length_geometry:
            warnings.append(ZERO_LENGTH_GEOMETRY_WARNING)
        return "\n".join(warnings)


def _coordinate_values_exceed_decimal_places(values: Any, max_decimal_places: int) -> bool:
    if isinstance(values, Decimal):
        return values.is_finite() and max(0, -values.as_tuple().exponent) > max_decimal_places
    if isinstance(values, list):
        return any(
            _coordinate_values_exceed_decimal_places(value, max_decimal_places)
            for value in values
        )
    return False


def _geometry_exceeds_coordinate_precision(geometry: Any, max_decimal_places: int) -> bool:
    if not isinstance(geometry, dict):
        return False
    if _coordinate_values_exceed_decimal_places(
        geometry.get("coordinates"),
        max_decimal_places,
    ):
        return True
    geometries = geometry.get("geometries", [])
    if not isinstance(geometries, list):
        return False
    return any(
        _geometry_exceeds_coordinate_precision(child, max_decimal_places)
        for child in geometries
    )


def geojson_file_has_excess_coordinate_precision(
    file_path: str,
    max_decimal_places: int = 7,
) -> bool:
    """Return whether serialized GeoJSON coordinates exceed the decimal-place limit."""
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file, parse_float=Decimal)

    if not isinstance(data, dict):
        return False
    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not isinstance(features, list):
            return False
        return any(
            isinstance(feature, dict)
            and _geometry_exceeds_coordinate_precision(
                feature.get("geometry"),
                max_decimal_places,
            )
            for feature in features
        )
    if data.get("type") == "Feature":
        return _geometry_exceeds_coordinate_precision(
            data.get("geometry"),
            max_decimal_places,
        )
    return _geometry_exceeds_coordinate_precision(data, max_decimal_places)


def osm_xml_file_has_excess_coordinate_precision(
    file_path: str,
    max_decimal_places: int = 7,
) -> bool:
    for _event, element in ET.iterparse(file_path, events=("end",)):
        if element.tag != "node":
            element.clear()
            continue
        for attr in ("lat", "lon"):
            value = element.get(attr)
            if value is None:
                continue
            try:
                coordinate = Decimal(value)
            except InvalidOperation:
                continue
            if _coordinate_values_exceed_decimal_places(coordinate, max_decimal_places):
                return True
        element.clear()
    return False


def input_file_has_excess_coordinate_precision(
    file_path: str,
    max_decimal_places: int = 7,
) -> bool:
    path = Path(file_path)
    suffixes = {suffix.lower() for suffix in path.suffixes}
    try:
        if ".geojson" in suffixes or path.suffix.lower() == ".json":
            return geojson_file_has_excess_coordinate_precision(
                str(path),
                max_decimal_places,
            )
        if path.suffix.lower() in {".xml", ".osm"}:
            return osm_xml_file_has_excess_coordinate_precision(
                str(path),
                max_decimal_places,
            )
    except (OSError, json.JSONDecodeError, ET.ParseError, TypeError, ValueError):
        return False
    return False
