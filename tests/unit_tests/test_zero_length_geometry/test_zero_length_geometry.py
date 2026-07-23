import asyncio
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from src.osm_osw_reformatter.config import FormatterConfig
from src.osm_osw_reformatter.helpers.osw import OSWHelper
from src.osm_osw_reformatter.helpers.output_validation import (
    EMPTY_OSM_XML_ERROR,
    NO_GENERATED_FILES_ERROR,
)
from src.osm_osw_reformatter.helpers.warnings import WarningCollector
from src.osm_osw_reformatter.osm2osw.osm2osw import OSM2OSW
from src.osm_osw_reformatter.osw2osm.osw2osm import OSW2OSM
from src.osm_osw_reformatter.serializer.osm.osm_graph import OSMGraph, OSMWayParser


FIXTURE_DIR = Path(__file__).parents[1] / "test_files" / "zero_length_geometry"
OSM_FIXTURE_DIR = FIXTURE_DIR / "osm"
OSW_FIXTURE_DIR = FIXTURE_DIR / "osw"


def _osm_fixture(filename):
    return str(OSM_FIXTURE_DIR / filename)


def _merge_osw_zip_dataset(zip_filename, output_dir, config=None, warnings=None):
    unzipped_files = OSWHelper.unzip(str(OSW_FIXTURE_DIR / zip_filename), output_dir)
    return OSWHelper.merge(unzipped_files, output_dir, "cleaned", config=config, warnings=warnings)


def _parse_osm_edges(filename, config=None, warnings=None):
    parser = OSMWayParser(OSWHelper.osw_way_filter, config=config, warnings=warnings)
    parser.apply_file(_osm_fixture(filename), locations=True)
    return parser.G


def _graph_from_osm(filename, config=None, warnings=None):
    osm_graph = OSMGraph.from_osm_file(
        _osm_fixture(filename),
        OSWHelper.osw_way_filter,
        OSWHelper.osw_node_filter,
        OSWHelper.osw_point_filter,
        OSWHelper.osw_line_filter,
        OSWHelper.osw_zone_filter,
        OSWHelper.osw_polygon_filter,
        config=config,
        warnings=warnings,
    )
    osm_graph.construct_geometries(config=config, warnings=warnings)
    return osm_graph


def _write_zip_dataset(output_dir, dataset_name, feature_collection):
    geojson_path = Path(output_dir) / f"{dataset_name}.geojson"
    with open(geojson_path, "w") as f:
        json.dump(feature_collection, f)
    zip_path = Path(output_dir) / f"{dataset_name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_file:
        zip_file.write(geojson_path, arcname=f"{dataset_name}.geojson")
    geojson_path.unlink()
    return zip_path


