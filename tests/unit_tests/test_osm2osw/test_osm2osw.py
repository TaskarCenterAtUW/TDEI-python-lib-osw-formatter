import os
import re
import json
import asyncio
import tempfile
import unittest
import math
from src.osm_osw_reformatter.config import FormatterConfig
from src.osm_osw_reformatter.osm2osw.osm2osw import OSM2OSW
from src.osm_osw_reformatter.serializer.osw.osw_normalizer import OSW_SCHEMA_ID

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'output')
TEST_FILE = os.path.join(ROOT_DIR, 'test_files/wa.microsoft.osm.pbf')
TEST_WIDTH_FILE = os.path.join(ROOT_DIR, 'test_files/width-test.xml')
TEST_INCLINE_FILE = os.path.join(ROOT_DIR, 'test_files/incline-test.xml')
TEST_INVALID_NODE_TAGS_FILE = os.path.join(ROOT_DIR, 'test_files/node_with_invalid_tags.xml')
TEST_TREE_FILE = os.path.join(ROOT_DIR, 'test_files/tree-test.xml')
TEST_BUG_3477_FILE = os.path.join(ROOT_DIR, 'test_files/bug_3477.xml')
TEST_BUG_3286_FILE = os.path.join(ROOT_DIR, 'test_files/bug_3286.xml')
TEST_NONSTANDARD_TAGS_FILE = os.path.join(ROOT_DIR, 'test_files/input_validation/nonstandard_tags.xml')


def is_valid_float(value):
    try:
        f = float(value)
        return not math.isnan(f)
    except (ValueError, TypeError):
        return False

