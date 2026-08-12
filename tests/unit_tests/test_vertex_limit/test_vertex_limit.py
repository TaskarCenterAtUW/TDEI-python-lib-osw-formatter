import asyncio
import json
import math
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from src.osm_osw_reformatter.config import DEFAULT_MAX_GEOMETRY_VERTICES, FormatterConfig
from src.osm_osw_reformatter.helpers.input_validation import (
    InputValidationError,
    validate_osw_input,
    validation_config,
)
from src.osm_osw_reformatter.osm2osw.osm2osw import OSM2OSW
from src.osm_osw_reformatter.osw2osm.osw2osm import OSW2OSM


FIXTURE_DIR = Path(__file__).parents[1] / "test_files" / "input_validation"
AT_LIMIT_ZIP = FIXTURE_DIR / "max_vertices_ok.zip"
OVER_LIMIT_ZIP = FIXTURE_DIR / "max_vertices_exceeded.zip"
AT_LIMIT_OSM = FIXTURE_DIR / "max_vertices_way_ok.xml"
OVER_LIMIT_OSM = FIXTURE_DIR / "max_vertices_way_exceeded.xml"

SCHEMA = "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json"
LON, LAT = -122.3105000, 47.6555000
PRECISION = 7


def _line(vertex_count):
    """A run of `vertex_count` distinct vertices, all within the precision limit."""
    return [[round(LON + i * 1e-5, PRECISION), LAT] for i in range(vertex_count)]


def _ring(vertex_count, radius):
    """A closed ring holding `vertex_count` unique vertices plus the repeated closer."""
    points = [
        [
            round(LON + radius * math.cos(2 * math.pi * i / vertex_count), PRECISION),
            round(LAT + radius * math.sin(2 * math.pi * i / vertex_count), PRECISION),
        ]
        for i in range(vertex_count)
    ]
    return points + [points[0]]


def _write_dataset(directory, name, features):
    path = Path(directory) / f"{name}.geojson"
    with open(path, "w") as f:
        json.dump({"$schema": SCHEMA, "type": "FeatureCollection", "features": features}, f)
    return path


def _zip_datasets(directory, datasets):
    zip_path = Path(directory) / "dataset.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name, features in datasets.items():
            path = _write_dataset(directory, name, features)
            archive.write(path, arcname=f"{name}.geojson")
            path.unlink()
    return zip_path


def _linestring_feature(feature_id, vertex_count, properties):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": _line(vertex_count)},
        "properties": {"_id": feature_id, **properties},
    }


def _polygon_feature(feature_id, rings, properties):
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": rings},
        "properties": {"_id": feature_id, **properties},
    }


def _validate(datasets, config=None):
    from python_osw_validation import OSWValidation

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = _zip_datasets(tmpdir, datasets)
        return OSWValidation(
            zipfile_path=str(zip_path),
            config=validation_config(config),
        ).validate()


def _edges(vertex_count):
    return {"edges": [_linestring_feature(
        "e1", vertex_count,
        {"_u_id": "n0", "_v_id": "n1", "highway": "footway", "footway": "sidewalk"},
    )]}


