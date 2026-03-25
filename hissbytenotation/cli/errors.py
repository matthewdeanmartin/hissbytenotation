"""CLI error model and stable exit codes."""

from __future__ import annotations

SUCCESS = 0
FALSEY_RESULT = 1
PARSE_FAILURE = 2
UNSUPPORTED_FORMAT = 3
MISSING_VALUE = 4
TYPE_MISMATCH = 5
GLOM_FAILURE = 6
MERGE_CONFLICT = 7
FILE_IO_ERROR = 8
STRICT_CONVERSION_REFUSED = 9
EXTERNAL_TOOL_MISSING = 10
INTERNAL_ERROR = 11
VALIDATION_FAILURE = 12


class CliError(Exception):
    """Base class for CLI-facing failures."""

    exit_code = INTERNAL_ERROR

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class InputParseError(CliError):
    """Raised when input cannot be parsed."""

    exit_code = PARSE_FAILURE


class UnsupportedFormatError(CliError):
    """Raised when a format is unavailable or unsupported."""

    exit_code = UNSUPPORTED_FORMAT


class MissingValueError(CliError):
    """Raised when an expected value is missing."""

    exit_code = MISSING_VALUE


class OperationTypeError(CliError):
    """Raised when a command is used on an incompatible type."""

    exit_code = TYPE_MISMATCH


class FileIOCliError(CliError):
    """Raised for file IO errors."""

    exit_code = FILE_IO_ERROR


class StrictConversionError(CliError):
    """Raised when strict mode refuses a lossy conversion."""

    exit_code = STRICT_CONVERSION_REFUSED


class ExternalToolError(CliError):
    """Raised when an external formatter is unavailable."""

    exit_code = EXTERNAL_TOOL_MISSING


class GlomCliError(CliError):
    """Raised when glom is unavailable or a glom spec fails."""

    exit_code = GLOM_FAILURE


class MergeConflictError(CliError):
    """Raised when merge inputs conflict under the selected policy."""

    exit_code = MERGE_CONFLICT


class ValidationFailureError(CliError):
    """Raised when cerberus schema validation fails."""

    exit_code = VALIDATION_FAILURE
