import gc
import os
import asyncio
import traceback
from pathlib import Path
from ..config import FormatterConfig
from ..helpers.osw import OSWHelper
from ..helpers.output_validation import ConversionOutputError, ensure_generated_files
from ..helpers.response import Response
from ..helpers.warnings import WarningCollector, input_file_has_excess_coordinate_precision


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
        warnings = WarningCollector(self.config.coordinate_precision)
        try:
            if input_file_has_excess_coordinate_precision(
                self.osm_file_path,
                self.config.coordinate_precision,
            ):
                warnings.add_coordinate_precision()

            print('Creating networks from region extracts...')
            tasks = [
                OSWHelper.get_osm_graph(
                    self.osm_file_path,
                    config=self.config,
                    warnings=warnings,
                )
            ]
            osm_graph_results = await asyncio.gather(*tasks)
            osm_graph_results = list(osm_graph_results)
            OG = osm_graph_results[0]

            await OSWHelper.simplify_og(OG)
            await OSWHelper.construct_geometries(OG, config=self.config, warnings=warnings)

            # for OG in osm_graph_results:
            generated_files = await OSWHelper.write_og(self.workdir, self.filename, OG)
            self.generated_files = generated_files
            ensure_generated_files(generated_files, require_existing=True)

            print(f'Created OSW files!')

            del tasks
            del osm_graph_results
            del OG
            del generated_files
            resp = Response(
                status=True,
                generated_files=self.generated_files,
                warnings=warnings.to_string(),
            )
        except ConversionOutputError as error:
            print(error)
            resp = Response(
                status=False,
                generated_files=self.generated_files,
                error=str(error),
                warnings=warnings.to_string(),
            )
        except Exception as error:
            traceback.print_exc()
            print(error)
            resp = Response(
                status=False,
                generated_files=self.generated_files,
                error=str(error),
                warnings=warnings.to_string(),
            )
        finally:
            gc.collect()
        return resp
