"""Validation of OSW and OSM input datasets before they are converted."""

import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from xml.etree import ElementTree as ET

import osmium
from python_osw_validation import OSWValidation
from python_osw_validation.config import ValidationConfig

from ..config import DEFAULT_COORDINATE_PRECISION, FormatterConfig


DEFAULT_MAX_ISSUES = 20
INVALID_OSW_INPUT_ERROR = 'Input is not a valid OSW dataset.'
UNKNOWN_VALIDATION_ERROR = 'The OSW validator reported the dataset as invalid.'
OSM_COORDINATE_PRECISION_ERROR_TEMPLATE = (
    "invalid input file, the file has GPS locations with higher than "
    "{coordinate_precision}-digits precision that TDEI doesn't allow. "
    "Please clean your dataset and resubmit"
)
# Every offending node is collected so the message can name what to fix, but
# only this many are spelled out before the rest are summarised as a count.
OSM_PRECISION_OFFENDERS_SHOWN = 20
OSM_COORDINATE_PRECISION_NODE_TEMPLATE = (
    "node {id} at lat={lat}, lon={lon} has {decimals} decimal places"
)
OSM_COORDINATE_PRECISION_MORE_TEMPLATE = (
    "...and {count} more node(s) with the same problem"
)
OSM_CORRUPT_FILE_ERROR = (
    "invalid input file, the OSM file is corrupted and could not be read. "
    "Please fix the file and resubmit"
)
OSM_CORRUPT_FILE_AT_ERROR_TEMPLATE = (
    "invalid input file, the OSM file is corrupted and could not be read. "
    "The problem is at line {line}, column {column}. "
    "Please fix the file and resubmit"
)
# Parser messages differ between the XML reader and osmium, but both spell the
# position the same way. Everything else in them is jargon, so only this is kept.
_PARSE_LOCATION_PATTERN = re.compile(r'line (\d+), column (\d+)')
# osmium reports many kinds of RuntimeError, most of which are complaints about
# the data rather than the file being unreadable. Only these mean it could not
# be parsed; anything else must keep its own message.
_PARSE_FAILURE_PATTERN = re.compile(
    r'not well-formed|parsing error|premature end|unexpected end|'
    r'invalid file|unknown file format|cannot open',
    re.IGNORECASE,
)
OSW_FILE_MISSING_ERROR = (
    "invalid input file, the OSW dataset '{name}' could not be found. "
    "Please check the file and resubmit"
)
OSW_FILE_NOT_A_ZIP_ERROR = (
    "invalid input file, '{name}' is not a valid zip archive. "
    "Please fix the file and resubmit"
)
OSW_FILE_NO_DATASETS_ERROR = (
    "invalid input file, the OSW dataset '{name}' contains no .geojson files. "
    "Please check the file and resubmit"
)

# Resolution of the integer coordinates osmium exposes, which the PBF scan
# divides against. `osmium.osm.Location` holds int32 in units of 1e-7 degrees,
# so a PBF cannot report more decimals than this whatever granularity the file
# declares -- more precise coordinates are quantized on read, not rejected.
OSMIUM_LOCATION_PRECISION = DEFAULT_COORDINATE_PRECISION


class InputValidationError(ValueError):
    """Raised when the input OSW dataset fails validation.

    The validator reports per-feature `issues`, each naming the file and feature
    it came from. They are kept intact on `issues` and rendered into the message.
    """

    def __init__(self, issues: Optional[Iterable[Any]] = None):
        self.issues: List[Any] = list(issues or [])
        self.messages: List[str] = format_issues(self.issues)
        super().__init__(format_validation_error(self.issues))


class OSWFileUnreadableError(InputValidationError):
    """Raised when the OSW archive cannot be opened at all.

    A subclass of `InputValidationError` so callers can catch either, but it
    carries a single plain-language message rather than per-feature issues:
    there is nothing inside the file to point at yet.
    """

    def __init__(self, message: str):
        self.issues = []
        self.messages = [message]
        ValueError.__init__(self, message)


class OSMCoordinatePrecisionError(ValueError):
    """Raised when an OSM input file carries coordinates that are too precise.

    Every offending node is kept on `offenders`, each a dict of `id`, `lat`,
    `lon`, and `decimals`. The message names them so the file can be corrected
    without hunting for which node is at fault.
    """

    def __init__(self, coordinate_precision: int, offenders: Optional[Iterable[Any]] = None):
        self.coordinate_precision = coordinate_precision
        self.offenders: List[Dict[str, Any]] = list(offenders or [])
        self.messages: List[str] = format_precision_offenders(self.offenders)
        self.issues: List[Dict[str, Any]] = [
            {
                'filename': None,
                'feature_index': None,
                'error_message': [message],
            }
            for message in self.messages
        ]
        summary = OSM_COORDINATE_PRECISION_ERROR_TEMPLATE.format(
            coordinate_precision=coordinate_precision,
        )
        details = '\n'.join(f'- {line}' for line in self.messages)
        super().__init__(f'{summary}\n{details}' if details else summary)


