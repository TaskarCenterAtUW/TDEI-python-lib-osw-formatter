import unittest
from tempfile import TemporaryDirectory

from src.osm_osw_reformatter import Formatter, FormatterConfig


class TestFormatterConfig(unittest.TestCase):
    def test_default_config_matches_validator_defaults(self):
        config = FormatterConfig()

        self.assertEqual(config.coordinate_precision, 7)
        self.assertTrue(config.allow_zero_length_lines)
        self.assertTrue(config.validate_input)
        self.assertTrue(config.validate_output)

    def test_formatter_accepts_direct_config_overrides(self):
        with TemporaryDirectory() as tmpdir:
            formatter = Formatter(
                workdir=tmpdir,
                file_path="test.osm",
                coordinate_precision=6,
                allow_zero_length_lines=False,
                validate_input=False,
                validate_output=False,
            )

        self.assertEqual(formatter.config.coordinate_precision, 6)
        self.assertFalse(formatter.config.allow_zero_length_lines)
        self.assertFalse(formatter.config.validate_input)
        self.assertFalse(formatter.config.validate_output)

    def test_coordinate_precision_must_be_integer(self):
        with self.assertRaises(TypeError):
            FormatterConfig(coordinate_precision=True)

    def test_coordinate_precision_must_be_zero_or_greater(self):
        with self.assertRaises(ValueError):
            FormatterConfig(coordinate_precision=-1)

    def test_allow_zero_length_lines_must_be_boolean(self):
        with self.assertRaises(TypeError):
            FormatterConfig(allow_zero_length_lines="yes")

    def test_validate_input_must_be_boolean(self):
        with self.assertRaises(TypeError):
            FormatterConfig(validate_input="yes")

    def test_validate_output_must_be_boolean(self):
        with self.assertRaises(TypeError):
            FormatterConfig(validate_output="yes")


if __name__ == "__main__":
    unittest.main()