class TestOSM2OSW(unittest.IsolatedAsyncioTestCase):
    def test_convert_successful(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertTrue(result.status)
            for file in result.generated_files:
                os.remove(file)

        asyncio.run(run_test())

    def test_generated_files(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertEqual(len(result.generated_files), 6)
            for file in result.generated_files:
                os.remove(file)

        asyncio.run(run_test())

    def test_generated_with_valid_width_tag(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()

            self.assertEqual(len(result.generated_files), 6)

            for file in result.generated_files:
                if file.endswith('.geojson'):
                    with open(file, 'r') as f:
                        geojson = json.load(f)
                        for feature in geojson.get("features", []):
                            props = feature.get("properties", {})
                            if "width" in props:
                                width_val = props["width"]
                                self.assertTrue(
                                    is_valid_float(width_val),
                                    msg=f"Invalid width value '{width_val}' in file {file}"
                                )

                os.remove(file)

        asyncio.run(run_test())

    def test_generated_files_include_nodes_points_edges(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            for file_path in result.generated_files:
                self.assertTrue(re.search(r'(nodes|points|edges|zones|polygons|lines)', file_path))
            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_generated_files_are_string(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            for file_path in result.generated_files:
                self.assertIsInstance(file_path, str)
            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    async def test_convert_error(self):
        async def mock_count_entities_error(osm_file_path, counter_cls):
            raise Exception("Error in counting entities")

        osm2osw = OSM2OSW(osm_file='test.pbf', workdir='work_dir', prefix='test')

        result = await osm2osw.convert()
        self.assertFalse(result.status)

    def test_ext_tags_present_in_output(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertTrue(result.status)

            has_ext_tag = False
            for file_path in result.generated_files:
                if file_path.endswith('.geojson'):
                    with open(file_path) as f:
                        geojson = json.load(f)
                        for feature in geojson.get('features', []):
                            props = feature.get('properties', {})
                            if any(k.startswith("ext:") for k in props):
                                has_ext_tag = True
                                break
                    if has_ext_tag:
                        break

            self.assertTrue(has_ext_tag, "No ext: tags found in generated GeoJSON features")

            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_nodes_file_has_point_geometry(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertTrue(result.status)

            for file_path in result.generated_files:
                if "nodes" in file_path:
                    with open(file_path) as f:
                        geojson = json.load(f)
                        for feature in geojson["features"]:
                            self.assertEqual(feature["geometry"]["type"], "Point")
                    break

            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_all_feature_ids_are_strings(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertTrue(result.status)

            for file_path in result.generated_files:
                with open(file_path) as f:
                    geojson = json.load(f)
                    for feature in geojson.get("features", []):
                        self.assertIn("_id", feature["properties"])
                        self.assertIsInstance(feature["properties"]["_id"], str)

            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_no_empty_features(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertTrue(result.status)

            for file_path in result.generated_files:
                with open(file_path) as f:
                    geojson = json.load(f)
                    for feature in geojson.get("features", []):
                        self.assertIn("geometry", feature)
                        self.assertIsNotNone(feature["geometry"])
                        self.assertIn("type", feature["geometry"])
                        self.assertIn("coordinates", feature["geometry"])

            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_no_duplicate_ids_in_file(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertTrue(result.status)

            for file_path in result.generated_files:
                with open(file_path) as f:
                    geojson = json.load(f)
                    seen_ids = set()
                    for feature in geojson.get("features", []):
                        _id = feature["properties"].get("_id")
                        self.assertNotIn(_id, seen_ids, f"Duplicate _id: {_id} in {file_path}")
                        seen_ids.add(_id)

            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_outputs_use_osw_03_schema(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='schema03')
            result = await osm2osw.convert()
            self.assertTrue(result.status)

            for file_path in result.generated_files:
                if file_path.endswith('.geojson'):
                    with open(file_path) as f:
                        data = json.load(f)
                        self.assertEqual(data.get("$schema"), OSW_SCHEMA_ID)
                os.remove(file_path)

        asyncio.run(run_test())

    def test_tree_coverage_emitted_under_osw_03(self):
        osm_file_path = TEST_TREE_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='tree')
            result = await osm2osw.convert()
            self.assertTrue(result.status)

            points = lines = polys = None
            for file_path in result.generated_files:
                if file_path.endswith('.graph.points.geojson'):
                    points = file_path
                elif file_path.endswith('.graph.lines.geojson'):
                    lines = file_path
                elif file_path.endswith('.graph.polygons.geojson'):
                    polys = file_path

            self.assertIsNotNone(points, "Points output missing")
            self.assertIsNotNone(lines, "Lines output missing")
            self.assertIsNotNone(polys, "Polygons output missing")

            with open(points) as f:
                data = json.load(f)
                self.assertEqual(data.get("$schema"), OSW_SCHEMA_ID)
                naturals = [feat["properties"].get("natural") for feat in data.get("features", [])]
                self.assertIn("tree", naturals)

            with open(lines) as f:
                data = json.load(f)
                self.assertEqual(data.get("$schema"), OSW_SCHEMA_ID)
                naturals = [feat["properties"].get("natural") for feat in data.get("features", [])]
                self.assertIn("tree_row", naturals)

            with open(polys) as f:
                data = json.load(f)
                self.assertEqual(data.get("$schema"), OSW_SCHEMA_ID)
                naturals = [feat["properties"].get("natural") for feat in data.get("features", [])]
                self.assertIn("wood", naturals)

            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_retains_incline_tag(self):
        osm_file_path = TEST_INCLINE_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertTrue(result.status)

            found_incline = False
            for file_path in result.generated_files:
                if file_path.endswith('edges.geojson'):
                    with open(file_path) as f:
                        geojson = json.load(f)
                        for feature in geojson.get('features', []):
                            props = feature.get('properties', {})
                            if 'incline' in props:
                                self.assertIsInstance(props['incline'], (int, float))
                                found_incline = True
                    break

            for file_path in result.generated_files:
                os.remove(file_path)

            self.assertTrue(found_incline, 'Incline tag not found in output edges')

        asyncio.run(run_test())

    def test_will_not_generate_nodes_file_if_node_with_invalid_tags(self):
        osm_file_path = TEST_INVALID_NODE_TAGS_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertEqual(len(result.generated_files), 0)
            for file in result.generated_files:
                os.remove(file)

        asyncio.run(run_test())

    def test_bug_3477_ext_only_closed_way_emits_polygon(self):
        osm_file_path = TEST_BUG_3477_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='bug3477')
            result = await osm2osw.convert()
            self.assertTrue(result.status)
            self.assertEqual(len(result.generated_files), 1)

            polygon_file = result.generated_files[0]
            self.assertTrue(polygon_file.endswith('.graph.polygons.geojson'))

            with open(polygon_file) as f:
                geojson = json.load(f)

            self.assertEqual(geojson.get("$schema"), OSW_SCHEMA_ID)
            self.assertEqual(len(geojson.get("features", [])), 1)

            feature = geojson["features"][0]
            self.assertEqual(feature["geometry"]["type"], "Polygon")
            self.assertEqual(feature["properties"].get("ext:demolished:building"), "yes")

            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_bug_3286_consecutive_duplicate_nodes(self):
        osm_file_path = TEST_BUG_3286_FILE

        async def run_test():
            # Dropping the collapsed segment is the opt-out behavior.
            osm2osw = OSM2OSW(
                osm_file=osm_file_path,
                workdir=OUTPUT_DIR,
                prefix='test',
                config=FormatterConfig(allow_zero_length_lines=False),
            )
            result = await osm2osw.convert()
            self.assertTrue(result.status)
            self.assertEqual(len(result.generated_files), 2)

            for file_path in result.generated_files:
                if file_path.endswith('edges.geojson'):
                    with open(file_path) as f:
                        geojson = json.load(f)
                        self.assertEqual(len(geojson.get("features", [])), 1)

            for file_path in result.generated_files:
                os.remove(file_path)

        asyncio.run(run_test())

    def test_non_standard_tags_are_written_under_ext(self):
        """Unknown keys, and invalid values on known keys, move under ext:*."""
        expected = {
            'nodes': {'ext:check_date': '2024-05-01'},
            'points': {'ext:backrest': 'yes'},
            'edges': {'ext:lit': 'yes', 'ext:incline': 'steep'},
            'lines': {'ext:material': 'wood'},
            'zones': {'ext:smoothness': 'good'},
            'polygons': {'ext:roof:shape': 'flat'},
        }

        async def run_test():
            with tempfile.TemporaryDirectory() as tmpdir:
                result = await OSM2OSW(
                    osm_file=TEST_NONSTANDARD_TAGS_FILE,
                    workdir=tmpdir,
                    prefix='ext',
                ).convert()
                self.assertTrue(result.status, msg=result.error)

                properties = {}
                for file_path in result.generated_files:
                    dataset = os.path.basename(file_path).split('.')[-2]
                    with open(file_path) as f:
                        properties[dataset] = [
                            feature['properties'] for feature in json.load(f)['features']
                        ]

            self.assertEqual(set(expected), set(properties))
            for dataset, ext_tags in expected.items():
                merged = {k: v for props in properties[dataset] for k, v in props.items()}
                for key, value in ext_tags.items():
                    self.assertEqual(merged.get(key), value, msg=f'{dataset}.{key}')
                    # The bare key must not survive alongside its ext: form.
                    self.assertNotIn(key[len('ext:'):], merged, msg=f'{dataset}.{key}')

            # Schema tags stay bare: tactile_paving is a real OSW kerb field.
            node_tags = {k: v for props in properties['nodes'] for k, v in props.items()}
            self.assertEqual(node_tags.get('tactile_paving'), 'yes')
            self.assertNotIn('ext:tactile_paving', node_tags)

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
