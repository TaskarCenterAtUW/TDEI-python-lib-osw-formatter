import os
import zipfile
import unittest
import subprocess
import shutil

from src.osm_osw_reformatter.osw2osm.osw2osm import OSW2OSM
from src.osm_osw_reformatter import Formatter

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'output')
TEST_DATA_WITH_INCLINE_ZIP_FILE = os.path.join(ROOT_DIR, 'test_files/dataset_with_incline.zip')


class TestOSMCompliance(unittest.IsolatedAsyncioTestCase):
    async def test_output_is_osm_compliant(self):
        osw2osm = OSW2OSM(zip_file_path=TEST_DATA_WITH_INCLINE_ZIP_FILE, workdir=OUTPUT_DIR, prefix='compliance')
        result = osw2osm.convert()
        osm_file = result.generated_files

        formatter = Formatter(workdir=OUTPUT_DIR, file_path=osm_file, prefix='compliance')
        res = await formatter.osm2osw()
        osw_files = res.generated_files

        zip_path = os.path.join(OUTPUT_DIR, 'compliance_osw.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in osw_files:
                zipf.write(f, os.path.basename(f))

        validator = shutil.which('osw-validate')
        if validator is None:
            self.skipTest('python-osw-validation not installed')
        proc = subprocess.run([validator, zip_path], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Validator output: {proc.stdout}\n{proc.stderr}")

        os.remove(osm_file)
        for f in osw_files:
            os.remove(f)
        os.remove(zip_path)
        formatter.cleanup()

