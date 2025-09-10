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
tactile_paving = osw_normalizer.tactile_paving
surface = osw_normalizer.surface
crossing_markings = osw_normalizer.crossing_markings
climb = osw_normalizer.climb
incline = osw_normalizer.incline
_normalize = osw_normalizer._normalize


class TestOSWWayNormalizer(unittest.TestCase):
    def test_is_sidewalk(self):
        tags = {'highway': 'footway', 'footway': 'sidewalk'}
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
        expected = {'highway': 'steps', 'climb': 'down', 'step_count': 3}
        self.assertEqual(result, expected)

    def test_normalize_stairs_defaults_highway_and_no_foot(self):
        tags = {'climb': 'up'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer._normalize_stairs()
        expected = {'highway': 'steps', 'climb': 'up'}
        self.assertEqual(result, expected)

    def test_normalize_stairs_drops_invalid_climb(self):
        tags = {'highway': 'steps', 'climb': 'left'}
        normalizer = OSWWayNormalizer(tags)
        result = normalizer.normalize()
        expected = {'highway': 'steps'}
        self.assertEqual(result, expected)

    def test_normalize_invalid_way(self):
        tags = {'highway': 'invalid_type'}
        normalizer = OSWWayNormalizer(tags)
        with self.assertRaises(ValueError):
            normalizer.normalize()


class TestOSWNodeNormalizer(unittest.TestCase):
    def test_is_kerb(self):
        tags = {'kerb': 'flush'}
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



if __name__ == '__main__':
    unittest.main()
