import os
import asyncio
from osm_osw_reformatter import Formatter

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = f'{ROOT_DIR}/output'
OSM_INPUT_FILE = f'{ROOT_DIR}/input/wedgewood_output.osm.pbf'
OSW_INPUT_FILE = f'{ROOT_DIR}/input/wa.seattle.zip'

is_exists = os.path.exists(OUTPUT_DIR)
if not is_exists:
    os.makedirs(OUTPUT_DIR)


async def osm_convert():
    f = Formatter(workdir=OUTPUT_DIR, file_path=OSM_INPUT_FILE)
    await f.osm2osw()
    # Uncomment below line to clean up the generated files
    # f.cleanup()


def osw_convert():
    f = Formatter(workdir=OUTPUT_DIR, file_path=OSW_INPUT_FILE)
    f.osw2osm()
    # Uncomment below line to clean up the generated files
    # f.cleanup()


if __name__ == '__main__':
    asyncio.run(osm_convert())
    osw_convert()
