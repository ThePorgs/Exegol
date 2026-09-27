"""Builds the resolver's profile-UserConfig tier from a profile's ``PROFILE_USER_CONFIG_MAP`` settings.

Turns the ``config.yml`` settings a profile may override into the ``{OptionKey: value}``
mapping ``OptionResolver.loadProfileUserConfig()`` installs, with the same coercion and
validation a ``config.yml`` value gets. This lives outside the resolver because it logs,
validates and may exit, which the resolver must never do (it would break ``--help`` and
completion).

Runs eagerly, once, at profile application: the host-path refusals are only enforcement if
they run whether or not the field is later read. No singleton is mutated.

Never import this module at module level from ``OptionResolver``, ``UserConfig`` or
``ParametersManager`` (circular import).
"""

from pathlib import Path
from typing import Any, Dict, List

from rich.markup import escape

from exegol.config.EnvInfo import EnvInfo
from exegol.config.OptionResolver import OptionKey, _REGISTRY
from exegol.config.UserConfig import UserConfig
from exegol.profile.ContainerProfile import ContainerProfile
from exegol.profile.ProfileApplication import flatten_profile_user_config_overrides
from exegol.profile.ProfileFieldMap import PROFILE_USER_CONFIG_MAP
from exegol.utils.ExeLog import logger
from exegol.utils.NetworkUtils import NetworkUtils
from exegol.utils.SessionHandler import SessionHandler


def _attribute_for(dotted: str) -> str:
    """The ``UserConfig`` attribute declared by ``dotted``'s option (``OptionSpec.user_config_attr``)."""
    option_key = PROFILE_USER_CONFIG_MAP[dotted]
    attribute = _REGISTRY[option_key].user_config_attr
    assert attribute is not None, (
        f"PROFILE_USER_CONFIG_MAP maps {dotted!r} to {option_key!r}, whose registry entry "
        "declares no user_config_attr, there is no attribute to read the fallback from."
    )
    return attribute


def _current(config: UserConfig, dotted: str) -> Any:
    """The already-loaded ``config.yml`` value for ``dotted``.

    A direct tier read, not ``get()``: the resolver would consult the tier being built.
    """
    return getattr(config, _attribute_for(dotted))


def _resolve_host_path(config: UserConfig, dotted: str, raw: Any, config_name: str, current: Path) -> Path:
    """Resolve a profile-declared host path, refusing destructive targets.

    These paths are mounted read-write and may get a recursive setgid chmod, so a profile
    value is untrusted: it must be absolute, not the filesystem root, not the invoking user's
    home or the process home (root's under sudo), nor an ancestor of either. A refusal is
    CRITICAL (exits) and still returns ``current`` as a fail-safe.
    """
    candidate = config._load_config_path({config_name: raw}, config_name, current)
    if candidate == current:
        # Declared null or unchanged value: nothing to guard.
        return candidate
    if not candidate.is_absolute():
        # A relative path would depend on the working directory, like the excluded `-cwd`.
        logger.critical(f"Profile field '{escape(dotted)}' must be an absolute path (or start with '~'), "
                        f"got {escape(str(raw))}: a relative path would mount whichever host tree exegol "
                        f"happened to be launched from.")
        return current
    if candidate.parent == candidate:
        logger.critical(f"Profile field '{escape(dotted)}' refuses the filesystem root {escape(str(candidate))}.")
        return current
    # Under sudo the process home is root's, so the invoking user's home needs its own check
    homes: List[Path] = []
    try:
        homes.append(EnvInfo.get_user_home())
    except RuntimeError:  # pragma: no cover - unresolvable home directory
        pass
    try:
        homes.append(Path.home())
    except RuntimeError:  # pragma: no cover - unresolvable home directory
        pass
    if any(candidate == home or candidate in home.parents for home in homes):
        logger.critical(f"Profile field '{escape(dotted)}' refuses {escape(str(candidate))}: exegol mounts this "
                        f"path read-write into the container and may apply a recursive g+rws chmod to it.")
        return current
    # Verbose like every profile announcement: the control is the refusals above, not this log level.
    logger.verbose(f"Profile overrides a host path: [blue]{escape(dotted)}[/blue] -> "
                   f"[magenta]{escape(str(candidate))}[/magenta] (mounted read-write into the container).")
    return candidate