class TestVertexLimitBoundary(unittest.TestCase):
    def test_edge_below_the_limit_passes(self):
        self.assertTrue(_validate(_edges(1999)).is_valid)

    def test_edge_exactly_at_the_limit_passes(self):
        self.assertTrue(_validate(_edges(DEFAULT_MAX_GEOMETRY_VERTICES)).is_valid)

    def test_edge_one_over_the_limit_fails(self):
        result = _validate(_edges(DEFAULT_MAX_GEOMETRY_VERTICES + 1))

        self.assertFalse(result.is_valid)
        self.assertIn("contains 2001 geometry vertices", result.errors[0])
        self.assertIn("Maximum allowed is 2000", result.errors[0])

    def test_line_over_the_limit_fails(self):
        datasets = {"lines": [_linestring_feature("l1", 2001, {"barrier": "fence"})]}

        self.assertFalse(_validate(datasets).is_valid)

    def test_polygon_at_the_limit_passes(self):
        datasets = {"polygons": [
            _polygon_feature("g1", [_ring(2000, 0.002)], {"building": "yes"})
        ]}

        self.assertTrue(_validate(datasets).is_valid)

    def test_polygon_over_the_limit_fails(self):
        datasets = {"polygons": [
            _polygon_feature("g1", [_ring(2001, 0.002)], {"building": "yes"})
        ]}

        self.assertFalse(_validate(datasets).is_valid)

    def test_polygon_closing_coordinate_is_not_counted(self):
        """A 2000-vertex ring serializes 2001 coordinates; the closer must not count."""
        rings = [_ring(2000, 0.002)]
        self.assertEqual(len(rings[0]), 2001)

        self.assertTrue(_validate({"polygons": [
            _polygon_feature("g1", rings, {"building": "yes"})
        ]}).is_valid)

    def test_polygon_interior_rings_count_towards_the_limit(self):
        """Neither ring exceeds the limit alone, but together they do."""
        rings = [_ring(1500, 0.002), _ring(501, 0.0005)]

        result = _validate({"polygons": [
            _polygon_feature("g1", rings, {"building": "yes"})
        ]})

        self.assertFalse(result.is_valid)
        self.assertIn("contains 2001 geometry vertices", result.errors[0])

    def test_point_datasets_are_not_affected(self):
        points = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coordinate},
                "properties": {"_id": f"p{index}", "amenity": "bench"},
            }
            for index, coordinate in enumerate(_line(2500))
        ]

        self.assertTrue(_validate({"points": points}).is_valid)


class TestVertexLimitReporting(unittest.TestCase):
    def test_violation_appears_in_errors_and_issues(self):
        result = _validate(_edges(2001))

        self.assertFalse(result.is_valid)
        self.assertTrue(result.errors)
        self.assertTrue(result.issues)

        issue = result.issues[0]
        self.assertEqual(issue["filename"], "edges.geojson")
        self.assertEqual(issue["feature_index"], 0)
        message = " ".join(
            issue["error_message"] if isinstance(issue["error_message"], list)
            else [issue["error_message"]]
        )
        self.assertIn("'e1'", message)          # feature id
        self.assertIn("2001", message)          # actual count
        self.assertIn("2000", message)          # the limit

    def test_max_errors_is_respected(self):
        datasets = {"edges": [
            _linestring_feature(
                f"e{index}", 2001,
                {"_u_id": "n0", "_v_id": "n1", "highway": "footway", "footway": "sidewalk"},
            )
            for index in range(5)
        ]}

        with tempfile.TemporaryDirectory() as tmpdir:
            from python_osw_validation import OSWValidation

            zip_path = _zip_datasets(tmpdir, datasets)
            result = OSWValidation(
                zipfile_path=str(zip_path),
                config=validation_config(),
            ).validate(max_errors=2)

        self.assertFalse(result.is_valid)
        self.assertLessEqual(len(result.errors), 2)


class TestVertexLimitIsConfigurable(unittest.TestCase):
    def test_default_is_two_thousand(self):
        self.assertEqual(DEFAULT_MAX_GEOMETRY_VERTICES, 2000)
        self.assertEqual(FormatterConfig().max_geometry_vertices, 2000)

    def test_config_reaches_the_validator(self):
        self.assertEqual(
            validation_config(FormatterConfig(max_geometry_vertices=50)).max_geometry_vertices,
            50,
        )

    def test_a_lower_limit_rejects_a_smaller_feature(self):
        datasets = _edges(100)

        self.assertTrue(_validate(datasets).is_valid)
        self.assertFalse(
            _validate(datasets, FormatterConfig(max_geometry_vertices=99)).is_valid
        )

    def test_a_higher_limit_accepts_an_over_default_feature(self):
        datasets = _edges(2001)

        self.assertFalse(_validate(datasets).is_valid)
        self.assertTrue(
            _validate(datasets, FormatterConfig(max_geometry_vertices=3000)).is_valid
        )

    def test_limit_must_be_a_positive_integer(self):
        for value in (0, -1):
            with self.assertRaises(ValueError):
                FormatterConfig(max_geometry_vertices=value)
        for value in ("2000", True, 1.5):
            with self.assertRaises(TypeError):
                FormatterConfig(max_geometry_vertices=value)


