import os
import re
import json
import asyncio
import unittest
from src.osm_osw_reformatter.osm2osw.osm2osw import OSM2OSW

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'output')
TEST_FILE = os.path.join(ROOT_DIR, 'test_files/wa.microsoft.osm.pbf')


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

    def test_generated_3_files(self):
        osm_file_path = TEST_FILE

        async def run_test():
            osm2osw = OSM2OSW(osm_file=osm_file_path, workdir=OUTPUT_DIR, prefix='test')
            result = await osm2osw.convert()
            self.assertEqual(len(result.generated_files), 4)
            for file in result.generated_files:
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
                            if any(k.startswith("ext") for k in props):
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


if __name__ == '__main__':
    unittest.main()
