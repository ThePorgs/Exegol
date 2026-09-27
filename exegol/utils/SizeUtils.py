"""Size-string helpers shared across the sentinel config surfaces.

One representation for every "max size" knob (log rotation ``max_size`` and
exec_command ``max_output``): a raw byte count, or a human string with a
binary-unit suffix ("100MB", "512KB", "2GB"). Everything is normalised to an
int number of bytes so the Pydantic schema, ``UserConfig`` and the emitted
``sentinel_config.json`` all speak the same unit — and the in-container scripts
never parse units.

Kept dependency-free (stdlib only) so both ``UserConfig`` and ``SentinelProfile``
can import it without an import cycle.
"""
import re
from typing import Union

# Splunk's product default for `TRUNCATE`, in bytes: an event longer than this is cut
# mid-line, which destroys the JSON rather than shortening it. The documented remedy is
# `TRUNCATE = 0` on the source type, but an operator who raises a limit has usually not
# touched their indexer yet -- so this is the number worth warning at, not an internal one.
#
# It lives here, next to the parser, for the same reason the parser does: both UserConfig and
# SentinelProfile need it, and SentinelProfile imports UserConfig, so the constant cannot live
# in either without a cycle.
SPLUNK_DEFAULT_TRUNCATE = 10_000

# Unit -> byte multiplier. Both the long ("MB" / "Mo") and short ("M") spellings are
# accepted, plus a bare number (empty suffix) meaning raw bytes. Powers of 1024.
_SIZE_UNITS = {
    "": 1, "B": 1, "O": 1,
    "K": 1024, "KB": 1024, "KO": 1024,
    "M": 1024 ** 2, "MB": 1024 ** 2, "MO": 1024 ** 2,
    "G": 1024 ** 3, "GB": 1024 ** 3, "GO": 1024 ** 3,
    "T": 1024 ** 4, "TB": 1024 ** 4, "TO": 1024 ** 4,
}
# number + optional unit suffix (one of K/M/G/T, each with an optional trailing B),
# or no suffix at all (bare bytes). Case-insensitive, surrounding space tolerated.
_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?[Bo]?)\s*$", re.IGNORECASE)


def parse_size_to_bytes(value: Union[int, float, str]) -> int:
    """Normalise a size to an integer number of bytes.

    Accepts:
      * an int/float byte count (returned truncated to int), or
      * a unit string, long or short spelling: "100MB"/"100M", "512KB"/"512K",
        "2GB"/"2G", "1TB"/"1T", "1024B" (case-insensitive; K/M/G/T are powers
        of 1024), or
      * a bare numeric string ("1048576") interpreted as bytes.

    Raises ``ValueError`` on anything else so Pydantic surfaces a validation error.
    """
    if isinstance(value, bool):
        raise ValueError("size must be a byte count or a unit string like '100MB', not a bool")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        m = _SIZE_RE.match(value)
        if not m:
            raise ValueError(
                f"invalid size {value!r}; use bytes (e.g. 1048576) or a unit string like '100MB', '2G'"
            )
        return int(float(m.group(1)) * _SIZE_UNITS[m.group(2).upper()])
    raise ValueError(f"invalid size type {type(value).__name__}; expected int bytes or a unit string like '100MB'")
