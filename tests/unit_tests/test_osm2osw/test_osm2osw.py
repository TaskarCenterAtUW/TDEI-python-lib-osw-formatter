import os
import re
import json
import asyncio
import unittest
import math
from src.osm_osw_reformatter.osm2osw.osm2osw import OSM2OSW

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'output')
TEST_FILE = os.path.join(ROOT_DIR, 'test_files/wa.microsoft.osm.pbf')
TEST_WIDTH_FILE = os.path.join(ROOT_DIR, 'test_files/width-test.xml')
TEST_INCLINE_FILE = os.path.join(ROOT_DIR, 'test_files/incline-test.xml')


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


if __name__ == '__main__':
    unittest.main()
