import math
import unittest
import json

import importlib.util
import sys
import types
from pathlib import Path

# Stub ogr2osm before loading the module under test
sys.modules['ogr2osm'] = types.SimpleNamespace(TranslationBase=object)

module_path = Path(__file__).resolve().parents[3] / 'src/osm_osw_reformatter/serializer/osm/osm_normalizer.py'
spec = importlib.util.spec_from_file_location('osm_normalizer', module_path)
osn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(osn)

OSMNormalizer = osn.OSMNormalizer


class DummyOsmGeometry:
    def __init__(self, tags=None, osm_id=-1):
        self.tags = tags or {}
        self.id = osm_id


class DummyMember:
    def __init__(self, ref):
        self.ref = ref


class DummyRel:
    def __init__(self, rel_id, members=None):
        self.id = rel_id
        self.members = members or []
        self.tags = {}


class DummyOgrGeom:
    def __init__(self, point):
        self.point = point

    def GetCoordinateDimension(self):
        return len(self.point)

    def GetPointCount(self):
        return 1

    def GetPoint(self, idx):
        return self.point

    def GetGeometryCount(self):
        return 0

    def GetGeometryRef(self, idx):
        return None


class TestOSMNormalizer(unittest.TestCase):
    def setUp(self):
        self.normalizer = OSMNormalizer()

    def test_stash_ext_canonicalizes_json(self):
        tags = {}
        self.normalizer._stash_ext(tags, 'detail', '{ "name": "Bob" }')
        self.assertEqual(json.loads(tags['ext:detail']), {"name": "Bob"})

        tags2 = {}
        self.normalizer._stash_ext(tags2, 'meta', {"foo": "bar"})
        self.assertEqual(json.loads(tags2['ext:meta']), {"foo": "bar"})

    def test_stash_ext_handles_exceptions(self):
        class Bad:
            def __str__(self):
                raise RuntimeError("boom")
        tags = {}
        with self.assertRaises(RuntimeError):
            self.normalizer._stash_ext(tags, 'bad', Bad())

    def test_stash_ext_ignores_none(self):
        tags = {}
        self.normalizer._stash_ext(tags, 'nothing', None)
        self.assertNotIn('ext:nothing', tags)

    def test_stash_ext_invalid_json_string(self):
        tags = {}
        # Invalid JSON should fall through the final canonicalization except block
        self.normalizer._stash_ext(tags, 'bad_json', '{oops}')
        self.assertEqual(tags['ext:bad_json'], '{oops}')

    def test_filter_tags_moves_unknown_and_invalid_datatypes(self):
        tags = {
            'highway': 'footway',
            'foot': 'yes',
            'climb': 'sideways',
            'incline': 'steep',
            'width': 'NaN',
            'mystery': 'value',
            'nested': {'a': 1},
            'listval': [1, 2],
        }
        result = self.normalizer.filter_tags(tags)
        self.assertNotIn('foot', result)
        self.assertNotIn('climb', result)
        self.assertNotIn('incline', result)
        self.assertNotIn('width', result)
        self.assertNotIn('mystery', result)
        self.assertNotIn('nested', result)
        self.assertNotIn('listval', result)
        self.assertEqual(result.get('highway'), 'footway')
        self.assertEqual(result.get('ext:climb'), 'sideways')
        self.assertEqual(result.get('ext:incline'), 'steep')
        self.assertEqual(result.get('ext:width'), 'NaN')
        self.assertEqual(result.get('ext:mystery'), 'value')
        self.assertEqual(json.loads(result.get('ext:nested')), {"a": 1})
        self.assertEqual(json.loads(result.get('ext:listval')), [1, 2])

    def test_filter_tags_adds_area_for_zones(self):
        tags = {'highway': 'pedestrian', '_w_id': '1'}
        result = self.normalizer.filter_tags(tags)
        self.assertEqual(result.get('area'), 'yes')

    def test_process_feature_post_sets_id_and_elevation(self):
        osmgeom = DummyOsmGeometry(tags={'ext:osm_id': ['10']}, osm_id=-5)
        ogrgeom = DummyOgrGeom((1.0, 2.0, 3.0))
        self.normalizer.process_feature_post(osmgeom, None, ogrgeom)
        self.assertEqual(osmgeom.id, 10)
        self.assertEqual(osmgeom.tags.get('ext:elevation'), ['3.0'] if isinstance(osmgeom.tags.get('ext:elevation'), list) else '3.0')

    def test_process_feature_post_set_tag_branches(self):
        # tags contains list key -> replace with list
        osmgeom_list = DummyOsmGeometry(tags={'ext:elevation': ['x'], '_id': ['2']}, osm_id=2)
        self.normalizer.process_feature_post(osmgeom_list, None, DummyOgrGeom((0, 0, 2)))
        self.assertEqual(osmgeom_list.tags.get('ext:elevation'), ['2.0'])
        # tags contains scalar key -> overwrite scalar
        osmgeom_scalar = DummyOsmGeometry(tags={'ext:elevation': 'old', '_id': ['3']}, osm_id=3)
        self.normalizer.process_feature_post(osmgeom_scalar, None, DummyOgrGeom((0, 0, 3)))
        self.assertEqual(osmgeom_scalar.tags.get('ext:elevation'), '3.0')

    def test_extract_elevation_rejects_nan(self):
        self.assertIsNone(self.normalizer._extract_elevation(DummyOgrGeom((0, 0, float('nan')))))
        class BadGeom:
            def GetCoordinateDimension(self):
                raise RuntimeError("bad")
        self.assertIsNone(self.normalizer._extract_elevation(BadGeom()))
        class BadGeom2:
            def GetCoordinateDimension(self):
                return 3
            def GetPointCount(self):
                raise RuntimeError("bad")
            def GetGeometryCount(self):
                raise RuntimeError("bad2")
        self.assertIsNone(self.normalizer._extract_elevation(BadGeom2()))
        # Not enough coordinates
        class TwoDGeom:
            def GetCoordinateDimension(self):
                return 3
            def GetPointCount(self):
                return 1
            def GetPoint(self, idx):
                return (1, 2)
            def GetGeometryCount(self):
                return 0
        self.assertIsNone(self.normalizer._extract_elevation(TwoDGeom()))
        # Non-numeric z
        self.assertIsNone(self.normalizer._extract_elevation(DummyOgrGeom((0, 0, 'abc'))))

    def test_process_output_normalizes_negative_ids(self):
        node = DummyOsmGeometry(tags={'_id': ['-1']}, osm_id=-1)
        way = DummyOsmGeometry(tags={'_id': ['-2']}, osm_id=-2)
        class RefObj:
            def __init__(self, rid):
                self.id = rid
        way.refs = [RefObj(-1)]
        rel_member = DummyMember(ref=RefObj(-3))
        rel = DummyRel(-4, members=[rel_member])
        self.normalizer.process_output([node], [way], [rel])

        self.assertGreaterEqual(node.id, 0)
        self.assertGreaterEqual(way.id, 0)
        self.assertGreaterEqual(rel.id, 0)
        self.assertGreaterEqual(rel.members[0].ref.id, 0)
        refs = getattr(way, 'refs', [])
        self.assertTrue(all(getattr(r, 'id', r) >= 0 for r in refs))
        # _id tag updated
        tag_val = node.tags.get('_id')
        if isinstance(tag_val, list):
            self.assertIn(str(node.id), tag_val)
        else:
            self.assertEqual(tag_val, str(node.id))

    def test_process_output_handles_various_refs_and_attrs(self):
        way = DummyOsmGeometry(tags={'_id': ['-9']}, osm_id=-9)
        way.nodeRefs = [-1, DummyOsmGeometry(tags={}, osm_id=-2), "raw"]
        rel_member = DummyMember(ref=-5)
        rel = DummyRel(-6, members=[rel_member])
        self.normalizer.process_output([], [way], [rel])
        refs = getattr(way, "nds", None) or getattr(way, "refs", None) or getattr(way, "nodeRefs", None) or getattr(way, "nodes", None)
        for r in refs:
            if isinstance(r, int):
                self.assertGreaterEqual(r, 0)
            elif hasattr(r, 'id'):
                self.assertGreaterEqual(r.id, 0)
            else:
                self.assertIsInstance(r, str)
        self.assertGreaterEqual(rel.members[0].ref, 0)


if __name__ == '__main__':
    unittest.main()
