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

    def test_removes_existing_climb_and_retains_incline(self):
        tags = {"highway": "footway", "incline": 0.014, "climb": "up"}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertEqual(normalizer["incline"], "0.014")
        self.assertNotIn("climb", normalizer)

    def test_does_not_add_climb_from_positive_incline(self):
        tags = {"highway": "footway", "incline": 0.014}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertNotIn("climb", normalizer)
        self.assertEqual(normalizer["incline"], "0.014")

    def test_does_not_add_climb_from_negative_incline(self):
        tags = {"highway": "footway", "incline": -0.014}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertNotIn("climb", normalizer)
        self.assertEqual(normalizer["incline"], "-0.014")

    def test_does_not_add_climb_from_zero_incline(self):
        tags = {"highway": "footway", "incline": 0}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertEqual(normalizer["incline"], "0.0")
        self.assertNotIn("climb", normalizer)

    def test_removes_climb_without_incline(self):
        tags = {"highway": "footway", "climb": "down"}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertNotIn("climb", normalizer)
        self.assertNotIn("incline", normalizer)

    def test_discards_non_numeric_incline_without_climb(self):
        tags = {"highway": "footway", "incline": "steep"}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertNotIn("incline", normalizer)
        self.assertNotIn("climb", normalizer)

    def test_retains_climb_when_highway_is_steps(self):
        tags = {"highway": "steps", "climb": "up"}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertIn("climb", normalizer)
        self.assertEqual(normalizer["climb"], "up")
        self.assertNotIn("incline", normalizer)

    def test_retains_climb_down_when_highway_is_steps(self):
        tags = {"highway": "steps", "climb": "down"}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertIn("climb", normalizer)
        self.assertEqual(normalizer["climb"], "down")

    def test_discards_invalid_climb_when_highway_is_steps(self):
        tags = {"highway": "steps", "climb": "sideways"}
        normalizer = self.normalizer.filter_tags(tags)
        self.assertNotIn("climb", normalizer)


class TestOSMProcessFeaturePost(unittest.TestCase):
    class DummyGeometry:
        def __init__(self, tags, osm_id=None):
            self.tags = tags
            self.id = osm_id

    def setUp(self):
        self.normalizer = OSMNormalizer()

    def test_assigns_ext_osm_id_to_geometry(self):
        geometry = self.DummyGeometry({"ext:osm_id": ["12345"]})

        self.normalizer.process_feature_post(geometry, ogrfeature=None, ogrgeometry=None)

        self.assertEqual(geometry.id, 12345)

    def test_falls_back_to_internal_id_tag(self):
        geometry = self.DummyGeometry({"_id": ["67890"]})

        self.normalizer.process_feature_post(geometry, ogrfeature=None, ogrgeometry=None)

        self.assertEqual(geometry.id, 67890)

    def test_keeps_existing_id_when_no_tags_present(self):
        geometry = self.DummyGeometry({}, osm_id=555)

        self.normalizer.process_feature_post(geometry, ogrfeature=None, ogrgeometry=None)

        self.assertEqual(geometry.id, 555)

    def test_ignores_empty_ext_osm_id_values(self):
        geometry = self.DummyGeometry({"ext:osm_id": [""], "_id": ["2468"]})

        self.normalizer.process_feature_post(geometry, ogrfeature=None, ogrgeometry=None)

        self.assertEqual(geometry.id, 2468)


if __name__ == '__main__':
    unittest.main()