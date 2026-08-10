from dataclasses import dataclass


DEFAULT_COORDINATE_PRECISION = 7
DEFAULT_MAX_GEOMETRY_VERTICES = 2000
DEFAULT_ALLOW_ZERO_LENGTH_LINES = True
DEFAULT_VALIDATE_INPUT = True
DEFAULT_VALIDATE_OUTPUT = True


@dataclass(frozen=True)
class FormatterConfig:
    """User-configurable formatter behavior."""

    coordinate_precision: int = DEFAULT_COORDINATE_PRECISION
    max_geometry_vertices: int = DEFAULT_MAX_GEOMETRY_VERTICES
    allow_zero_length_lines: bool = DEFAULT_ALLOW_ZERO_LENGTH_LINES
    validate_input: bool = DEFAULT_VALIDATE_INPUT
    validate_output: bool = DEFAULT_VALIDATE_OUTPUT

    def __post_init__(self) -> None:
        if isinstance(self.coordinate_precision, bool) or not isinstance(
            self.coordinate_precision, int
        ):
            raise TypeError("coordinate_precision must be an integer.")
        if self.coordinate_precision < 0:
            raise ValueError("coordinate_precision must be zero or greater.")
        if isinstance(self.max_geometry_vertices, bool) or not isinstance(
            self.max_geometry_vertices, int
        ):
            raise TypeError("max_geometry_vertices must be an integer.")
        if self.max_geometry_vertices <= 0:
            raise ValueError("max_geometry_vertices must be greater than zero.")
        if not isinstance(self.allow_zero_length_lines, bool):
            raise TypeError("allow_zero_length_lines must be a boolean.")
        if not isinstance(self.validate_input, bool):
            raise TypeError("validate_input must be a boolean.")
        if not isinstance(self.validate_output, bool):
            raise TypeError("validate_output must be a boolean.")
