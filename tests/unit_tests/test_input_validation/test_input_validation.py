import asyncio
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src.osm_osw_reformatter.config import FormatterConfig
from src.osm_osw_reformatter.helpers.input_validation import (
    INVALID_OSW_INPUT_ERROR,
    InputValidationError,
    OSMCoordinatePrecisionError,
    OSMFileCorruptError,
    OSWFileUnreadableError,
    format_issues,
    format_validation_error,
    osm_exceeds_coordinate_precision,
    validate_osm_input,
    validate_osw_input,
)
from src.osm_osw_reformatter.helpers.output_validation import (
    INVALID_OSW_OUTPUT_ERROR,
    OSWOutputValidationError,
    validate_osw_output,
)
from src.osm_osw_reformatter.osm2osw.osm2osw import OSM2OSW
from src.osm_osw_reformatter.osw2osm.osw2osm import OSW2OSM


# Tracked copies of the datasets in the repo-root `fixtures/` folder, which is
# gitignored and only used for local/manual runs.
FIXTURE_DIR = Path(__file__).parents[1] / 'test_files' / 'input_validation'
VALID_OSW_ZIP = FIXTURE_DIR / 'valid_osw.zip'
INVALID_OSW_ZIP = FIXTURE_DIR / 'invalid_osw.zip'
VALID_OSM_XML = FIXTURE_DIR / 'valid_osm.xml'
INVALID_OSM_XML = FIXTURE_DIR / 'invalid_osm.xml'
CORRUPT_OSM_XML = FIXTURE_DIR / 'corrupt_osm.xml'


class TestValidateOSWInput(unittest.TestCase):
    def test_valid_dataset_passes_validation(self):
        validate_osw_input(str(VALID_OSW_ZIP))

    def test_invalid_dataset_raises_with_validator_issues(self):
        with self.assertRaises(InputValidationError) as ctx:
            validate_osw_input(str(INVALID_OSW_ZIP))

        self.assertTrue(ctx.exception.issues)
        self.assertIn(INVALID_OSW_INPUT_ERROR, str(ctx.exception))
        for message in ctx.exception.messages:
            self.assertIn(message, str(ctx.exception))

    def test_issues_name_the_file_and_feature_they_came_from(self):
        with self.assertRaises(InputValidationError) as ctx:
            validate_osw_input(str(INVALID_OSW_ZIP))

        reported_files = {issue.get('filename') for issue in ctx.exception.issues}
        self.assertEqual(
            reported_files,
            {'nodes.geojson', 'edges.geojson', 'points.geojson', 'lines.geojson', 'zones.geojson'},
        )
        self.assertIn("edges.geojson (feature 0): ", '\n'.join(ctx.exception.messages))

    def test_repeated_issue_messages_are_reported_once(self):
        duplicate = {'filename': 'zones.geojson', 'feature_index': 0, 'error_message': ['bad foot']}

        messages = format_issues([duplicate, dict(duplicate)])

        self.assertEqual(messages, ['zones.geojson (feature 0): bad foot'])

    def test_issue_without_a_feature_index_is_reported_against_the_file(self):
        messages = format_issues(
            [{'filename': 'dataset.zip', 'feature_index': None, 'error_message': 'unreadable'}]
        )

        self.assertEqual(messages, ['dataset.zip: unreadable'])

    def test_missing_file_is_reported_in_plain_language(self):
        with self.assertRaises(OSWFileUnreadableError) as ctx:
            validate_osw_input('does-not-exist.zip')

        message = str(ctx.exception)
        self.assertIn("'does-not-exist.zip' could not be found", message)
        self.assertNotIn('Errno', message)

    def test_file_that_is_not_a_zip_is_reported_in_plain_language(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir, 'not_a_zip.zip')
            zip_path.write_text('this is plain text, not a zip')

            with self.assertRaises(OSWFileUnreadableError) as ctx:
                validate_osw_input(str(zip_path))

        message = str(ctx.exception)
        self.assertIn("'not_a_zip.zip' is not a valid zip archive", message)
        # The caller's absolute path must not leak into the message.
        self.assertNotIn(tmpdir, message)

    def test_archive_without_datasets_is_reported_in_plain_language(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir, 'not_osw.zip')
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr('readme.txt', 'this is not an OSW dataset')

            with self.assertRaises(OSWFileUnreadableError) as ctx:
                validate_osw_input(str(zip_path))

        self.assertIn("contains no .geojson files", str(ctx.exception))

    def test_archive_errors_are_still_input_validation_errors(self):
        with self.assertRaises(InputValidationError):
            validate_osw_input('does-not-exist.zip')

    def test_format_validation_error_without_details(self):
        message = format_validation_error([])

        self.assertIn(INVALID_OSW_INPUT_ERROR, message)