def _build_volume_overrides(config: UserConfig, declared: Dict[str, Any]) -> Dict[str, Any]:
    """Mirrors ``_process_data()``'s volume section; returns ``{dotted: value}`` for applied paths."""
    applied: Dict[str, Any] = {}
    dotted = "customization.my_resources_path"
    if dotted in declared:
        applied[dotted] = _resolve_host_path(config, dotted, declared[dotted],
                                             "my_resources_path", _current(config, dotted))
    dotted = "volumes.exegol_resources_path"
    if dotted in declared:
        applied[dotted] = _resolve_host_path(config, dotted, declared[dotted],
                                             "exegol_resources_path", _current(config, dotted))
    dotted = "volumes.private_workspace_path"
    if dotted in declared:
        # The attribute is `private_volume_path`, but the config.yml key is 'private_workspace_path'.
        applied[dotted] = _resolve_host_path(config, dotted, declared[dotted],
                                             "private_workspace_path", _current(config, dotted))
    return applied


def _build_sentinel_overrides(config: UserConfig, declared: Dict[str, Any]) -> Dict[str, Any]:
    """Mirrors ``_process_data()``'s sentinel-section lines, one branch per dotted path."""
    applied: Dict[str, Any] = {}
    dotted = "sentinel.gid"
    if dotted in declared:
        # Loaders read by key, so the value is wrapped under its config.yml key name.
        # A declared null never triggers a config.yml rewrite: the file is already loaded.
        applied[dotted] = config._load_config_int({"log_group_gid": declared[dotted]},
                                                  "log_group_gid", _current(config, dotted))
    dotted = "sentinel.sentinel_logs_host_path"
    if dotted in declared:
        # Same guard as the volume paths: this relocates the host audit logs.
        applied[dotted] = _resolve_host_path(config, dotted, declared[dotted],
                                             "sentinel_path", _current(config, dotted))
    dotted = "sentinel.log_rotation.enabled"
    if dotted in declared:
        applied[dotted] = config._load_config_bool({"enabled": declared[dotted]},
                                                   "enabled", _current(config, dotted))
    dotted = "sentinel.log_rotation.max_files"
    if dotted in declared:
        applied[dotted] = config._load_config_int({"max_files": declared[dotted]},
                                                  "max_files", _current(config, dotted))
    dotted = "sentinel.log_rotation.compress"
    if dotted in declared:
        applied[dotted] = config._load_config_bool({"compress": declared[dotted]},
                                                   "compress", _current(config, dotted))
    dotted = "sentinel.log_rotation.max_size"
    if dotted in declared:
        max_size = config._load_config_str({"max_size": declared[dotted]},
                                           "max_size", _current(config, dotted))
        # Shared positive-value guard, same as for a config.yml value.
        applied[dotted] = UserConfig._enforceLogRotationMaxSizePositive(max_size)
    dotted = "sentinel.log_output.enabled"
    if dotted in declared:
        # `_load_sentinel_bool`, not `_load_config_bool`: a profile-supplied value must go
        # through the same helper the config.yml path uses, and for this key that helper is the
        # fail-closed one. It carries a single underscore so both call sites can share it, as
        # `_enforceLogRotationMaxSizePositive` already does — reaching through the mangled
        # `config._UserConfig__load_sentinel_bool` would be a private access, and substituting
        # `_load_config_bool` would silently flip the direction, since that one is a bare
        # `cast()` that hands back whatever YAML produced.
        #
        # `unreadable=False` is the whole point: a value this helper cannot recognise resolves
        # to capture off. Pydantic's lax-bool coercion on `LogOutputSection.enabled` already
        # rejects most junk upstream, so this is the backstop for what survives it, and
        # guessing "on" for a value nobody could read is the one wrong answer available. A
        # declared null still resolves to the loaded config.yml value, which is what is passed
        # as the default.
        applied[dotted] = config._load_sentinel_bool({"enabled": declared[dotted]},
                                                     "enabled", _current(config, dotted),
                                                     "sentinel.log_output.enabled (profile)",
                                                     unreadable=False)
    dotted = "sentinel.log_output.max_size"
    if dotted in declared:
        max_size = config._load_config_str({"max_size": declared[dotted]},
                                           "max_size", _current(config, dotted))
        # The same shared helper the config.yml path uses, so a profile-supplied value gets
        # both halves: the strictly-positive guard with its fallback to the init default,
        # and the Splunk-truncate advisory. A value at or above the indexer's default
        # TRUNCATE destroys the event rather than shortening it, and nothing downstream
        # reports that, so the warning has to be raised where the value is read.
        applied[dotted] = UserConfig._enforceLogOutputMaxSize(max_size)
    dotted = "sentinel.log_output.truncation"
    if dotted in declared:
        # Same constrained choice set as the config.yml path; `_load_config_str` warns and
        # keeps the current value for anything outside it.
        applied[dotted] = config._load_config_str({"truncation": declared[dotted]},
                                                  "truncation", _current(config, dotted),
                                                  choices={"head", "tail", "both"})
    return applied