class TestVertexLimitOSWToOSM(unittest.TestCase):
    """Input is held to the limit; the OSM way cap is handled by splitting."""

    @staticmethod
    def _way_node_counts(osm_path):
        root = ET.parse(osm_path).getroot()
        return [len(way.findall("nd")) for way in root.findall(".//way")]

    def _convert(self, zip_path, config=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(zip_path),
                workdir=tmpdir,
                prefix="vertices",
                config=config,
            ).convert()
            self.assertTrue(result.status, msg=result.error)
            return self._way_node_counts(result.generated_files)

    def test_input_at_the_limit_is_accepted(self):
        validate_osw_input(str(AT_LIMIT_ZIP))

        counts = self._convert(AT_LIMIT_ZIP)
        self.assertTrue(counts)
        self.assertLessEqual(max(counts), DEFAULT_MAX_GEOMETRY_VERTICES)

    def test_input_over_the_limit_is_rejected(self):
        with self.assertRaises(InputValidationError) as ctx:
            validate_osw_input(str(OVER_LIMIT_ZIP))

        self.assertIn("contains 2001 geometry vertices", str(ctx.exception))

    def test_input_over_the_limit_stops_conversion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(OVER_LIMIT_ZIP),
                workdir=tmpdir,
                prefix="vertices",
            ).convert()

        self.assertFalse(result.status)
        self.assertIn("Maximum allowed is 2000", result.error)

    def test_closed_ring_at_the_limit_is_still_split(self):
        """A ring of 2000 unique vertices needs 2001 node refs, so it must split.

        The validator counts unique vertices and excludes the closing coordinate,
        while an OSM way counts every node reference. A dataset can therefore be
        valid and still hold a ring that cannot be one way.
        """
        counts = self._convert(AT_LIMIT_ZIP)

        self.assertLessEqual(max(counts), DEFAULT_MAX_GEOMETRY_VERTICES)
        # The zone ring is the one that had to be broken up.
        self.assertGreater(len(counts), 4)

    def test_split_pieces_stay_joined(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(AT_LIMIT_ZIP),
                workdir=tmpdir,
                prefix="joined",
            ).convert()
            self.assertTrue(result.status, msg=result.error)
            root = ET.parse(result.generated_files).getroot()
            ways = [[nd.get("ref") for nd in way.findall("nd")] for way in root.findall(".//way")]

        starts = {refs[0] for refs in ways}
        ends = {refs[-1] for refs in ways}
        self.assertTrue(starts & ends, "Split pieces are not joined to each other")

    def test_split_limit_is_configurable(self):
        """A lower limit splits more aggressively.

        It also makes input validation stricter, so this dataset -- valid at the
        default -- has to skip validation to reach the conversion under test.
        """
        counts = self._convert(
            AT_LIMIT_ZIP,
            FormatterConfig(max_geometry_vertices=500, validate_input=False),
        )

        self.assertLessEqual(max(counts), 500)
        self.assertGreater(len(counts), 4)

    def test_lowering_the_limit_also_tightens_input_validation(self):
        validate_osw_input(str(AT_LIMIT_ZIP))          # fine at the default

        with self.assertRaises(InputValidationError):
            validate_osw_input(str(AT_LIMIT_ZIP), FormatterConfig(max_geometry_vertices=500))


class TestVertexLimitOSMToOSW(unittest.TestCase):
    """Generated OSW is held to the limit, so an over-long OSM way is rejected."""

    def _convert(self, osm_path, config=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            return asyncio.run(
                OSM2OSW(
                    prefix="vertices",
                    osm_file=str(osm_path),
                    workdir=tmpdir,
                    config=config,
                ).convert()
            )

    def test_way_at_the_limit_converts(self):
        result = self._convert(AT_LIMIT_OSM)

        self.assertTrue(result.status, msg=result.error)

    def test_way_over_the_limit_is_rejected(self):
        result = self._convert(OVER_LIMIT_OSM)

        self.assertFalse(result.status)
        self.assertIn("contains 2001 geometry vertices", result.error)
        self.assertIn("Maximum allowed is 2000", result.error)

    def test_a_higher_limit_accepts_the_same_file(self):
        result = self._convert(OVER_LIMIT_OSM, FormatterConfig(max_geometry_vertices=3000))

        self.assertTrue(result.status, msg=result.error)


if __name__ == "__main__":
    unittest.main()