class TestOSW2OSMInputValidation(unittest.TestCase):
    def test_invalid_dataset_is_reported_back_to_the_caller(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(INVALID_OSW_ZIP),
                workdir=tmpdir,
                prefix='invalid',
            ).convert()

        self.assertFalse(result.status)
        self.assertIsNone(result.generated_files)
        self.assertIn(INVALID_OSW_INPUT_ERROR, result.error)

    def test_invalid_dataset_is_rejected_before_conversion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.osm_osw_reformatter.osw2osm.osw2osm.OSWHelper.unzip') as unzip:
                result = OSW2OSM(
                    zip_file_path=str(INVALID_OSW_ZIP),
                    workdir=tmpdir,
                    prefix='invalid',
                ).convert()

        self.assertFalse(result.status)
        unzip.assert_not_called()

    def test_validation_can_be_switched_off(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                'src.osm_osw_reformatter.osw2osm.osw2osm.validate_osw_input'
            ) as validate:
                OSW2OSM(
                    zip_file_path=str(INVALID_OSW_ZIP),
                    workdir=tmpdir,
                    prefix='invalid',
                    config=FormatterConfig(validate_input=False),
                ).convert()

        validate.assert_not_called()

    def test_valid_dataset_converts_successfully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(VALID_OSW_ZIP),
                workdir=tmpdir,
                prefix='valid',
            ).convert()

            self.assertTrue(result.status, msg=result.error)
            self.assertTrue(Path(result.generated_files).exists())


class TestValidateOSMInput(unittest.TestCase):
    def test_coordinates_within_precision_pass(self):
        validate_osm_input(str(VALID_OSM_XML))

    def test_coordinates_above_precision_raise(self):
        with self.assertRaises(OSMCoordinatePrecisionError) as ctx:
            validate_osm_input(str(INVALID_OSM_XML))

        self.assertEqual(
            str(ctx.exception),
            "invalid input file, the file has GPS locations with higher than "
            "7-digits precision that TDEI doesn't allow. "
            "Please clean your dataset and resubmit",
        )

    def test_message_reports_the_configured_precision(self):
        with self.assertRaises(OSMCoordinatePrecisionError) as ctx:
            validate_osm_input(
                str(VALID_OSM_XML),
                config=FormatterConfig(coordinate_precision=3),
            )

        self.assertIn('higher than 3-digits precision', str(ctx.exception))

    def test_precision_boundary_is_exact(self):
        """One digit over the limit is rejected; there is no tolerance."""
        cases = {
            '47.6555000': False,      # exactly at the limit
            '47.6555': False,         # under the limit
            '47': False,              # no decimal part
            '47.65550001': True,      # one digit over
            '47.655500001': True,
            '47.65550000': True,      # 8 written digits, even though the last is zero
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            for latitude, should_reject in cases.items():
                osm_path = Path(tmpdir, f'{latitude}.xml')
                osm_path.write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<osm version="0.6">\n'
                    f'  <node id="1" lat="{latitude}" lon="-122.3095000" version="1"/>\n'
                    '</osm>\n'
                )

                self.assertEqual(
                    osm_exceeds_coordinate_precision(str(osm_path), 7),
                    should_reject,
                    msg=f'lat={latitude}',
                )

    def test_corrupt_file_raises_a_readable_error(self):
        with self.assertRaises(OSMFileCorruptError) as ctx:
            validate_osm_input(str(CORRUPT_OSM_XML))

        message = str(ctx.exception)
        self.assertEqual(
            message,
            'invalid input file, the OSM file is corrupted and could not be read. '
            'The problem is at line 3, column 65. '
            'Please fix the file and resubmit',
        )
        # Parser jargon stays on `detail`, out of the user-facing message.
        self.assertNotIn('well-formed', message)
        self.assertNotIn('token', message)
        self.assertIn('well-formed', ctx.exception.detail)

    def test_corrupt_file_without_a_position_still_reads_cleanly(self):
        error = OSMFileCorruptError('something went wrong')

        self.assertEqual(
            str(error),
            'invalid input file, the OSM file is corrupted and could not be read. '
            'Please fix the file and resubmit',
        )
        self.assertIsNone(error.line)

    def test_truncated_file_raises_a_readable_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            osm_path = Path(tmpdir, 'truncated.osm')
            osm_path.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<osm version="0.6">\n'
                '  <node id="1" lat="47.6555000" lon="-122.3105000" version="1"/>\n'
            )

            with self.assertRaises(OSMFileCorruptError):
                validate_osm_input(str(osm_path))

    def test_pbf_coordinates_are_checked(self):
        pbf_path = Path(__file__).parents[1] / 'test_files' / 'wa.microsoft.osm.pbf'

        # PBF stores coordinates in units of 1e-7 degrees, so 7 decimals always fit.
        self.assertFalse(osm_exceeds_coordinate_precision(str(pbf_path), 7))
        self.assertTrue(osm_exceeds_coordinate_precision(str(pbf_path), 2))


