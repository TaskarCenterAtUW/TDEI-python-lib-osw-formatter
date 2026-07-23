from pathlib import Path
from typing import List, Optional, Union
from xml.etree import ElementTree as ET


NO_GENERATED_FILES_ERROR = "Conversion completed but no output files were generated."
EMPTY_OSM_XML_ERROR = (
    "Conversion completed but generated OSM XML contains no nodes, ways, or relations."
)


class ConversionOutputError(RuntimeError):
    pass


def generated_files_as_list(
    generated_files: Optional[Union[str, List[str]]],
) -> List[str]:
    if generated_files is None:
        return []
    if isinstance(generated_files, list):
        return [str(file_path) for file_path in generated_files if file_path]
    if generated_files:
        return [str(generated_files)]
    return []


def ensure_generated_files(
    generated_files: Optional[Union[str, List[str]]],
    require_existing: bool = False,
) -> None:
    files = generated_files_as_list(generated_files)
    if not files:
        raise ConversionOutputError(NO_GENERATED_FILES_ERROR)
    if require_existing and not any(Path(file_path).exists() for file_path in files):
        raise ConversionOutputError(NO_GENERATED_FILES_ERROR)


def osm_xml_has_entities(osm_xml_path: Path) -> bool:
    tree = ET.parse(osm_xml_path)
    root = tree.getroot()
    return any(root.findall(f".//{tag}") for tag in ("node", "way", "relation"))


def ensure_osm_xml_has_entities(osm_xml_path: Path) -> None:
    if not osm_xml_has_entities(osm_xml_path):
        raise ConversionOutputError(EMPTY_OSM_XML_ERROR)
