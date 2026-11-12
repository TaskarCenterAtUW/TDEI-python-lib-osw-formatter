import asyncio
import json
import math
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import networkx as nx
from shapely.geometry import Point, Polygon, box, shape
from shapely.ops import unary_union

from src.osm_osw_reformatter.config import FormatterConfig
from src.osm_osw_reformatter.osm2osw.osm2osw import OSM2OSW
from src.osm_osw_reformatter.serializer.osm.osm_graph import OSMGraph
from src.osm_osw_reformatter.serializer.polygon_partition import (
    partition_polygon,
    polygon_vertex_count,
)

FIXTURE_DIR = Path(__file__).parents[1] / 'test_files' / 'bug_4658'


def circle_ring(count, radius=1, center=(0, 0)):
    return [
        (round(center[0] + radius * math.cos(i * 2 * math.pi / count), 7),
         round(center[1] + radius * math.sin(i * 2 * math.pi / count), 7))
        for i in range(count)
    ]


class TestPolygonPartition(unittest.TestCase):
    def assert_partition(self, original, limit, precision=7):
        parts = partition_polygon(original, limit, precision)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(p.is_valid and p.area > 0 for p in parts))
        self.assertTrue(all(polygon_vertex_count(p) <= limit for p in parts))
        combined = unary_union(parts)
        # Rounding newly intersected edges can move them by one coordinate-grid
        # unit. The entire union must still match the input to that precision.
        tolerance = original.length * 10 ** -precision * 2
        self.assertLessEqual(original.symmetric_difference(combined).area, tolerance)
        self.assertAlmostEqual(sum(p.area for p in parts), combined.area, places=10)
        return parts, combined

    def test_at_limit_is_unchanged_and_closing_points_are_excluded(self):
        polygon = box(0, 0, 1, 1)
        self.assertEqual(polygon_vertex_count(polygon), 4)
        self.assertIs(partition_polygon(polygon, 4, 7)[0], polygon)

    def test_large_ring_and_ticket_sized_ring(self):
        for count in (2001, 41842):
            with self.subTest(count=count):
                self.assert_partition(Polygon(circle_ring(count)), 2000)

    def test_holes_count_towards_limit_and_stay_excluded(self):
        outer = circle_ring(120)
        hole = circle_ring(120, radius=0.3)
        polygon = Polygon(outer, [hole])
        parts, combined = self.assert_partition(polygon, 128)
        self.assertFalse(combined.covers(Point(0, 0)))
        self.assertLess(combined.intersection(Polygon(hole)).area, 1e-7)

    def test_many_holes_and_holes_crossing_cuts(self):
        holes = [list(box(x, y, x + 1, y + 1).exterior.coords)
                 for x in range(1, 19, 2) for y in range(1, 19, 2)]
        polygon = Polygon(box(0, 0, 20, 20).exterior.coords, holes)
        _, combined = self.assert_partition(polygon, 32)
        self.assertTrue(combined.equals(polygon))

    def test_concave_polygon_can_yield_disconnected_pieces(self):
        # A comb: a horizontal cut can produce several disconnected teeth.
        polygon = unary_union([box(0, 0, 20, 1)] + [box(x, 0, x + 1, 8) for x in range(0, 20, 2)])
        _, combined = self.assert_partition(polygon, 12)
        self.assertTrue(combined.equals(polygon))

    def test_new_intersections_respect_coordinate_precision(self):
        polygon = Polygon([(0, 0), (0.03, 1), (0.07, 0.9), (0.1, 0)])
        polygon = Polygon(list(polygon.exterior.coords)[:-1], [
            [(0.04, 0.3), (0.06, 0.3), (0.06, 0.4), (0.04, 0.4)]
        ])
        parts, _ = self.assert_partition(polygon, 6, precision=2)
        for part in parts:
            coordinates = json.loads(json.dumps(part.__geo_interface__["coordinates"]), parse_float=Decimal)
            for ring in coordinates:
                for coord in ring:
                    for value in coord:
                        self.assertLessEqual(max(0, -value.as_tuple().exponent), 2)

    def test_invalid_oversized_polygon_is_not_silently_repaired(self):
        polygon = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (1, 3)])
        with self.assertRaisesRegex(ValueError, 'invalid'):
            partition_polygon(polygon, 4, 7)

    def test_unachievable_precision_or_budget_fails_clearly(self):
        polygon = Polygon(circle_ring(20, radius=0.01))
        with self.assertRaisesRegex(ValueError, 'precision'):
            partition_polygon(polygon, 8, 0)
        with self.assertRaisesRegex(ValueError, '>= 4'):
            partition_polygon(polygon, 3, 7)

    def test_export_preserves_properties_source_ids_and_graph(self):
        polygon = Polygon(circle_ring(240))
        graph = nx.MultiDiGraph()
        graph.add_node('g123', geometry=polygon, osm_id=123, **{'ext:building': 'yes'})
        graph.add_node('g456', geometry=box(3, 3, 4, 4), osm_id=456, **{'ext:building': 'yes'})
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = [Path(tmpdir, f'{name}.geojson') for name in ('nodes', 'edges', 'points', 'lines', 'zones', 'polygons')]
            OSMGraph(graph).to_geojson(*paths, config=FormatterConfig(max_geometry_vertices=64))
            features = json.loads(paths[-1].read_text())['features']
        self.assertEqual([f['properties']['_id'] for f in features], [str(i + 1) for i in range(len(features))])
        pieces = [shape(f['geometry']) for f in features if f['properties']['ext:osm_id'] == '123']
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all(f['properties']['ext:building'] == 'yes' for f in features))
        self.assertTrue(all(polygon_vertex_count(shape(f['geometry'])) <= 64 for f in features))
        self.assertIs(graph.nodes['g123']['geometry'], polygon)
        self.assertEqual(graph.nodes['g123']['osm_id'], 123)


