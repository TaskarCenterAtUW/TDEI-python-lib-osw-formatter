import gc
import os
import asyncio
import traceback
from pathlib import Path
from ..config import FormatterConfig
from ..helpers.input_validation import (
    OSMCoordinatePrecisionError,
    OSMFileCorruptError,
    is_osm_parse_failure,
    validate_osm_input,
)
from ..helpers.osw import OSWHelper
from ..helpers.output_validation import (
    ConversionOutputError,
    ensure_generated_files,
    validate_osw_output,
)
from ..helpers.response import Response


class OSM2OSW:
    def __init__(self, prefix: str, osm_file=None, workdir=None, config: FormatterConfig = None):
        self.osm_file_path = str(Path(osm_file))
        filename = os.path.basename(osm_file).replace('.pbf', '').replace('.xml', '').replace('.osm', '')
        self.workdir = workdir
        self.filename = f'{prefix + "." if prefix else ""}{filename}'
        self.generated_files = []
        if config is not None and not isinstance(config, FormatterConfig):
            raise TypeError("config must be a FormatterConfig instance.")
        self.config = config or FormatterConfig()

    async def convert(self) -> Response:
        try:
            if self.config.validate_input:
                validate_osm_input(self.osm_file_path, config=self.config)

            print('Creating networks from region extracts...')
            tasks = [
                OSWHelper.get_osm_graph(
                    self.osm_file_path,
                    config=self.config,
                )
            ]
            try:
                osm_graph_results = await asyncio.gather(*tasks)
            except RuntimeError as error:
                # The reader raises RuntimeError both for unreadable files and
                # for complaints about the data; only the former is corruption.
                if is_osm_parse_failure(error):
                    raise OSMFileCorruptError(str(error)) from error
                raise
            osm_graph_results = list(osm_graph_results)
            OG = osm_graph_results[0]

            await OSWHelper.simplify_og(OG)
            await OSWHelper.construct_geometries(OG, config=self.config)

            # for OG in osm_graph_results:
            generated_files = await OSWHelper.write_og(self.workdir, self.filename, OG)
            self.generated_files = generated_files
            ensure_generated_files(generated_files, require_existing=True)
            if self.config.validate_output:
                validate_osw_output(generated_files, config=self.config)

            print(f'Created OSW files!')

            del tasks
            del osm_graph_results
            del OG
            del generated_files
            resp = Response(
                status=True,
                generated_files=self.generated_files,
            )
        except (OSMCoordinatePrecisionError, OSMFileCorruptError) as error:
            print(f'Invalid OSM input: {error}')
            resp = Response(
                status=False,
                generated_files=self.generated_files,
                error=str(error),
            )
        except ConversionOutputError as error:
            print(error)
            resp = Response(
                status=False,
                generated_files=self.generated_files,
                error=str(error),
            )
        except Exception as error:
            traceback.print_exc()
            print(error)
            resp = Response(
                status=False,
                generated_files=self.generated_files,
                error=str(error),
            )
        finally:
            gc.collect()
        return resp