class TestZeroLengthGeometryCleanup(unittest.TestCase):
    def test_osm2osw_duplicate_node_refs_are_skipped(self):
        graph = _parse_osm_edges("duplicate_node_refs_sidewalk.xml")

        self.assertEqual(len(graph.edges), 0)

    def test_osm2osw_different_node_refs_with_identical_coordinates_are_skipped(self):
        graph = _parse_osm_edges("identical_coordinate_crossing.xml")

        self.assertEqual(len(graph.edges), 0)

    def test_osm2osw_different_node_refs_with_identical_coordinates_warns(self):
        warnings = WarningCollector(coordinate_precision=7)

        _parse_osm_edges("identical_coordinate_crossing.xml", warnings=warnings)

        self.assertIn("duplicate or collapsed coordinate geometry", warnings.to_string())

    def test_osm2osw_allow_zero_length_lines_preserves_zero_length_edge(self):
        config = FormatterConfig(allow_zero_length_lines=True)
        warnings = WarningCollector(coordinate_precision=7)

        graph = _parse_osm_edges(
            "identical_coordinate_crossing.xml",
            config=config,
            warnings=warnings,
        )

        self.assertEqual(len(graph.edges), 1)
        self.assertIn("duplicate or collapsed coordinate geometry", warnings.to_string())

    def test_osm2osw_valid_distinct_edge_is_preserved(self):
        graph = _parse_osm_edges("valid_sidewalk_edge.xml")

        self.assertEqual(len(graph.edges), 1)

    def test_osm2osw_collapsed_line_is_skipped(self):
        osm_graph = _graph_from_osm("collapsed_fence_line.xml")

        self.assertNotIn("l700001", osm_graph.get_graph().nodes)

    def test_osm2osw_line_duplicate_consecutive_coordinates_are_cleaned(self):
        osm_graph = _graph_from_osm("tree_row_duplicate_coordinate_line.xml")

        coords = list(osm_graph.get_graph().nodes["l700002"]["geometry"].coords)
        self.assertEqual(coords, [(-122.34028, 47.67851), (-122.3401, 47.67872)])

    def test_osm2osw_zero_length_edge_preserves_tagged_node(self):
        osm_graph = _graph_from_osm("zero_length_edge_orphan_nodes.xml")

        self.assertEqual(len(osm_graph.get_graph().edges), 0)
        self.assertEqual(len(osm_graph.get_graph().nodes), 1)
        node_data = next(iter(osm_graph.get_graph().nodes(data=True)))[1]
        self.assertEqual(node_data.get("ext:highway"), "footway")
        self.assertEqual(node_data.get("ext:footway"), "sidewalk")
        self.assertEqual(node_data.get("ext:surface"), "concrete")

    def test_osm2osw_zero_length_edge_writes_valid_custom_point_geojson(self):
        osm_graph = _graph_from_osm("zero_length_edge_orphan_nodes.xml")
        with tempfile.TemporaryDirectory() as tmpdir:
            nodes_path = Path(tmpdir) / "nodes.geojson"
            edges_path = Path(tmpdir) / "edges.geojson"
            points_path = Path(tmpdir) / "points.geojson"
            lines_path = Path(tmpdir) / "lines.geojson"
            zones_path = Path(tmpdir) / "zones.geojson"
            polygons_path = Path(tmpdir) / "polygons.geojson"

            osm_graph.to_geojson(
                nodes_path,
                edges_path,
                points_path,
                lines_path,
                zones_path,
                polygons_path,
            )

            self.assertFalse(nodes_path.exists())
            with open(points_path) as f:
                points = json.load(f)

        self.assertEqual(len(points["features"]), 1)
        self.assertEqual(points["features"][0]["geometry"]["type"], "Point")
        self.assertNotIn("highway", points["features"][0]["properties"])
        self.assertNotIn("footway", points["features"][0]["properties"])
        self.assertNotIn("surface", points["features"][0]["properties"])
        self.assertEqual(points["features"][0]["properties"].get("ext:highway"), "footway")
        self.assertEqual(points["features"][0]["properties"].get("ext:footway"), "sidewalk")

    def test_osm2osw_collapsed_polygon_is_skipped(self):
        osm_graph = _graph_from_osm("collapsed_building_polygon.xml")

        polygon_nodes = [
            data for _, data in osm_graph.get_graph().nodes(data=True)
            if data.get("building") == "yes"
        ]
        self.assertEqual(polygon_nodes, [])

    def test_osm2osw_collapsed_zone_is_skipped(self):
        osm_graph = _graph_from_osm("collapsed_pedestrian_zone.xml")

        zone_nodes = [
            data for _, data in osm_graph.get_graph().nodes(data=True)
            if data.get("highway") == "pedestrian"
        ]
        self.assertEqual(zone_nodes, [])

    def test_osm2osw_allow_zero_length_lines_does_not_apply_to_zones(self):
        config = FormatterConfig(allow_zero_length_lines=True)

        osm_graph = _graph_from_osm("collapsed_pedestrian_zone.xml", config=config)

        zone_nodes = [
            data for _, data in osm_graph.get_graph().nodes(data=True)
            if data.get("highway") == "pedestrian"
        ]
        self.assertEqual(zone_nodes, [])

    def test_osw2osm_edge_duplicate_consecutive_coordinates_are_cleaned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("edge_duplicate_coordinates.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [[-122.33581, 47.60972], [-122.33542, 47.60994]],
        )

    def test_osw2osm_zero_length_edge_is_converted_to_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("edge_zero_length.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.33702, 47.61018],
        )

    def test_osw2osm_zero_length_line_is_converted_to_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("line_zero_length.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.34562, 47.66105],
        )

    def test_osw2osm_allow_zero_length_lines_preserves_zero_length_line(self):
        config = FormatterConfig(allow_zero_length_lines=True)
        warnings = WarningCollector(coordinate_precision=7)
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset(
                "line_zero_length.zip",
                tmpdir,
                config=config,
                warnings=warnings,
            )

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "LineString")
        self.assertIn("duplicate or collapsed coordinate geometry", warnings.to_string())

    def test_osw2osm_zero_area_polygon_is_converted_to_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("polygon_zero_area.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.32070, 47.61201],
        )

    def test_osw2osm_zero_area_zone_is_converted_to_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("zone_zero_area.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.33612, 47.60892],
        )

    def test_osw2osm_allow_zero_length_lines_does_not_apply_to_zones(self):
        config = FormatterConfig(allow_zero_length_lines=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset(
                "zone_zero_area.zip",
                tmpdir,
                config=config,
            )

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")

    def test_osw2osm_point_features_are_not_affected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("point_valid.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")

    def test_osw2osm_zero_length_line_zip_generates_osm_node_with_tags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_zip = OSW_FIXTURE_DIR / "line_zero_length.zip"
            zip_path = Path(tmpdir) / "line_zero_length.zip"
            with open(source_zip, "rb") as source, open(zip_path, "wb") as target:
                target.write(source.read())

            result = OSW2OSM(zip_file_path=str(zip_path), workdir=tmpdir, prefix="line").convert()

            self.assertTrue(result.status, msg=getattr(result, "error", "Conversion failed"))
            root = ET.parse(result.generated_files).getroot()
            nodes = root.findall(".//node")
            ways = root.findall(".//way")

        self.assertEqual(len(nodes), 1)
        self.assertEqual(len(ways), 0)
        tags = {tag.get("k"): tag.get("v") for tag in nodes[0].findall("tag")}
        self.assertEqual(tags.get("barrier"), "fence")
        self.assertEqual(tags.get("name"), "Aurora Avenue construction fence")

    def test_osm2osw_no_generated_files_returns_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = asyncio.run(
                OSM2OSW(
                    prefix="empty",
                    osm_file=_osm_fixture("collapsed_fence_line.xml"),
                    workdir=tmpdir,
                ).convert()
            )

        self.assertFalse(result.status)
        self.assertEqual(result.generated_files, [])
        self.assertEqual(result.error, NO_GENERATED_FILES_ERROR)
        self.assertIn("duplicate or collapsed coordinate geometry", result.warnings)

    def test_osw2osm_empty_osm_xml_returns_error(self):
        fc = {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json",
            "type": "FeatureCollection",
            "features": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = _write_zip_dataset(tmpdir, "points", fc)

            result = OSW2OSM(
                zip_file_path=str(zip_path),
                workdir=tmpdir,
                prefix="empty",
            ).convert()

        self.assertFalse(result.status)
        self.assertEqual(result.generated_files, None)
        self.assertEqual(result.error, EMPTY_OSM_XML_ERROR)

    def test_osm2osw_high_precision_coordinates_return_warning(self):
        osm = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="precision-fixture">
  <node id="1001" lat="47.61018012" lon="-122.33702012" version="1"/>
  <node id="1002" lat="47.61019012" lon="-122.33703012" version="1"/>
  <way id="900001" version="1">
    <nd ref="1001"/>
    <nd ref="1002"/>
    <tag k="highway" v="footway"/>
    <tag k="footway" v="sidewalk"/>
  </way>
</osm>
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            osm_path = Path(tmpdir) / "precision.osm"
            with open(osm_path, "w") as f:
                f.write(osm)

            result = asyncio.run(
                OSM2OSW(prefix="precision", osm_file=str(osm_path), workdir=tmpdir).convert()
            )

        self.assertTrue(result.status, msg=result.error)
        self.assertIn("more than 7 decimal places", result.warnings)

    def test_osw2osm_high_precision_coordinates_return_warning(self):
        fc = {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json",
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.33702012, 47.61018012],
                    },
                    "properties": {
                        "_id": "p-precision",
                        "barrier": "bollard",
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = _write_zip_dataset(tmpdir, "points", fc)

            result = OSW2OSM(
                zip_file_path=str(zip_path),
                workdir=tmpdir,
                prefix="precision",
            ).convert()

        self.assertTrue(result.status, msg=result.error)
        self.assertIn("more than 7 decimal places", result.warnings)

    def test_coordinate_precision_is_configurable(self):
        fc = {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json",
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.33702012, 47.61018012],
                    },
                    "properties": {
                        "_id": "p-precision",
                        "barrier": "bollard",
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = _write_zip_dataset(tmpdir, "points", fc)

            result = OSW2OSM(
                zip_file_path=str(zip_path),
                workdir=tmpdir,
                prefix="precision",
                config=FormatterConfig(coordinate_precision=8),
            ).convert()

        self.assertTrue(result.status, msg=result.error)
        self.assertEqual(result.warnings, "")


if __name__ == "__main__":
    unittest.main()
