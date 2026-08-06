import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, List, Optional, Union
from xml.etree import ElementTree as ET

from python_osw_validation import OSWValidation

from ..config import FormatterConfig
from .input_validation import DEFAULT_MAX_ISSUES, format_issues, validation_config


INVALID_OSW_OUTPUT_ERROR = "Generated OSW dataset is not valid."
NO_GENERATED_FILES_ERROR = "Conversion completed but no output files were generated."
EMPTY_OSM_XML_ERROR = (
    "Conversion completed but generated OSM XML contains no nodes, ways, or relations."
)


class ConversionOutputError(RuntimeError):
    pass


class OSWOutputValidationError(ConversionOutputError):
    """Raised when the generated OSW dataset fails validation.

    A subclass of `ConversionOutputError` so it travels the same path as the
    other output failures, but it carries the validator's per-feature `issues`.
    """

    def __init__(self, issues: Optional[Iterable[Any]] = None):
        self.issues: List[Any] = list(issues or [])
        self.messages: List[str] = format_issues(self.issues)
        details = "\n".join(f"- {line}" for line in self.messages)
        message = f"{INVALID_OSW_OUTPUT_ERROR}\n{details}" if details else INVALID_OSW_OUTPUT_ERROR
        super().__init__(message)


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


def validate_osw_output(
    generated_files: Optional[Union[str, List[str]]],
    config: Optional[FormatterConfig] = None,
) -> None:
    """Validate generated OSW files, raising ``OSWOutputValidationError`` when invalid.

    The validator reads a zip archive, so the generated files are bundled into a
    temporary one. It runs with the formatter's own settings, so output is judged
    by the rules it was produced with.

    Raises:
        OSWOutputValidationError: If the validator rejects the generated dataset.
    """
    files = [
        file_path for file_path in generated_files_as_list(generated_files)
        if Path(file_path).exists()
    ]
    if not files:
        return

    with tempfile.TemporaryDirectory() as workdir:
        zip_path = Path(workdir, "generated_osw.zip")
        with zipfile.ZipFile(zip_path, "w") as archive:
            for file_path in files:
                archive.write(file_path, Path(file_path).name)

        result = OSWValidation(
            zipfile_path=str(zip_path),
            config=validation_config(config),
        ).validate(max_errors=DEFAULT_MAX_ISSUES)

    if not result.is_valid:
        raise OSWOutputValidationError(
            result.issues
            or [{"error_message": message} for message in (result.errors or [])]
        )
