import gc
import os
import asyncio
import traceback
from pathlib import Path
from ..helpers.osw import OSWHelper
from ..helpers.response import Response


class OSM2OSW:
    def __init__(self, prefix: str, osm_file=None, workdir=None):
        self.osm_file_path = str(Path(osm_file))
        filename = os.path.basename(osm_file).replace('.pbf', '').replace('.xml', '').replace('.osm', '')
        self.workdir = workdir
        self.filename = f'{prefix + "." if prefix else ""}{filename}'
        self.generated_files = []

    async def convert(self) -> Response:
        try:
            print('Creating networks from region extracts...')
            tasks = [OSWHelper.get_osm_graph(self.osm_file_path)]
            osm_graph_results = await asyncio.gather(*tasks)
            osm_graph_results = list(osm_graph_results)
            OG = osm_graph_results[0]

            await OSWHelper.simplify_og(OG)
            await OSWHelper.construct_geometries(OG)

            # for OG in osm_graph_results:
            generated_files = await OSWHelper.write_og(self.workdir, self.filename, OG)

            print(f'Created OSW files!')
            self.generated_files = generated_files

            del tasks
            del osm_graph_results
            del OG
            del generated_files
            resp = Response(status=True, generated_files=self.generated_files)
        except Exception as error:
            traceback.print_exc()
            print(error)
            resp = Response(status=False, error=str(error))
        finally:
            gc.collect()
        return resp
