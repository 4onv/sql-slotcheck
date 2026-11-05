"""Bounds and scalar validation shared by capture readers."""

import math


class CaptureError(ValueError):
    """The input cannot be interpreted as a version-1 positional capture."""


MAX_COLUMNS = 128
MAX_ROWS = 256
MAX_STRING = 4096
MAX_TEXT_PER_RESULT = 1_048_576
MAX_INTEGER_BITS = 4096
TYPE_NAMES = {str: "string", int: "integer", float: "number", bool: "boolean", type(None): "null"}


def _count_text(value, used, location):
    length = len(value)
    if length > MAX_STRING:
        raise CaptureError(f"{location} exceeds {MAX_STRING} characters.")
    total = used + length
    if total > MAX_TEXT_PER_RESULT:
        raise CaptureError(f"{location} exceeds the {MAX_TEXT_PER_RESULT}-character result limit.")
    return total


def check_label(value, used, location):
    if not isinstance(value, str):
        raise CaptureError(f"{location} requires a string column label.")
    return _count_text(value, used, location)


def check_cell(value, used, location):
    kind = type(value)
    if kind not in TYPE_NAMES:
        raise CaptureError(f"{location} must be a JSON scalar.")
    if kind is str:
        return _count_text(value, used, location)
    if kind is float and not math.isfinite(value):
        raise CaptureError(f"{location} must be finite.")
    if kind is int and value.bit_length() > MAX_INTEGER_BITS:
        raise CaptureError(f"{location} exceeds the {MAX_INTEGER_BITS}-bit integer limit.")
    return used
