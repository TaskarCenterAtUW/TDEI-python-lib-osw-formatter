import os
import zipfile
import unittest
import xml.etree.ElementTree as ET
from src.osm_osw_reformatter import Formatter

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'output')
TEST_ZIP_FILE = os.path.join(ROOT_DIR, 'test_files/test_roundtrip.zip')
TEST_XML_FILE = os.path.join(ROOT_DIR, 'test_files/test_roundtrip.xml')


def parse_osm_file(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    nodes = []
    ways = []
    for elem in root:
        if elem.tag == 'node':
            nodes.append(elem)
        elif elem.tag == 'way':
            ways.append(elem)
    return nodes, ways

def extract_ext_tags(elems):
    """Extract all ext:* tags from a list of XML elements."""
    ext_tags = set()
    for elem in elems:
        for tag in elem.findall("tag"):
            k = tag.attrib.get('k', '')
            v = tag.attrib.get('v', '')
            if k.startswith('ext:'):
                ext_tags.add((k, v))
    return ext_tags

def generate_zip(filepaths):
    zip_path = f'{OUTPUT_DIR}/first_roundtrip_geojson.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filepath in filepaths:
            arcname = os.path.basename(filepath)
            zipf.write(filepath, arcname)
    return zip_path

class TestRoundTrip(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.formatter = Formatter(workdir=OUTPUT_DIR, file_path=TEST_ZIP_FILE, prefix='test_roundtrip')
        convert = self.formatter.osw2osm()
        self.generated_osm_file = convert.generated_files
        print(self.generated_osm_file)

    def tearDown(self):
        self.formatter.cleanup()

    def compare_osm_files(self, file1, file2):
        nodes1, ways1 = parse_osm_file(file1)
        nodes2, ways2 = parse_osm_file(file2)

        # Get all ext:* tags from both files
        ext_tags1 = extract_ext_tags(nodes1) | extract_ext_tags(ways1)
        ext_tags2 = extract_ext_tags(nodes2) | extract_ext_tags(ways2)

        # Check all tags in file1 are present in file2
        missing_ext_tags = ext_tags1 - ext_tags2

        if missing_ext_tags:
            print(f"Missing ext:* tags in output: {missing_ext_tags}")

        self.assertTrue(
            not missing_ext_tags,
            f"These ext:* tags from the input are missing in the output: {missing_ext_tags}"
        )

    async def test_roundtrip(self):
        # First roundtrip: OSW -> OSM XML -> OSW (GeoJSON) -> OSM XML
        formatter = Formatter(workdir=OUTPUT_DIR, file_path=self.generated_osm_file, prefix='first_roundtrip_geojson')
        result = await formatter.osm2osw()
        generated_files = result.generated_files
        first_round_zip = generate_zip(generated_files)

        formatter = Formatter(workdir=OUTPUT_DIR, file_path=first_round_zip, prefix='second_roundtrip_xml')
        convert = formatter.osw2osm()
        generated_osm_file = convert.generated_files

        self.compare_osm_files(self.generated_osm_file, generated_osm_file)

        formatter.cleanup()

class TestXMLRoundTrip(unittest.IsolatedAsyncioTestCase):

    def compare_osm_files(self, file1, file2):
        nodes1, ways1 = parse_osm_file(file1)
        nodes2, ways2 = parse_osm_file(file2)

        # Get all ext:* tags from both files
        ext_tags1 = extract_ext_tags(nodes1) | extract_ext_tags(ways1)
        ext_tags2 = extract_ext_tags(nodes2) | extract_ext_tags(ways2)

        # Check all tags in file1 are present in file2
        missing_ext_tags = ext_tags1 - ext_tags2

        if missing_ext_tags:
            print(f"Missing ext:* tags in output: {missing_ext_tags}")

        self.assertTrue(
            not missing_ext_tags,
            f"These ext:* tags from the input are missing in the output: {missing_ext_tags}"
        )

    async def test_xml_roundtrip(self):
        formatter = Formatter(workdir=OUTPUT_DIR, file_path=TEST_XML_FILE, prefix='first_roundtrip_geojson')
        result = await formatter.osm2osw()
        generated_files = result.generated_files
        first_round_zip = generate_zip(generated_files)

        formatter = Formatter(workdir=OUTPUT_DIR, file_path=first_round_zip, prefix='second_roundtrip_xml')
        convert = formatter.osw2osm()
        generated_osm_file = convert.generated_files

        self.compare_osm_files(TEST_XML_FILE, generated_osm_file)
        formatter.cleanup()

