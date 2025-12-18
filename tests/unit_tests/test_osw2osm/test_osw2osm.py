import json
import os
from pathlib import Path
import tempfile
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


def _create_custom_property_zip(zip_path: str, properties: dict) -> str:
    """Create a temporary OSW dataset with custom/non-compliant properties."""
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0.0, 1.0], [0.0, 2.0]]
                },
                "properties": {
                    "_id": "10",
                    "_u_id": "2",
                    "_v_id": "3",
                    "highway": "footway",
                    "foot": "yes",
                    **properties
                }
            }
        ]
    }
    edges_path = Path(os.path.dirname(zip_path)) / "custom_edges.geojson"
    with open(edges_path, "w") as fh:
        json.dump(geojson, fh)
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(edges_path, arcname='edges.geojson')
    return zip_path


def _create_3d_node_zip(zip_path: str, z_value: float) -> str:
    """Create an OSW dataset with a 3D node to test elevation extraction."""
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    nodes_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-122.363431818197, 47.6778173599078, z_value]
                },
                "properties": {"_id": "n1", "kerb": "flush", "barrier": "kerb"}
            }
        ]
    }
    nodes_path = Path(os.path.dirname(zip_path)) / "nodes_3d.geojson"
    with open(nodes_path, "w") as fh:
        json.dump(nodes_geojson, fh)
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(nodes_path, arcname='nodes.geojson')
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
                self.assertEqual(tags.get('ext:incline'), 'steep')
            if tags.get('_id') == '1':
                self.assertEqual(tags.get('incline'), '0.1')

        self.assertEqual(len(root.findall(".//tag[@k='incline']")), 1)

        os.remove(result.generated_files)
        os.remove(zip_file)

    def test_osm_elements_have_version_attribute(self):
        zip_file = TEST_WIDTH_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='version')
        result = osw2osm.convert()

        tree = ET.parse(result.generated_files)
        root = tree.getroot()

        for element in root.findall('.//node') + root.findall('.//way') + root.findall('.//relation'):
            self.assertEqual(element.get('version'), '1')

        os.remove(result.generated_files)

    def test_visible_elements_gain_version_attribute(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        xml_path = os.path.join(OUTPUT_DIR, 'visible_version.xml')
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="0" lon="0" visible="true" />
  <node id="2" lat="1" lon="1" />
  <way id="10" visible="true">
    <nd ref="1" />
  </way>
</osm>
"""
        with open(xml_path, 'w') as fh:
            fh.write(xml_content)

        OSW2OSM._ensure_version_attribute(Path(xml_path))

        tree = ET.parse(xml_path)
        root = tree.getroot()

        visible_nodes = [n for n in root.findall('.//node') if n.get('visible') == 'true']
        visible_ways = [w for w in root.findall('.//way') if w.get('visible') == 'true']

        self.assertTrue(visible_nodes, "Expected at least one visible node in test fixture")
        self.assertTrue(visible_ways, "Expected at least one visible way in test fixture")

        for element in visible_nodes + visible_ways:
            self.assertEqual(element.get('version'), '1')

        os.remove(xml_path)

    def test_non_compliant_properties_promoted_to_ext_tags(self):
        zip_path = os.path.join(OUTPUT_DIR, 'dataset_with_custom_props.zip')
        props = {
            "incline": "steep",
            "metadata": {"color": "blue"}
        }
        zip_file = _create_custom_property_zip(zip_path, props)
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='custom')
        result = osw2osm.convert()

        tree = ET.parse(result.generated_files)
        root = tree.getroot()

        way = root.find('.//way')
        tags = {tag.get('k'): tag.get('v') for tag in way.findall('tag')}

        self.assertNotIn('incline', tags)
        self.assertEqual(tags.get('ext:incline'), 'steep')
        self.assertEqual(tags.get('ext:metadata'), '{"color": "blue"}')

        os.remove(result.generated_files)
        os.remove(zip_file)
        custom_edges = Path(os.path.dirname(zip_path)) / "custom_edges.geojson"
        if custom_edges.exists():
            os.remove(custom_edges)

    def test_3d_coordinates_promoted_to_ext_elevation(self):
        zip_path = os.path.join(OUTPUT_DIR, 'dataset_with_3d_node.zip')
        zip_file = _create_3d_node_zip(zip_path, 0.0)
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='elevation')
        result = osw2osm.convert()

        self.assertTrue(result.status, msg=getattr(result, 'error', 'Conversion failed'))
        tree = ET.parse(result.generated_files)
        root = tree.getroot()

        node = root.find('.//node')
        tags = {tag.get('k'): tag.get('v') for tag in node.findall('tag')}
        self.assertEqual(tags.get('ext:elevation'), '0.0')

        if result.generated_files:
            os.remove(result.generated_files)
        if zip_file and os.path.exists(zip_file):
            os.remove(zip_file)
        nodes_path = Path(os.path.dirname(zip_path)) / "nodes_3d.geojson"
        if nodes_path.exists():
            os.remove(nodes_path)

    def test_ids_are_sequential_per_type(self):
        zip_file = TEST_WIDTH_ZIP_FILE
        osw2osm = OSW2OSM(zip_file_path=zip_file, workdir=OUTPUT_DIR, prefix='sequential')
        result = osw2osm.convert()

        OSW2OSM._remap_ids_to_sequential(Path(result.generated_files))
        tree = ET.parse(result.generated_files)
        root = tree.getroot()

        node_ids = sorted(int(n.get('id')) for n in root.findall('.//node'))
        way_ids = sorted(int(w.get('id')) for w in root.findall('.//way'))
        rel_ids = sorted(int(r.get('id')) for r in root.findall('.//relation'))

        self.assertEqual(node_ids, list(range(1, len(node_ids) + 1)))
        self.assertEqual(way_ids, list(range(1, len(way_ids) + 1)))
        if rel_ids:
            self.assertEqual(rel_ids, list(range(1, len(rel_ids) + 1)))

        os.remove(result.generated_files)

    def test_remap_ids_rewrites_refs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = Path(tmpdir, "sample.osm.xml")
            xml_path.write_text(
                """<osm version="0.6">
  <node id="10" lat="0" lon="0"><tag k="_id" v="10"/></node>
  <node id="20" lat="1" lon="1"><tag k="_id" v="20"/></node>
  <way id="30">
    <nd ref="10"/><nd ref="20"/>
    <tag k="_id" v="30"/>
  </way>
  <relation id="40">
    <member type="node" ref="20" role=""/>
    <member type="way" ref="30" role=""/>
    <tag k="_id" v="40"/>
  </relation>
</osm>"""
            )

            OSW2OSM._remap_ids_to_sequential(xml_path)

            root = ET.parse(xml_path).getroot()
            node_ids = [n.get("id") for n in root.findall(".//node")]
            way_ids = [w.get("id") for w in root.findall(".//way")]
            rel_ids = [r.get("id") for r in root.findall(".//relation")]

            self.assertEqual(node_ids, ["1", "2"])
            self.assertEqual(way_ids, ["1"])
            self.assertEqual(rel_ids, ["1"])

            nd_refs = [nd.get("ref") for nd in root.findall(".//way/nd")]
            self.assertEqual(nd_refs, ["1", "2"])

            member_refs = [(m.get("type"), m.get("ref")) for m in root.findall(".//relation/member")]
            self.assertEqual(member_refs, [("node", "2"), ("way", "1")])

            node_tag_ids = [tag.get("v") for tag in root.findall(".//node/tag[@k='_id']")]
            self.assertEqual(node_tag_ids, ["1", "2"])
            way_tag_ids = [tag.get("v") for tag in root.findall(".//way/tag[@k='_id']")]
            self.assertEqual(way_tag_ids, ["1"])
            rel_tag_ids = [tag.get("v") for tag in root.findall(".//relation/tag[@k='_id']")]
            self.assertEqual(rel_tag_ids, ["1"])


if __name__ == '__main__':
    unittest.main()