class TestMultipolygonConversion(unittest.TestCase):
    def source_polygon(self, filename):
        root = ET.parse(FIXTURE_DIR / filename).getroot()
        nodes = {node.attrib['id']: (float(node.attrib['lon']), float(node.attrib['lat']))
                 for node in root.findall('node')}
        ways = {way.attrib['id']: [nd.attrib['ref'] for nd in way.findall('nd')]
                for way in root.findall('way')}
        # The fixtures reproduce the actual mismatch: every original OSM way
        # respects its node-reference limit, including ring closure references.
        self.assertTrue(all(len(refs) <= 2000 for refs in ways.values()))
        exterior = []
        interiors = []
        for member in root.find('relation').findall('member'):
            refs = ways[member.attrib['ref']]
            if member.attrib['role'] == 'outer':
                if exterior:
                    self.assertEqual(exterior[-1], refs[0])
                    exterior.extend(refs[1:])
                else:
                    exterior.extend(refs)
            else:
                interiors.append([nodes[ref] for ref in refs])
        return Polygon([nodes[ref] for ref in exterior], interiors)

    def convert_fixture(self, filename, config=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = asyncio.run(OSM2OSW(
                prefix='out', osm_file=FIXTURE_DIR / filename, workdir=tmpdir,
                config=config,
            ).convert())
            self.assertTrue(result.status, result.error)
            polygons_file = next(p for p in result.generated_files if p.endswith('polygons.geojson'))
            return json.loads(Path(polygons_file).read_text())['features']

    def assert_partitioned_output(self, features, original, limit):
        parts = [shape(f['geometry']) for f in features]
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(p.is_valid and p.area > 0 for p in parts))
        self.assertTrue(all(polygon_vertex_count(p) <= limit for p in parts))
        self.assertEqual({f['properties']['ext:osm_id'] for f in features}, {'20000'})
        self.assertEqual(len({f['properties']['_id'] for f in features}), len(features))
        self.assertTrue(all(f['properties']['name'] == 'Large park' for f in features))
        self.assertTrue(all(f['properties']['natural'] == 'wood' for f in features))
        combined = unary_union(parts)
        self.assertLess(original.symmetric_difference(combined).area, 1e-6)
        self.assertAlmostEqual(sum(p.area for p in parts), combined.area, places=10)
        self.assertFalse(combined.covers(Point(0, 0)))

    def test_relation_from_small_ways_generates_valid_partitioned_osw(self):
        filename = 'multipolygon_over_limit.osm'
        original = self.source_polygon(filename)
        self.assertEqual(polygon_vertex_count(original), 2412)
        # Exercise the default limit, custom configuration through the async
        # writer, and conversion even when output validation is disabled.
        for limit, validate in ((2000, True), (128, True), (128, False)):
            with self.subTest(limit=limit, validate=validate):
                features = self.convert_fixture(filename, FormatterConfig(
                    max_geometry_vertices=limit, validate_output=validate,
                ))
                self.assert_partitioned_output(features, original, limit)

    def test_polygon_at_limit_is_exported_without_partitioning(self):
        filename = 'multipolygon_at_limit.osm'
        original = self.source_polygon(filename)
        self.assertEqual(polygon_vertex_count(original), 2000)
        features = self.convert_fixture(filename)
        self.assertEqual(len(features), 1)
        output = shape(features[0]['geometry'])
        self.assertEqual(polygon_vertex_count(output), 2000)
        self.assertTrue(output.equals(original))
        self.assertEqual(len(output.interiors), 1)

    def test_total_vertices_include_holes_even_when_each_ring_is_within_limit(self):
        filename = 'polygon_holes_over_limit.osm'
        original = self.source_polygon(filename)
        self.assertEqual(len(original.exterior.coords) - 1, 1200)
        self.assertEqual(len(original.interiors[0].coords) - 1, 1200)
        features = self.convert_fixture(filename)
        self.assert_partitioned_output(features, original, 2000)


if __name__ == '__main__':
    unittest.main()
