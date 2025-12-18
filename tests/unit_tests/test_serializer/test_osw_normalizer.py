import unittest
import importlib.util
from pathlib import Path

module_path = Path(__file__).resolve().parents[3] / 'src/osm_osw_reformatter/serializer/osw/osw_normalizer.py'
spec = importlib.util.spec_from_file_location('osw_normalizer', module_path)
osw_normalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(osw_normalizer)

OSWWayNormalizer = osw_normalizer.OSWWayNormalizer
OSWNodeNormalizer = osw_normalizer.OSWNodeNormalizer
OSWPointNormalizer = osw_normalizer.OSWPointNormalizer
OSWLineNormalizer = osw_normalizer.OSWLineNormalizer
OSWPolygonNormalizer = osw_normalizer.OSWPolygonNormalizer
OSWZoneNormalizer = osw_normalizer.OSWZoneNormalizer
tactile_paving = osw_normalizer.tactile_paving
surface = osw_normalizer.surface
crossing_markings = osw_normalizer.crossing_markings
climb = osw_normalizer.climb
incline = osw_normalizer.incline
leaf_cycle = osw_normalizer.leaf_cycle
leaf_type = osw_normalizer.leaf_type
natural_point = osw_normalizer.natural_point
natural_line = osw_normalizer.natural_line
natural_polygon = osw_normalizer.natural_polygon
_normalize = osw_normalizer._normalize


