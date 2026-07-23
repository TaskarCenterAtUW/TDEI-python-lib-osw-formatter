import unittest
from src.osm_osw_reformatter.helpers.response import Response


class TestResponseClass(unittest.TestCase):

    def test_default_values(self):
        response = Response(status=True)
        self.assertTrue(response.status)
        self.assertIsNone(response.generated_files)
        self.assertIsNone(response.error)
        self.assertEqual(response.warnings, "")

    def test_custom_values(self):
        files = ['file1.txt', 'file2.txt']
        response = Response(
            status=False,
            generated_files=files,
            error='An error message',
            warnings='A warning message',
        )
        self.assertFalse(response.status)
        self.assertEqual(response.generated_files, files)
        self.assertEqual(response.error, 'An error message')
        self.assertEqual(response.warnings, 'A warning message')

    def test_generated_files_string(self):
        response = Response(status=True, generated_files='file.txt')
        self.assertEqual(response.generated_files, 'file.txt')

    def test_generated_files_list(self):
        files = ['file1.txt', 'file2.txt']
        response = Response(status=True, generated_files=files)
        self.assertEqual(response.generated_files, files)

    def test_error_string(self):
        response = Response(status=False, error='An error message')
        self.assertEqual(response.error, 'An error message')

    def test_error_none(self):
        response = Response(status=True, error=None)
        self.assertIsNone(response.error)


if __name__ == '__main__':
    unittest.main()
