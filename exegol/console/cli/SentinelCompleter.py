"""Tab completion for Sentinel profile names (``-SP`` / ``--sentinel-profile`` and ``exegol info -S``).

Kept apart from ``ExegolCompleter``, which must import no ``yaml``
(``tests/profile/test_discovery.py``): Sentinel profile names are keys inside each
document's ``profiles:`` block, not file stems, so they can only be learned by parsing.
Candidate spelling is shared with ``ExegolCompleter`` via ``profileCompletionCandidates``.
"""
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.config.OptionResolver import OptionKey, OptionResolver
from exegol.console.cli.ExegolCompleter import profileCompletionCandidates


# Sources are often full git clones: skip YAML files too large to be a profile rather than
# stall the shell parsing them on a tab press. Real profile files are a few KB.
_SENTINEL_COMPLETER_MAX_YAML_BYTES = 1_048_576


def _declaredSentinelProfileNames(yaml_file: Path) -> Tuple[str, ...]:
    """Return the names declared in ``yaml_file``'s top-level ``profiles:`` block.

    Plain ``yaml.safe_load``, not ``load_yaml_file``: no validation or logging on a tab press.
    Any failure (unreadable, non-UTF-8, invalid YAML, non-mapping root) returns ``()``.
    """
    try:
        if yaml_file.stat().st_size > _SENTINEL_COMPLETER_MAX_YAML_BYTES:
            return ()
        with yaml_file.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
    except Exception:
        # Intentionally broad: a completer has no error channel.
        return ()
    if not isinstance(document, dict):
        return ()
    # Subscript rather than `.get`, so the structural guard looking for `get` calls in
    # completers is not confused by a dict's `.get`.
    profiles = document["profiles"] if "profiles" in document else None
    if not isinstance(profiles, dict):
        return ()
    return tuple(str(name) for name in profiles)


def SentinelProfileCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Complete Sentinel profile names for ``-SP`` / ``--sentinel-profile`` and ``exegol info -S``.

    Each profile is offered as ``source.name``, and bare when no other source uses that name
    (same rule as ``ProfileCompleter``). Sources mirror
    ``SentinelProfileManager.__enumerate_roots()``: implicit ``core`` plus every
    ``sentinel.sources`` entry (its ``path:``, else ``component_path / key``).

    Uses ``defaultFor`` since the parser is still being built. Not licence-gated: the licence
    session is not settled at parser-build time.
    """
    component_path = Path(OptionResolver().defaultFor(OptionKey.SENTINEL_PROFILE_PATH))
    declared_sources: Dict[str, Any] = OptionResolver().defaultFor(OptionKey.SENTINEL_SOURCES) or {}

    # `core` is not a `sentinel.sources` entry but is always loaded when present.
    roots: Dict[str, Path] = {}
    core_root = component_path / ConstantConfig.SENTINEL_CORE_SOURCE_KEY
    if core_root.is_dir():
        roots[ConstantConfig.SENTINEL_CORE_SOURCE_KEY] = core_root
    for source_key, spec in declared_sources.items():
        if not isinstance(spec, dict):
            continue
        local_path = spec["path"] if "path" in spec else None
        roots[source_key] = EnvInfo.expand_user(local_path) if local_path else component_path / source_key

    discovered: List[Tuple[str, str]] = []
    for source_key, source_dir in roots.items():
        # A missing root is normal (e.g. a `git:` source not yet fetched by `exegol update`).
        if not source_dir.is_dir():
            continue
        seen_files = set()
        for pattern in ("**/*.yml", "**/*.yaml"):
            for yaml_file in source_dir.glob(pattern):
                # Skip dot-directories (e.g. `.github/`), as __scan_source_root does.
                if any(part.startswith(".") for part in yaml_file.relative_to(source_dir).parts):
                    continue
                if yaml_file in seen_files:
                    continue
                seen_files.add(yaml_file)
                for profile_name in _declaredSentinelProfileNames(yaml_file):
                    discovered.append((source_key, profile_name))

    return profileCompletionCandidates(discovered, prefix.lower() if prefix else "")