def format_precision_offenders(offenders: Optional[Iterable[Any]]) -> List[str]:
    """Render offending nodes as readable lines, capped with a remainder."""
    offenders = list(offenders or [])
    lines = [
        OSM_COORDINATE_PRECISION_NODE_TEMPLATE.format(
            id=offender.get('id'),
            lat=offender.get('lat'),
            lon=offender.get('lon'),
            decimals=offender.get('decimals'),
        )
        for offender in offenders[:OSM_PRECISION_OFFENDERS_SHOWN]
    ]
    remainder = len(offenders) - len(lines)
    if remainder > 0:
        lines.append(OSM_COORDINATE_PRECISION_MORE_TEMPLATE.format(count=remainder))
    return lines


class OSMFileCorruptError(ValueError):
    """Raised when an OSM input file cannot be parsed at all.

    The underlying parser message is kept on `detail` for logging, but it is
    never shown to the user: only the position it reports is worth reading.
    """

    def __init__(self, detail: str = ''):
        self.detail = detail
        match = _PARSE_LOCATION_PATTERN.search(detail or '')
        if match:
            self.line, self.column = (int(group) for group in match.groups())
            message = OSM_CORRUPT_FILE_AT_ERROR_TEMPLATE.format(
                line=self.line,
                column=self.column,
            )
        else:
            self.line = self.column = None
            message = OSM_CORRUPT_FILE_ERROR
        super().__init__(message)


class _PbfPrecisionHandler(osmium.SimpleHandler):
    """Collect PBF nodes whose coordinates carry more decimals than allowed.

    osmium exposes coordinates as integers in units of 1e-7 degrees, so a
    coordinate fits `precision` decimals exactly when that integer divides by
    10 ** (OSMIUM_LOCATION_PRECISION - precision).
    """

    def __init__(self, coordinate_precision: int):
        osmium.SimpleHandler.__init__(self)
        self.coordinate_precision = coordinate_precision
        self.divisor = 10 ** (OSMIUM_LOCATION_PRECISION - coordinate_precision)
        self.offenders: List[Dict[str, Any]] = []

    @property
    def exceeds_precision(self) -> bool:
        return bool(self.offenders)

    def node(self, n) -> None:
        if not n.location.valid():
            return
        if n.location.x % self.divisor or n.location.y % self.divisor:
            latitude = format(n.location.lat, 'f').rstrip('0')
            longitude = format(n.location.lon, 'f').rstrip('0')
            self.offenders.append({
                'id': n.id,
                'lat': latitude,
                'lon': longitude,
                'decimals': max(_decimal_places(latitude), _decimal_places(longitude)),
            })


def is_osm_parse_failure(message: str) -> bool:
    """Whether a reader error means the file could not be parsed at all."""
    return bool(_PARSE_FAILURE_PATTERN.search(str(message or '')))


def _decimal_places(value: str) -> int:
    try:
        exponent = Decimal(value).as_tuple().exponent
    except (InvalidOperation, TypeError, ValueError):
        return 0
    return max(0, -exponent) if isinstance(exponent, int) else 0


def osm_xml_precision_offenders(file_path: str, coordinate_precision: int) -> List[Dict[str, Any]]:
    """Every XML node whose coordinates carry more decimals than allowed."""
    offenders: List[Dict[str, Any]] = []
    try:
        for _event, element in ET.iterparse(file_path, events=('end',)):
            if element.tag != 'node':
                element.clear()
                continue
            latitude = element.get('lat')
            longitude = element.get('lon')
            decimals = max(_decimal_places(latitude), _decimal_places(longitude))
            if decimals > coordinate_precision:
                offenders.append({
                    'id': element.get('id'),
                    'lat': latitude,
                    'lon': longitude,
                    'decimals': decimals,
                })
            element.clear()
    except ET.ParseError as error:
        raise OSMFileCorruptError(str(error)) from error
    return offenders


def osm_pbf_precision_offenders(file_path: str, coordinate_precision: int) -> List[Dict[str, Any]]:
    """Every PBF node whose coordinates carry more decimals than allowed."""
    # Nothing osmium reads can exceed its own 1e-7 resolution, so at or above
    # that precision the scan can only ever pass.
    if coordinate_precision >= OSMIUM_LOCATION_PRECISION:
        return []
    handler = _PbfPrecisionHandler(coordinate_precision)
    try:
        handler.apply_file(file_path)
    except RuntimeError as error:
        raise OSMFileCorruptError(str(error)) from error
    return handler.offenders


def osm_precision_offenders(file_path: str, coordinate_precision: int) -> List[Dict[str, Any]]:
    """Every node coordinate carrying more decimals than allowed."""
    if Path(file_path).suffix.lower() == '.pbf':
        return osm_pbf_precision_offenders(file_path, coordinate_precision)
    return osm_xml_precision_offenders(file_path, coordinate_precision)


def osm_xml_exceeds_coordinate_precision(file_path: str, coordinate_precision: int) -> bool:
    return bool(osm_xml_precision_offenders(file_path, coordinate_precision))


