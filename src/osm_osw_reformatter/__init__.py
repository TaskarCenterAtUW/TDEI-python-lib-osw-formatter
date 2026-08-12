import os
from pathlib import Path
from .osm2osw.osm2osw import OSM2OSW
from .osw2osm.osw2osm import OSW2OSM
from .config import (
    DEFAULT_ALLOW_ZERO_LENGTH_LINES,
    DEFAULT_COORDINATE_PRECISION,
    DEFAULT_MAX_GEOMETRY_VERTICES,
    DEFAULT_VALIDATE_INPUT,
    DEFAULT_VALIDATE_OUTPUT,
    FormatterConfig,
)
from .helpers.response import Response
from .version import __version__

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
# Path used for generation the files.
DOWNLOAD_FOLDER = f'{Path.cwd()}/tmp'


class Formatter:
    def __init__(
        self,
        workdir=DOWNLOAD_FOLDER,
        file_path=None,
        prefix='final',
        config: FormatterConfig = None,
        coordinate_precision: int = None,
        max_geometry_vertices: int = None,
        allow_zero_length_lines: bool = None,
        validate_input: bool = None,
        validate_output: bool = None,
    ):
        is_exists = os.path.exists(workdir)
        if not is_exists:
            os.makedirs(workdir)
        if config is not None and not isinstance(config, FormatterConfig):
            raise TypeError("config must be a FormatterConfig instance.")
        if config is None:
            config = FormatterConfig(
                coordinate_precision=(
                    DEFAULT_COORDINATE_PRECISION
                    if coordinate_precision is None
                    else coordinate_precision
                ),
                max_geometry_vertices=(
                    DEFAULT_MAX_GEOMETRY_VERTICES
                    if max_geometry_vertices is None
                    else max_geometry_vertices
                ),
                allow_zero_length_lines=(
                    DEFAULT_ALLOW_ZERO_LENGTH_LINES
                    if allow_zero_length_lines is None
                    else allow_zero_length_lines
                ),
                validate_input=(
                    DEFAULT_VALIDATE_INPUT
                    if validate_input is None
                    else validate_input
                ),
                validate_output=(
                    DEFAULT_VALIDATE_OUTPUT
                    if validate_output is None
                    else validate_output
                ),
            )
        self.workdir = workdir
        self.file_path = file_path
        self.generated_files = []
        self.prefix = prefix
        self.config = config

    async def osm2osw(self) -> Response:
        convert = OSM2OSW(
            osm_file=self.file_path,
            workdir=self.workdir,
            prefix=self.prefix,
            config=self.config,
        )
        result = await convert.convert()
        self.generated_files = result.generated_files
        return result

    def osw2osm(self) -> Response:
        convert = OSW2OSM(
            zip_file_path=self.file_path,
            workdir=self.workdir,
            prefix=self.prefix,
            config=self.config,
        )
        result = convert.convert()
        self.generated_files = [result.generated_files]
        return result

    def cleanup(self) -> None:
        for file in self.generated_files:
            if os.path.exists(file):
                os.remove(file)