class TestOSM2OSWInputValidation(unittest.TestCase):
    def _convert(self, osm_file, config=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            return asyncio.run(
                OSM2OSW(
                    prefix='precision',
                    osm_file=str(osm_file),
                    workdir=tmpdir,
                    config=config,
                ).convert()
            )

    def test_high_precision_input_is_rejected(self):
        result = self._convert(INVALID_OSM_XML)

        self.assertFalse(result.status)
        self.assertEqual(result.generated_files, [])
        self.assertIn("TDEI doesn't allow", result.error)

    def test_high_precision_input_is_rejected_before_conversion(self):
        with patch('src.osm_osw_reformatter.osm2osw.osm2osw.OSWHelper.get_osm_graph') as get_graph:
            result = self._convert(INVALID_OSM_XML)

        self.assertFalse(result.status)
        get_graph.assert_not_called()

    def test_validation_can_be_switched_off(self):
        result = self._convert(INVALID_OSM_XML, config=FormatterConfig(validate_input=False))

        self.assertTrue(result.status, msg=result.error)

    def test_corrupt_file_is_reported_instead_of_crashing(self):
        result = self._convert(CORRUPT_OSM_XML)

        self.assertFalse(result.status)
        self.assertEqual(result.generated_files, [])
        self.assertIn('the OSM file is corrupted and could not be read', result.error)
        self.assertNotIn('well-formed', result.error)

    def test_corrupt_file_is_reported_even_with_validation_off(self):
        """The parser fails during conversion; the caller still gets the message."""
        result = self._convert(CORRUPT_OSM_XML, config=FormatterConfig(validate_input=False))

        self.assertFalse(result.status)
        self.assertIn('the OSM file is corrupted and could not be read', result.error)
        # osmium words its failure differently; the user sees the same sentence.
        self.assertNotIn('XML parsing error', result.error)

    def test_valid_input_converts_successfully(self):
        result = self._convert(VALID_OSM_XML)

        self.assertTrue(result.status, msg=result.error)
        self.assertTrue(result.generated_files)


class TestValidateOSWOutput(unittest.TestCase):
    SCHEMA = 'https://sidewalks.washington.edu/opensidewalks/0.3/schema.json'

    def _write_edges(self, directory, properties):
        path = Path(directory, 'out.graph.edges.geojson')
        path.write_text(json.dumps({
            '$schema': self.SCHEMA,
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [[-122.3105000, 47.6555000], [-122.3100000, 47.6555000]],
                },
                'properties': properties,
            }],
        }))
        return str(path)

    def test_compliant_output_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_edges(tmpdir, {
                '_id': '1', '_u_id': '1', '_v_id': '2',
                'highway': 'footway', 'footway': 'sidewalk',
            })

            validate_osw_output([path])

    def test_non_compliant_output_raises_with_issues(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_edges(tmpdir, {
                '_id': '1', '_u_id': '1', '_v_id': '2',
                'highway': 'footway', 'footway': 'sidewalk',
                'width': 'NaN',
            })

            with self.assertRaises(OSWOutputValidationError) as ctx:
                validate_osw_output([path])

        self.assertTrue(ctx.exception.issues)
        self.assertIn(INVALID_OSW_OUTPUT_ERROR, str(ctx.exception))
        self.assertIn('width', str(ctx.exception))
        # Issues name the generated file they came from.
        self.assertIn('out.graph.edges.geojson', str(ctx.exception))

    def test_missing_files_are_not_validated(self):
        validate_osw_output(['does-not-exist.geojson'])
        validate_osw_output([])
        validate_osw_output(None)


class TestOSM2OSWOutputValidation(unittest.TestCase):
    def _convert(self, config=None, tamper=None):
        from src.osm_osw_reformatter.helpers.osw import OSWHelper

        original = OSWHelper.write_og
        if tamper is not None:
            OSWHelper.write_og = tamper(original)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                return asyncio.run(
                    OSM2OSW(
                        prefix='out',
                        osm_file=str(VALID_OSM_XML),
                        workdir=tmpdir,
                        config=config,
                    ).convert()
                )
        finally:
            OSWHelper.write_og = original

    @staticmethod
    def _break_edges(original):
        """Make the generated edges non-compliant after they are written."""
        def wrapper(cls, workdir, filename, og):
            async def _inner():
                paths = await original.__func__(cls, workdir, filename, og)
                for path in paths:
                    if path.endswith('edges.geojson'):
                        with open(path) as f:
                            data = json.load(f)
                        for feature in data['features']:
                            feature['properties']['width'] = 'NaN'
                        with open(path, 'w') as f:
                            json.dump(data, f)
                return paths
            return _inner()
        return classmethod(wrapper)

    def test_compliant_output_converts_successfully(self):
        result = self._convert()

        self.assertTrue(result.status, msg=result.error)

    def test_non_compliant_output_is_reported_to_the_caller(self):
        result = self._convert(tamper=self._break_edges)

        self.assertFalse(result.status)
        self.assertIn(INVALID_OSW_OUTPUT_ERROR, result.error)
        self.assertIn('width', result.error)

    def test_output_validation_can_be_switched_off(self):
        result = self._convert(
            config=FormatterConfig(validate_output=False),
            tamper=self._break_edges,
        )

        self.assertTrue(result.status, msg=result.error)


if __name__ == '__main__':
    unittest.main()