class TestOSWWayNormalizer(unittest.TestCase):
    def test_is_sidewalk(self):
        tags = {'highway': 'footway', 'footway': 'sidewalk'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_sidewalk())

    def test_is_sidewalk_with_ext_tags(self):
        tags = {'ext:highway': 'footway', 'ext:footway': 'sidewalk'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_sidewalk())

    def test_is_crossing(self):
        tags = {'highway': 'footway', 'footway': 'crossing'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_crossing())

    def test_is_traffic_island(self):
        tags = {'highway': 'footway', 'footway': 'traffic_island'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_traffic_island())

    def test_is_footway(self):
        tags = {'highway': 'footway'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_footway())

    def test_is_stairs(self):
        tags = {'highway': 'steps'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_stairs())

    def test_is_stairs_with_invalid_climb(self):
        tags = {'highway': 'steps', 'climb': 'left'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_stairs())

    def test_is_pedestrian(self):
        tags = {'highway': 'pedestrian'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_pedestrian())

    def test_is_living_street(self):
        tags = {'highway': 'living_street'}
        normalizer = OSWWayNormalizer(tags)
        self.assertTrue(normalizer.is_living_street())

    def test_normalize_sidewalk(self):
        tags = {'highway': 'footway', 'footway': 'sidewalk', 'width': '1.5', 'surface': 'asphalt'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer.normalize()
        expected = {'highway': 'footway', 'width': 1.5, 'surface': 'asphalt', 'footway': 'sidewalk', 'foot': 'yes'}
        self.assertEqual(result, expected)

    def test_normalize_crossing(self):
        tags = {'highway': 'footway', 'footway': 'crossing'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer.normalize()
        expected = {'highway': 'footway', 'footway': 'crossing', 'foot': 'yes'}
        self.assertEqual(result, expected)

    def test_normalize_living_street_defaults_to_pedestrian_access(self):
        tags = {'highway': 'living_street', 'width': '6.5'}
        normalizer = OSWWayNormalizer(tags)

        result = normalizer.normalize()

        self.assertEqual(
            result,
            {'highway': 'living_street', 'width': 6.5, 'foot': 'yes'},
        )

    def test_normalize_incline(self):
        tags = {'highway': 'footway', 'incline': '10'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer.normalize()
        expected = {'highway': 'footway', 'incline': 10.0, 'foot': 'yes'}
        self.assertEqual(result, expected)

    def test_normalize_length(self):
        tags = {'highway': 'footway', 'length': '12'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer.normalize()
        expected = {'highway': 'footway', 'length': 12.0, 'foot': 'yes'}
        self.assertEqual(result, expected)

    def test_normalize_stairs_keeps_climb(self):
        tags = {'highway': 'steps', 'climb': 'down', 'step_count': '3'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer.normalize()
        expected = {'highway': 'steps', 'climb': 'down', 'step_count': 3, 'foot': 'yes'}
        self.assertEqual(result, expected)

    def test_normalize_stairs_defaults_highway_and_no_foot(self):
        tags = {'climb': 'up'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer._normalize_stairs()
        expected = {'climb': 'up', 'foot': 'yes'}
        self.assertEqual(result, expected)

    def test_normalize_stairs_drops_invalid_climb(self):
        tags = {'highway': 'steps', 'climb': 'left'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer.normalize()
        expected = {'highway': 'steps', 'foot': 'yes'}
        self.assertEqual(result, expected)

    def test_normalize_invalid_way(self):
        tags = {'highway': 'invalid_type'}
        normalizer = OSWWayNormalizer(tags)
        with self.assertRaises(ValueError):
            normalizer.normalize()

    def test_osw_way_filter_helper(self):
        tags = {'highway': 'footway', 'footway': 'sidewalk'}
        self.assertTrue(OSWWayNormalizer.osw_way_filter(tags))
        tags = {'highway': 'motorway'}
        self.assertFalse(OSWWayNormalizer.osw_way_filter(tags))


class TestOSWNodeNormalizer(unittest.TestCase):
    def test_is_kerb(self):
        tags = {'kerb': 'flush'}
        normalizer = OSWNodeNormalizer(tags)
        self.assertTrue(normalizer.is_kerb())

    def test_is_kerb_with_ext_tags(self):
        tags = {'ext:kerb': 'flush'}
        normalizer = OSWNodeNormalizer(tags)
        self.assertTrue(normalizer.is_kerb())

    def test_is_kerb_with_ext_barrier_only(self):
        tags = {'ext:barrier': 'kerb'}
        normalizer = OSWNodeNormalizer(tags)
        self.assertTrue(normalizer.is_kerb())

    def test_is_kerb_invalid(self):
        tags = {'kerb': 'invalid_type'}
        normalizer = OSWNodeNormalizer(tags)
        self.assertFalse(normalizer.is_kerb())

    def test_normalize_kerb(self):
        tags = {'kerb': 'flush', 'barrier': 'some_barrier', 'tactile_paving': 'yes'}
        normalizer = OSWNodeNormalizer(tags)
        result = normalizer.normalize()
        expected = {'kerb': 'flush', 'barrier': 'some_barrier', 'tactile_paving': 'yes', 'barrier': 'kerb'}
        self.assertEqual(result, expected)

    def test_normalize_invalid_node(self):
        tags = {'type': 'invalid_node_type'}
        normalizer = OSWNodeNormalizer(tags)
        with self.assertRaises(ValueError):
            normalizer.normalize()


class TestOSWPointNormalizer(unittest.TestCase):
    def test_is_powerpole(self):
        tags = {'power': 'pole'}
        normalizer = OSWPointNormalizer(tags)
        self.assertTrue(normalizer.is_powerpole())

    def test_is_powerpole_invalid(self):
        tags = {'power': 'invalid_type'}
        normalizer = OSWPointNormalizer(tags)
        self.assertFalse(normalizer.is_powerpole())

    def test_normalize_powerpole(self):
        tags = {'power': 'pole', 'barrier': 'some_barrier', 'tactile_paving': 'yes'}
        normalizer = OSWPointNormalizer(tags)
        result = normalizer.normalize()
        expected = {'power': 'pole'}
        self.assertEqual(result, expected)

    def test_normalize_fire_hydrant(self):
        tags = {'emergency': 'fire_hydrant', 'name': 'Hydrant 42'}
        normalizer = OSWPointNormalizer(tags)
        result = normalizer.normalize()
        expected = {'emergency': 'fire_hydrant'}
        self.assertEqual(result, expected)

    def test_invalid_point_is_logged_and_skipped(self):
        tags = {'amenity': 'unknown'}
        normalizer = OSWPointNormalizer(tags)
        result = normalizer.normalize()
        self.assertEqual(result, {})

    def test_is_tree(self):
        tags = {'natural': 'tree'}
        normalizer = OSWPointNormalizer(tags)
        self.assertTrue(normalizer.is_tree())

    def test_is_tree_with_ext_tags(self):
        tags = {'ext:natural': 'tree'}
        normalizer = OSWPointNormalizer(tags)
        self.assertTrue(normalizer.is_tree())

    def test_normalize_tree(self):
        tags = {'natural': 'tree', 'leaf_cycle': 'Deciduous', 'leaf_type': 'needleLeaved'}
        normalizer = OSWPointNormalizer(tags)
        result = normalizer.normalize()
        expected = {'natural': 'tree', 'leaf_cycle': 'deciduous', 'leaf_type': 'needleleaved'}
        self.assertEqual(result, expected)


class TestOSWLineNormalizer(unittest.TestCase):
    def test_is_tree_row(self):
        tags = {'natural': 'tree_row'}
        normalizer = OSWLineNormalizer(tags)
        self.assertTrue(normalizer.is_tree_row())

    def test_is_fence_with_ext_tags(self):
        tags = {'ext:barrier': 'fence'}
        normalizer = OSWLineNormalizer(tags)
        self.assertTrue(normalizer.is_fence())

    def test_normalize_tree_row(self):
        tags = {'natural': 'tree_row', 'leaf_cycle': 'evergreen', 'leaf_type': 'leafless'}
        normalizer = OSWLineNormalizer(tags)
        result = normalizer.normalize()
        expected = {'natural': 'tree_row', 'leaf_cycle': 'evergreen', 'leaf_type': 'leafless'}
        self.assertEqual(result, expected)

    def test_invalid_line_raises(self):
        tags = {'barrier': 'wall'}
        normalizer = OSWLineNormalizer(tags)
        with self.assertRaises(ValueError):
            normalizer.normalize()


class TestOSWPolygonNormalizer(unittest.TestCase):
    def test_is_wood(self):
        tags = {'natural': 'wood'}
        normalizer = OSWPolygonNormalizer(tags)
        self.assertTrue(normalizer.is_wood())

    def test_is_building_with_ext_tags(self):
        tags = {'ext:building': 'yes'}
        normalizer = OSWPolygonNormalizer(tags)
        self.assertTrue(normalizer.is_building())

    def test_normalize_wood(self):
        tags = {'natural': 'wood', 'leaf_cycle': 'mixed', 'leaf_type': 'broadleaved'}
        normalizer = OSWPolygonNormalizer(tags)
        result = normalizer.normalize()
        expected = {'natural': 'wood', 'leaf_cycle': 'mixed', 'leaf_type': 'broadleaved'}
        self.assertEqual(result, expected)

    def test_invalid_polygon_raises(self):
        tags = {'natural': 'meadow'}
        normalizer = OSWPolygonNormalizer(tags)
        with self.assertRaises(ValueError):
            normalizer.normalize()


class TestOSWZoneNormalizer(unittest.TestCase):
    def test_invalid_zone_raises(self):
        tags = {'highway': 'residential'}
        normalizer = OSWZoneNormalizer(tags)
        with self.assertRaises(ValueError):
            normalizer.normalize()

    def test_is_pedestrian_with_ext_tags(self):
        tags = {'ext:highway': 'pedestrian'}
        normalizer = OSWZoneNormalizer(tags)
        self.assertTrue(normalizer.is_pedestrian())


class TestCommonFunctions(unittest.TestCase):
    def test_tactile_paving(self):
        self.assertTrue(tactile_paving('yes', {}))
        self.assertTrue(tactile_paving('contrasted', {}))
        self.assertEqual(tactile_paving('no', {}), 'no')
        self.assertIsNone(tactile_paving('invalid_value', {}))

    def test_surface(self):
        self.assertEqual(surface('asphalt', {}), 'asphalt')
        self.assertEqual(surface('concrete', {}), 'concrete')
        self.assertIsNone(surface('invalid_surface', {}))

    def test_crossing_markings_from_zebra_crossing_tag(self):
        self.assertEqual(crossing_markings('', {'crossing': 'zebra'}), 'zebra')

    def test_crossing_markings(self):
        self.assertEqual(crossing_markings('dashes', {'crossing:markings': 'dashes'}), 'dashes')
        self.assertEqual(crossing_markings('dots', {'crossing:markings': 'dots'}), 'dots')
        self.assertIsNone(crossing_markings('invalid_value', {'crossing:markings': 'invalid_value'}))

    def test_climb(self):
        self.assertEqual(climb('up', {}), 'up')
        self.assertEqual(climb('down', {}), 'down')
        self.assertIsNone(climb('invalid_value', {}))

    def test_incline(self):
        self.assertEqual(incline('10', {}), 10.0)
        self.assertEqual(incline('0.5', {}), 0.5)
        self.assertIsNone(incline('steep', {}))

    def test_leaf_cycle(self):
        self.assertEqual(leaf_cycle('Semi_deciduous', {}), 'semi_deciduous')
        self.assertIsNone(leaf_cycle('unknown', {}))

    def test_leaf_type(self):
        self.assertEqual(leaf_type('BroadLeaved', {}), 'broadleaved')
        self.assertIsNone(leaf_type('fake', {}))

    def test_kerb(self):
        self.assertEqual(osw_normalizer.kerb('flush', {}), 'flush')
        self.assertIsNone(osw_normalizer.kerb('invalid', {}))

    def test_foot(self):
        self.assertEqual(osw_normalizer.foot('designated', {}), 'designated')
        self.assertIsNone(osw_normalizer.foot('spaceship', {}))

    def test_natural_point_invalid(self):
        self.assertIsNone(natural_point('bush', {}))

    def test_natural_line_invalid(self):
        self.assertIsNone(natural_line('hedge', {}))

    def test_natural_polygon_invalid(self):
        self.assertIsNone(natural_polygon('meadow', {}))


class TestNormalizeWidthField(unittest.TestCase):
    def test_removes_width_when_value_is_nan_string(self):
        generic_keep_keys = {"highway": str, "width": float}
        generic_defaults = {}
        tags = {"highway": "footway", "width": 'NaN'}
        normalizer = _normalize(tags, generic_keep_keys, generic_defaults)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertNotIn('width', normalizer)

    def test_removes_width_when_value_is_non_numeric_string(self):
        generic_keep_keys = {"highway": str, "width": float}
        generic_defaults = {}
        tags = {"highway": "footway", "width": 'hello'}
        normalizer = _normalize(tags, generic_keep_keys, generic_defaults)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertNotIn('width', normalizer)

    def test_preserves_width_when_value_is_float(self):
        generic_keep_keys = {"highway": str, "width": float}
        generic_defaults = {}
        tags = {"highway": "footway", "width": 1.2}
        normalizer = _normalize(tags, generic_keep_keys, generic_defaults)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertIn('width', normalizer)

    def test_preserves_width_when_value_is_int(self):
        generic_keep_keys = {"highway": str, "width": float}
        generic_defaults = {}
        tags = {"highway": "footway", "width": 10}
        normalizer = _normalize(tags, generic_keep_keys, generic_defaults)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertIn('width', normalizer)

    def test_removes_width_when_value_is_actual_nan(self):
        generic_keep_keys = {"highway": str, "width": float}
        generic_defaults = {}
        tags = {"highway": "footway", "width": float('nan')}
        normalizer = _normalize(tags, generic_keep_keys, generic_defaults)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertNotIn('width', normalizer)

    def test_preserves_width_when_value_is_float_with_string(self):
        generic_keep_keys = {"highway": str, "width": float}
        generic_defaults = {}
        tags = {"highway": "footway", "width": '1.525'}
        normalizer = _normalize(tags, generic_keep_keys, generic_defaults)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertIn('width', normalizer)
        self.assertEqual(normalizer['width'], 1.525)

    def test_normalize_sets_literal_defaults(self):
        tags = {"foo": "bar"}
        keep_keys = {"foo": ["ext:foo_copy", "bar"]}
        result = _normalize(tags, keep_keys, {})
        self.assertEqual(result.get("ext:foo_copy"), "bar")



if __name__ == '__main__':
    unittest.main()
