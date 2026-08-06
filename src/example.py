import os
import asyncio
from osm_osw_reformatter import Formatter
import argparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = f'{ROOT_DIR}/output'
OSM_INPUT_FILE = f'{ROOT_DIR}/fixtures/zero_length_way_only.xml'
OSW_INPUT_FILE = f'{ROOT_DIR}/fixtures/invalid_osw.zip'

is_exists = os.path.exists(OUTPUT_DIR)
if not is_exists:
    os.makedirs(OUTPUT_DIR)

config = FormatterConfig(
        coordinate_precision=7,
        allow_zero_length_lines=True,
    )

async def osm_convert():
    f = Formatter(workdir=OUTPUT_DIR, file_path=OSM_INPUT_FILE)
    await f.osm2osw()
    # Uncomment below line to clean up the generated files
    # f.cleanup()


def osw_convert():
    f = Formatter(workdir=OUTPUT_DIR, file_path=OSW_INPUT_FILE)
    results = f.osw2osm()
    if not results.status:
        print(results.error)
    # Uncomment below line to clean up the generated files
    # f.cleanup()


if __name__ == '__main__':
    asyncio.run(osm_convert())
    # osw_convert()

def main():
    parser = argparse.ArgumentParser(description='Convert between OSM and OSW')
    parser.add_argument('-i', '--input', required=True, help='input file path')
    parser.add_argument('-o', '--output', required=True, help='output directory')
    parser.add_argument('-s', '--mode', required=True, choices=['OSW2OSM', 'OSM2OSW'], help='conversion mode')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    f = Formatter(workdir=args.output, file_path=args.input)

    if args.mode == 'OSM2OSW':
        asyncio.run(f.osm2osw())
    else:
        f.osw2osm()

if __name__ == '__main__':
    main()