def osm_pbf_exceeds_coordinate_precision(file_path: str, coordinate_precision: int) -> bool:
    return bool(osm_pbf_precision_offenders(file_path, coordinate_precision))


def osm_exceeds_coordinate_precision(file_path: str, coordinate_precision: int) -> bool:
    """Return whether any node coordinate carries more decimals than allowed."""
    return bool(osm_precision_offenders(file_path, coordinate_precision))


def validate_osm_input(file_path: str, config: Optional[FormatterConfig] = None) -> None:
    """Reject OSM input whose coordinates exceed the configured precision.

    Args:
        file_path: Path to the OSM `.xml`, `.osm`, or `.pbf` file.
        config: Formatter settings supplying `coordinate_precision`.

    Raises:
        OSMFileCorruptError: If the file cannot be parsed.
        OSMCoordinatePrecisionError: If any node coordinate is too precise.
    """
    config = config or FormatterConfig()
    offenders = osm_precision_offenders(str(file_path), config.coordinate_precision)
    if offenders:
        raise OSMCoordinatePrecisionError(config.coordinate_precision, offenders)


def _issue_messages(issue: Any) -> List[str]:
    """Return the message(s) an issue carries, whatever shape it arrived in."""
    if not isinstance(issue, dict):
        return [str(issue)] if issue else []

    message = issue.get('error_message')
    if isinstance(message, (list, tuple, set)):
        return [str(entry) for entry in message if entry]
    return [str(message)] if message else []


def _issue_location(issue: Dict[str, Any]) -> str:
    filename = issue.get('filename')
    feature_index = issue.get('feature_index')
    if filename and feature_index is not None:
        return f'{filename} (feature {feature_index})'
    if filename:
        return str(filename)
    if feature_index is not None:
        return f'feature {feature_index}'
    return ''


def format_issues(issues: Optional[Iterable[Any]]) -> List[str]:
    """Render validator issues as unique, human-readable lines."""
    lines: List[str] = []
    for issue in issues or []:
        location = _issue_location(issue) if isinstance(issue, dict) else ''
        for message in _issue_messages(issue):
            line = f'{location}: {message}' if location else message
            if line not in lines:
                lines.append(line)
    return lines


def format_validation_error(issues: Optional[Iterable[Any]]) -> str:
    lines = format_issues(issues)
    if not lines:
        return f'{INVALID_OSW_INPUT_ERROR} {UNKNOWN_VALIDATION_ERROR}'
    details = '\n'.join(f'- {line}' for line in lines)
    return f'{INVALID_OSW_INPUT_ERROR}\n{details}'


def validation_config(config: Optional[FormatterConfig] = None) -> ValidationConfig:
    """Translate formatter settings into the matching validator settings."""
    config = config or FormatterConfig()
    return ValidationConfig(
        coordinate_precision=config.coordinate_precision,
        allow_zero_length_lines=config.allow_zero_length_lines,
        max_geometry_vertices=config.max_geometry_vertices,
    )


def _ensure_osw_archive_readable(zip_file_path: str) -> None:
    """Report archive-level problems in plain language.

    The validator surfaces these as raw parser and OS errors, and names the file
    by its full path. Only the file name is echoed back.
    """
    path = Path(zip_file_path)
    if not path.is_file():
        raise OSWFileUnreadableError(OSW_FILE_MISSING_ERROR.format(name=path.name))
    if not zipfile.is_zipfile(path):
        raise OSWFileUnreadableError(OSW_FILE_NOT_A_ZIP_ERROR.format(name=path.name))

    with zipfile.ZipFile(path) as archive:
        entries = [
            name for name in archive.namelist()
            if name.lower().endswith('.geojson') and '__MACOSX' not in name
        ]
    if not entries:
        raise OSWFileUnreadableError(OSW_FILE_NO_DATASETS_ERROR.format(name=path.name))


def validate_osw_input(
    zip_file_path: str,
    config: Optional[FormatterConfig] = None,
    max_issues: int = DEFAULT_MAX_ISSUES,
) -> None:
    """Validate an OSW zip archive, raising ``InputValidationError`` when invalid.

    Args:
        zip_file_path: Path to the OSW dataset archive.
        config: Formatter settings; `coordinate_precision` and
            `allow_zero_length_lines` are applied to the validator so the input
            is judged by the same rules the formatter converts with.
        max_issues: Maximum number of validator issues reported back to the caller.

    Raises:
        InputValidationError: If the validator rejects the dataset, or fails to run.
    """
    _ensure_osw_archive_readable(zip_file_path)
    try:
        validation = OSWValidation(
            zipfile_path=str(zip_file_path),
            config=validation_config(config),
        )
        result = validation.validate(max_errors=max_issues)
    except InputValidationError:
        raise
    except Exception as error:
        raise InputValidationError([{'error_message': str(error)}]) from error

    if not result.is_valid:
        # `issues` name the file and feature each problem came from; `errors` is
        # the flatter legacy list and only stands in when no issue was recorded.
        raise InputValidationError(
            result.issues
            or [{'error_message': message} for message in (result.errors or [])]
        )