def _build_network_overrides(config: UserConfig, declared: Dict[str, Any]) -> Dict[str, Any]:
    """Mirrors ``_process_data()``'s network-section lines, one branch per dotted path."""
    applied: Dict[str, Any] = {}
    dotted = "network.dedicated_range"
    if dotted in declared:
        dedicated_range = declared[dotted]
        if dedicated_range is None:
            # A null keeps the loaded value: the dynamic default is a host scan that may
            # pick another subnet or block on an interactive prompt.
            applied[dotted] = _current(config, dotted)
        else:
            # Key must stay 'exegol_dedicated_range': the dynamic default is registered under it.
            applied[dotted] = config._load_config_str({"exegol_dedicated_range": dedicated_range},
                                                      "exegol_dedicated_range")
    dotted = "network.default_netmask"
    if dotted in declared:
        # Validated by parse_netmask like a config.yml value. str() first: the string loader
        # only casts, and the parser asserts on non-str input. A null stays None (keeps current).
        declared_netmask = declared[dotted]
        current_netmask = _current(config, dotted)
        applied[dotted] = NetworkUtils.parse_netmask(
            config._load_config_str(
                {"exegol_default_netmask": None if declared_netmask is None else str(declared_netmask)},
                "exegol_default_netmask", str(current_netmask)),
            default=current_netmask)
    return applied


def _build_image_overrides(config: UserConfig, declared: Dict[str, Any]) -> Dict[str, Any]:
    """Mirrors ``_process_data()``'s Enterprise-gated ``custom_images`` line.

    A profile file must not unlock an Enterprise feature: without access the field is
    skipped with a warning and nothing is returned (so no "applied" line is logged).
    """
    applied: Dict[str, Any] = {}
    dotted = "image.custom_images"
    if dotted in declared:
        if SessionHandler().enterprise_feature_access():
            # `default=` is mandatory: without it a declared null would become `[]` and wipe
            # the configured images instead of keeping them.
            applied[dotted] = config._load_config_list_str(
                {"custom_images": declared[dotted]}, "custom_images",
                default=list(_current(config, dotted)))
        else:
            logger.warning("Profile field 'image.custom_images' was not applied: custom images are an "
                           "Enterprise feature and this machine does not have Enterprise access.")
    return applied


def build_profile_user_config_tier(profile: ContainerProfile) -> Dict[OptionKey, Any]:
    """Compute, validate and announce ``profile``'s ``UserConfig`` overrides as a resolver tier.

    Only fields the profile file declared and that were actually applied get an entry (a
    gate may decline one). Each value goes through the same ``_load_config_*`` helper as
    ``config.yml``; a declared null keeps the already-loaded value. Stateless.
    """
    declared = flatten_profile_user_config_overrides(profile)
    if not declared:
        return {}

    # Read for the coercion fallback only, never written.
    config = UserConfig()

    applied: Dict[str, Any] = {}
    applied.update(_build_volume_overrides(config, declared))
    applied.update(_build_sentinel_overrides(config, declared))
    applied.update(_build_network_overrides(config, declared))
    applied.update(_build_image_overrides(config, declared))

    # Iterate the table for a stable announcement order.
    tier: Dict[OptionKey, Any] = {}
    for dotted, option_key in PROFILE_USER_CONFIG_MAP.items():
        if dotted not in applied:
            continue
        value = applied[dotted]
        tier[option_key] = value
        # escape() both halves: untrusted values could break rich markup or hide part of a path.
        logger.verbose(f"Profile override applied: [blue]{escape(dotted)}[/blue] = {escape(str(value))}")

    return tier
