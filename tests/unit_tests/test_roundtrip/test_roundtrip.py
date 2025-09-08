import os
import zipfile
import unittest
import xml.etree.ElementTree as ET
from src.osm_osw_reformatter import Formatter

# Paths to test files and output directory
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'output')
TEST_ZIP_FILE = os.path.join(ROOT_DIR, 'test_files/test_roundtrip.zip')
TEST_XML_FILE = os.path.join(ROOT_DIR, 'test_files/test_roundtrip.xml')

### Helper to parse OSM XML and return all node and way elements ###
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

### Extract all ext:* tags (as (k,v) pairs) from a list of OSM XML elements ###
def extract_ext_tags(elems):
    ext_tags = set()
    for elem in elems:
        for tag in elem.findall("tag"):
            k = tag.attrib.get('k', '')
            v = tag.attrib.get('v', '')
            if k.startswith('ext:'):
                ext_tags.add((k, v))
    return ext_tags

### Utility: Given filepaths, bundle them into a zip for input to the formatter ###
def generate_zip(filepaths):
    zip_path = f'{OUTPUT_DIR}/first_roundtrip_geojson.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filepath in filepaths:
            arcname = os.path.basename(filepath)
            zipf.write(filepath, arcname)
    return zip_path

################################################################################
# Test 1: Full roundtrip starting from an OSW zip file
# This checks that all ext:* tags in the original OSM XML are preserved after:
# OSW zip → OSM XML → OSW (GeoJSON) → OSM XML
################################################################################

class TestRoundTrip(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Start with a zipped OSW input, convert to OSM XML
        self.formatter = Formatter(workdir=OUTPUT_DIR, file_path=TEST_ZIP_FILE, prefix='test_roundtrip')
        convert = self.formatter.osw2osm()
        self.assertTrue(convert.status, convert.error)
        self.generated_osm_file = convert.generated_files
        print(self.generated_osm_file)

    def tearDown(self):
        # Filter out any `None` entries before cleanup to avoid TypeError
        self.formatter.generated_files = [f for f in self.formatter.generated_files if f]
        if self.formatter.generated_files:
            self.formatter.cleanup()

    ### Compares ext:* tags in two OSM XML files ###
    def compare_osm_files(self, file1, file2):
        nodes1, ways1 = parse_osm_file(file1)
        nodes2, ways2 = parse_osm_file(file2)
        ext_tags1 = extract_ext_tags(nodes1) | extract_ext_tags(ways1)
        ext_tags2 = extract_ext_tags(nodes2) | extract_ext_tags(ways2)
        missing_ext_tags = ext_tags1 - ext_tags2

        if missing_ext_tags:
            print(f"Missing ext:* tags in output: {missing_ext_tags}")

        self.assertTrue(
            not missing_ext_tags,
            f"These ext:* tags from the input are missing in the output: {missing_ext_tags}"
        )

    async def test_roundtrip(self):
        # OSM XML → OSW (GeoJSON) → zip → OSM XML
        formatter = Formatter(workdir=OUTPUT_DIR, file_path=self.generated_osm_file, prefix='first_roundtrip_geojson')
        result = await formatter.osm2osw()
        self.assertTrue(result.status, result.error)
        generated_files = result.generated_files
        first_round_zip = generate_zip(generated_files)

        formatter = Formatter(workdir=OUTPUT_DIR, file_path=first_round_zip, prefix='second_roundtrip_xml')
        convert = formatter.osw2osm()
        self.assertTrue(convert.status, convert.error)
        generated_osm_file = convert.generated_files

        self.compare_osm_files(self.generated_osm_file, generated_osm_file)
        formatter.cleanup()

################################################################################
# Test 2: Full roundtrip starting from a plain OSM XML file (not zipped OSW)
# This is useful to ensure ext:* tags are preserved in a slightly different flow
################################################################################

class TestXMLRoundTrip(unittest.IsolatedAsyncioTestCase):

    def compare_osm_files(self, file1, file2):
        nodes1, ways1 = parse_osm_file(file1)
        nodes2, ways2 = parse_osm_file(file2)
        ext_tags1 = extract_ext_tags(nodes1) | extract_ext_tags(ways1)
        ext_tags2 = extract_ext_tags(nodes2) | extract_ext_tags(ways2)
        missing_ext_tags = ext_tags1 - ext_tags2

        if missing_ext_tags:
            print(f"Missing ext:* tags in output: {missing_ext_tags}")

        self.assertTrue(
            not missing_ext_tags,
            f"These ext:* tags from the input are missing in the output: {missing_ext_tags}"
        )

    async def test_xml_roundtrip(self):
        # Start from OSM XML → OSW (GeoJSON) → zip → OSM XML
        formatter = Formatter(workdir=OUTPUT_DIR, file_path=TEST_XML_FILE, prefix='first_roundtrip_geojson')
        result = await formatter.osm2osw()
        self.assertTrue(result.status, result.error)
        generated_files = result.generated_files
        first_round_zip = generate_zip(generated_files)

        formatter = Formatter(workdir=OUTPUT_DIR, file_path=first_round_zip, prefix='second_roundtrip_xml')
        convert = formatter.osw2osm()
        self.assertTrue(convert.status, convert.error)
        generated_osm_file = convert.generated_files

        self.compare_osm_files(TEST_XML_FILE, generated_osm_file)
        formatter.cleanup()

################################################################################

