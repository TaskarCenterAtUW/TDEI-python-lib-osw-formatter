import os
from pathlib import Path
from .osm2osw.osm2osw import OSM2OSW
from .osw2osm.osw2osm import OSW2OSM
from .osw2osm.osw2osm_new import OSW2OSMNew
from .helpers.response import Response
from .version import __version__

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
# Path used for generation the files.
DOWNLOAD_FOLDER = f'{Path.cwd()}/tmp'


class Formatter:
    def __init__(self, workdir=DOWNLOAD_FOLDER, file_path=None, prefix='final'):
        is_exists = os.path.exists(workdir)
        if not is_exists:
            os.makedirs(workdir)
        self.workdir = workdir
        self.file_path = file_path
        self.generated_files = []
        self.prefix = prefix

    async def osm2osw(self) -> Response:
        convert = OSM2OSW(osm_file=self.file_path, workdir=self.workdir, prefix=self.prefix)
        result = await convert.convert()
        self.generated_files = result.generated_files
        return result

    def osw2osm(self) -> Response:
        convert = OSW2OSMNew(zip_file_path=self.file_path, workdir=self.workdir, prefix=self.prefix)
        result = convert.convert()
        self.generated_files = [result.generated_files]
        return result

    def cleanup(self) -> None:
        for file in self.generated_files:
            if os.path.exists(file):
                os.remove(file)
