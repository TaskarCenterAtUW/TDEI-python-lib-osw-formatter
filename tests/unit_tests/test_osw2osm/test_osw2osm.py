import os
import zipfile
import unittest
from src.osm_osw_reformatter.osw2osm.osw2osm import OSW2OSM
import xml.etree.ElementTree as ET

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'output')
TEST_ZIP_FILE = os.path.join(ROOT_DIR, 'test_files/osw.zip')
TEST_WIDTH_ZIP_FILE = os.path.join(ROOT_DIR, 'test_files/width-test.zip')
TEST_DATA_WITH_INCLINE_ZIP_FILE = os.path.join(ROOT_DIR, 'test_files/dataset_with_incline.zip')
TEST_EDGES_WITH_INVALID_INCLINE_FILE = os.path.join(ROOT_DIR, 'test_files/edges_invalid_incline.geojson')
TEST_NODES_WITH_INVALID_INCLINE_FILE = os.path.join(ROOT_DIR, 'test_files/nodes_invalid_incline.geojson')


def _create_invalid_incline_zip(zip_path: str) -> str:
    """Create a temporary OSW dataset with invalid incline values.

    The resulting ZIP mirrors the structure expected by ``OSW2OSM`` and contains
    both ``edges.geojson`` and ``nodes.geojson`` files.

    Args:
        zip_path: Location where the archive will be written.

    Returns:
        The path to the generated ZIP archive.
    """
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(TEST_EDGES_WITH_INVALID_INCLINE_FILE, arcname='edges.geojson')
        zf.write(TEST_NODES_WITH_INVALID_INCLINE_FILE, arcname='nodes.geojson')
    return zip_path


class TestOSW2OSM(unittest.IsolatedAsyncioTestCase):
    def test_convert_successful(self):
        zip_file = TEST_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        self.assertTrue(result.status)
        os.remove(result.generated_files)

    def test_generated_file(self):
        zip_file = TEST_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        self.assertEqual(len([result.generated_files]), 1)
        os.remove(result.generated_files)

    def test_generated_file_should_be_xml(self):
        zip_file = TEST_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        self.assertTrue(result.generated_files.endswith('.xml'))
        os.remove(result.generated_files)

    def test_generated_file_should_be_xml_and_valid_width_tag(self):
        zip_file = TEST_WIDTH_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        self.assertTrue(result.generated_files.endswith('.xml'))
        xml_file_path = result.generated_files

        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        for tag in root.findall(".//tag[@k='width']"):
            value = tag.get('v', '').strip()
            self.assertNotEqual(value, '', msg="Width tag value is empty")
            try:
                float_val = float(value)
                self.assertFalse(float_val != float_val, msg=f"Width tag value is NaN: {value}")
            except ValueError:
                self.fail(f"Width tag value is not a valid float: {value}")

        os.remove(result.generated_files)

    def test_convert_generated_files_are_string(self):
        zip_file = TEST_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        self.assertIsInstance(result.generated_files, str)
        os.remove(result.generated_files)

    async def test_convert_error(self):
        osw2osm = OSW2OSM(zip_file_path='test.zip', workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        self.assertFalse(result.status)

    def test_generated_file_does_not_contain_climb_tag(self):
        zip_file = TEST_DATA_WITH_INCLINE_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        xml_file_path = result.generated_files

        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        self.assertEqual(len(root.findall(".//tag[@k='climb']")), 0)

        os.remove(result.generated_files)

    def test_generated_file_contains_incline_tag(self):
        zip_file = TEST_DATA_WITH_INCLINE_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        xml_file_path = result.generated_files

        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        self.assertGreater(len(root.findall(".//tag[@k='incline']")), 0)

        os.remove(result.generated_files)

    def test_incline_tags_do_not_have_climb(self):
        zip_file = TEST_DATA_WITH_INCLINE_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='test')
        result = osw2osm.convert()
        xml_file_path = result.generated_files

        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        for element in root.findall('.//way') + root.findall('.//node') + root.findall('.//relation'):
            tags = {tag.get('k'): tag.get('v') for tag in element.findall('tag')}
            if 'incline' in tags and float(tags.get('incline', 0) or 0) != 0:
                self.assertNotIn('climb', tags)

        os.remove(result.generated_files)

    def test_invalid_incline_values_are_excluded(self):
        zip_path = os.path.join(OUTPUT_DIR, 'dataset_with_invalid_incline.zip')
        zip_file = _create_invalid_incline_zip(zip_path)
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='invalid')
        result = osw2osm.convert()

        # Ensure conversion succeeded so the XML file path is valid
        self.assertTrue(result.status, msg=getattr(result, 'error', 'Conversion failed'))
        xml_file_path = result.generated_files

        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        for way in root.findall('.//way'):
            tags = {tag.get('k'): tag.get('v') for tag in way.findall('tag')}
            if tags.get('_id') == '2':
                self.assertNotIn('incline', tags)
            if tags.get('_id') == '1':
                self.assertEqual(tags.get('incline'), '0.1')

        self.assertEqual(len(root.findall(".//tag[@k='incline']")), 1)

        os.remove(result.generated_files)
        os.remove(zip_file)


if __name__ == '__main__':
    unittest.main()
