from dataclasses import dataclass


DEFAULT_COORDINATE_PRECISION = 7
DEFAULT_ALLOW_ZERO_LENGTH_LINES = False


@dataclass(frozen=True)
class FormatterConfig:
    """User-configurable formatter behavior."""

    coordinate_precision: int = DEFAULT_COORDINATE_PRECISION
    allow_zero_length_lines: bool = DEFAULT_ALLOW_ZERO_LENGTH_LINES

    def __post_init__(self) -> None:
        if isinstance(self.coordinate_precision, bool) or not isinstance(
            self.coordinate_precision, int
        ):
            raise TypeError("coordinate_precision must be an integer.")
        if self.coordinate_precision < 0:
            raise ValueError("coordinate_precision must be zero or greater.")
        if not isinstance(self.allow_zero_length_lines, bool):
            raise TypeError("allow_zero_length_lines must be a boolean.")
