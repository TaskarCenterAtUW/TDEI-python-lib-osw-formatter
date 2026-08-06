import gc
import ogr2osm
from xml.etree import ElementTree as ET
from pathlib import Path
from ..config import FormatterConfig
from ..helpers.input_validation import InputValidationError, validate_osw_input
from ..helpers.osw import OSWHelper
from ..helpers.output_validation import (
    ConversionOutputError,
    ensure_generated_files,
    ensure_osm_xml_has_entities,
)
from ..helpers.response import Response
from ..serializer.osm.osm_normalizer import OSMNormalizer


class OSW2OSM:
    def __init__(self, zip_file_path: str, workdir: str, prefix: str, config: FormatterConfig = None):
        self.zip_path = str(Path(zip_file_path))
        self.workdir = workdir
        self.prefix = prefix
        if config is not None and not isinstance(config, FormatterConfig):
            raise TypeError("config must be a FormatterConfig instance.")
        self.config = config or FormatterConfig()

    def convert(self) -> Response:
        try:
            if self.config.validate_input:
                validate_osw_input(self.zip_path, config=self.config)
            unzipped_files = OSWHelper.unzip(self.zip_path, self.workdir)
            input_file = OSWHelper.merge(
                osm_files=unzipped_files,
                output=self.workdir,
                prefix=self.prefix,
                config=self.config,
            )
            output_file = Path(self.workdir, f'{self.prefix}.graph.osm.xml')

            # Create the translation object.
            translation_object = OSMNormalizer(config=self.config)

            # Create the ogr datasource
            datasource = ogr2osm.OgrDatasource(translation_object)
            datasource.open_datasource(input_file)

            # Instantiate the ogr to osm converter class ogr2osm. OsmData and start the conversion process
            osm_data = ogr2osm.OsmData(translation_object)
            osm_data.process(datasource)

            # Instantiate either ogr2osm.OsmDataWriter or ogr2osm.PbfDataWriter
            data_writer = ogr2osm.OsmDataWriter(output_file, suppress_empty_tags=True)
            osm_data.output(data_writer)
            self._restore_zero_length_way_refs(output_file)
            self._ensure_version_attribute(output_file)
            self._remap_ids_to_sequential(output_file)
            ensure_generated_files(str(output_file), require_existing=True)
            ensure_osm_xml_has_entities(output_file)

            del translation_object
            del datasource
            del osm_data
            del data_writer
            # Delete merge file
            Path(input_file).unlink()
            resp = Response(
                status=True,
                generated_files=str(output_file),
            )
        except InputValidationError as error:
            print(f'Invalid OSW input: {error}')
            resp = Response(status=False, error=str(error))
        except ConversionOutputError as error:
            print(f'Error during conversion: {error}')
            resp = Response(status=False, error=str(error))
        except Exception as error:
            print(f'Error during conversion: {error}')
            resp = Response(status=False, error=str(error))
        finally:
            gc.collect()
        return resp

    @staticmethod
    def _restore_zero_length_way_refs(osm_xml_path: Path) -> None:
        """Re-add the node reference ogr2osm drops from a zero-length way.

        A zero-length OSW edge has both endpoints at the same node, so ogr2osm's
        linestring parser skips the second vertex as a consecutive duplicate and
        emits a way with one node, which is not valid OSM. Such an edge is meant
        to survive as ``w = [n, n]``. A single-node way has no other source, so
        any that appears here is this case.
        """
        try:
            tree = ET.parse(osm_xml_path)
        except Exception:
            return

        root = tree.getroot()
        restored = False
        for way in root.findall('.//way'):
            refs = way.findall('nd')
            if len(refs) != 1:
                continue
            duplicate = ET.Element('nd', {'ref': refs[0].get('ref')})
            way.insert(list(way).index(refs[0]) + 1, duplicate)
            restored = True

        if restored:
            tree.write(osm_xml_path, encoding='utf-8', xml_declaration=True)

    @staticmethod
    def _ensure_version_attribute(osm_xml_path: Path) -> None:
        """Ensure nodes, ways, and relations include a version attribute."""
        try:
            tree = ET.parse(osm_xml_path)
        except Exception:
            return

        root = tree.getroot()
        for tag in ('node', 'way', 'relation'):
            for element in root.findall(f'.//{tag}'):
                if not element.get('version'):
                    element.set('version', '1')

        tree.write(osm_xml_path, encoding='utf-8', xml_declaration=True)

    @staticmethod
    def _remap_ids_to_sequential(osm_xml_path: Path) -> None:
        """Remap node/way/relation IDs to sequential values starting at 1 and update references."""
        try:
            tree = ET.parse(osm_xml_path)
        except Exception:
            return

        root = tree.getroot()

        def remap_elements(xpath: str):
            mapping = {}
            elems = root.findall(xpath)
            for idx, elem in enumerate(elems, start=1):
                old_id = elem.get('id')
                if old_id is None:
                    continue
                mapping[old_id] = str(idx)
                elem.set('id', str(idx))
                for tag in elem.findall("./tag[@k='_id']"):
                    tag.set('v', str(idx))
            return mapping

        node_map = remap_elements('.//node')
        way_map = remap_elements('.//way')
        rel_map = remap_elements('.//relation')

        # Update way nd refs
        for way in root.findall('.//way'):
            for nd in way.findall('nd'):
                ref = nd.get('ref')
                if ref in node_map:
                    nd.set('ref', node_map[ref])

        # Update relation member refs
        for rel in root.findall('.//relation'):
            for member in rel.findall('member'):
                ref = member.get('ref')
                m_type = member.get('type')
                if m_type == 'node' and ref in node_map:
                    member.set('ref', node_map[ref])
                elif m_type == 'way' and ref in way_map:
                    member.set('ref', way_map[ref])
                elif m_type == 'relation' and ref in rel_map:
                    member.set('ref', rel_map[ref])

        tree.write(osm_xml_path, encoding='utf-8', xml_declaration=True)
