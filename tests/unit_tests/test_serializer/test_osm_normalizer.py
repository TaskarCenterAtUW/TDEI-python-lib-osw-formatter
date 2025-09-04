import unittest
from src.osm_osw_reformatter.serializer.osm.osm_normalizer import OSMNormalizer

class TestOSMNormalizeWidthField(unittest.TestCase):
    def setUp(self):
        self.normalizer = OSMNormalizer()


    def test_removes_width_when_value_is_nan_string(self):
        tags = {"highway": "footway", "width": 'NaN'}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertNotIn('width', normalizer)


    def test_removes_width_when_value_is_non_numeric_string(self):
        tags = {"highway": "footway", "width": 'hello'}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertNotIn('width', normalizer)

    def test_preserves_width_when_value_is_float(self):
        tags = {"highway": "footway", "width": 1.2}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertIn('width', normalizer)

    def test_preserves_width_when_value_is_int(self):
        tags = {"highway": "footway", "width": 10}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertIn('width', normalizer)

    def test_removes_width_when_value_is_actual_nan(self):
        tags = {"highway": "footway", "width": float('nan')}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertNotIn('width', normalizer)

    def test_preserves_width_when_value_is_float_with_string(self):
        tags = {"highway": "footway", "width": '1.525'}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertIsInstance(normalizer, dict)
        self.assertIn('highway', normalizer)
        self.assertIn('width', normalizer)
        self.assertEqual(normalizer['width'], '1.525')


class TestOSMNormalizeInclineField(unittest.TestCase):
    def setUp(self):
        self.normalizer = OSMNormalizer()

    def test_retains_existing_incline_and_climb(self):
        tags = {"highway": "footway", "incline": 0.014, "climb": "up"}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertEqual(normalizer["incline"], "0.014")
        self.assertEqual(normalizer["climb"], "up")

    def test_derives_climb_from_positive_incline(self):
        tags = {"highway": "footway", "incline": 0.014}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertEqual(normalizer["climb"], "up")
        self.assertEqual(normalizer["incline"], "0.014")

    def test_derives_climb_from_negative_incline(self):
        tags = {"highway": "footway", "incline": -0.014}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertEqual(normalizer["climb"], "down")
        self.assertEqual(normalizer["incline"], "-0.014")
