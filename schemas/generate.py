"""Regenerate every checked-in JSON Schema artifact in this directory.

Run from the repository root::

    python schemas/generate.py

Files are written with ``Path.write_text`` (a shell redirect would add a trailing newline).
The schemas are editor-facing only (``yaml-language-server``); no runtime code reads them and
they are not shipped in the wheel. The schema drift tests fail when an artifact is stale:
rerun this script and commit the diff.
"""

from pathlib import Path
from typing import List, Tuple, Type

from exegol.config.YamlConfigLoader import StrictYamlModel
from exegol.profile.ContainerProfile import ContainerProfile
from exegol.sentinel.SentinelProfile import SentinelConfig

SCHEMAS_DIR = Path(__file__).parent

# (root model, artifact filename)
SCHEMA_TARGETS: List[Tuple[Type[StrictYamlModel], str]] = [
    (ContainerProfile, "container-profile.schema.json"),
    (SentinelConfig, "sentinel.schema.json"),
]


def main() -> None:
    """Write every artifact declared in ``SCHEMA_TARGETS``."""
    for model, filename in SCHEMA_TARGETS:
        destination = SCHEMAS_DIR / filename
        destination.write_text(model.generate_json_schema(), encoding="utf-8")
        print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
