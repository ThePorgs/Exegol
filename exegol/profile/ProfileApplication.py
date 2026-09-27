"""Translate a loaded :class:`ContainerProfile` into the resolver's profile tiers.

``ProfileFieldMap`` declares which dotted schema path feeds which ``OptionKey``; this module
walks the profile and builds the flat mappings. Rules of the walk:

* **Presence, not truthiness**: the source is ``model_dump(exclude_unset=True)``, so a key
  exists exactly when the file declared it, even as ``null``.
* **An unresolved path contributes nothing** (not ``None``), leaving the option to the lower
  tiers (UserConfig, builtin default).
* **``display.desktop`` is composed as a group** into the ``proto:host:port`` wire form.

No value is validated or normalised here (pydantic already did); coercion and announcements
live in :mod:`exegol.profile.ProfileUserConfigTier`.
"""

from typing import Any, Dict, Mapping, Optional, Tuple, cast

from exegol.config.OptionResolver import OptionKey, OptionResolver
from exegol.profile.ContainerProfile import ContainerProfile
from exegol.profile.ProfileFieldMap import PROFILE_FIELD_MAP, PROFILE_USER_CONFIG_MAP

# The only OptionKey composed from several schema fields: skipped by the generic loop and
# built by `_compose_desktop_config`.
_DESKTOP_SECTION = "display.desktop"
_DESKTOP_ANCHOR = _DESKTOP_SECTION+".proto"

# Marks "path not declared", distinct from a declared `None`.
_MISSING = object()


def _walk(dump: Dict[str, Any], dotted: str) -> Any:
    """Return the value at ``dotted`` inside ``dump``, or :data:`_MISSING`.

    A section declared as ``null`` stops the walk: its leaves were never declared.
    """
    node: Any = dump
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            return _MISSING
        node = node[segment]
    return node


def _sibling(dump: Dict[str, Any], section: str, field: str) -> Tuple[bool, Any]:
    """Return ``(declared, value)`` for ``field`` inside the ``section`` sub-dict."""
    node = _walk(dump, section)
    if not isinstance(node, dict) or field not in node:
        return False, None
    return True, node[field]


def _compose_desktop_config(dump: Dict[str, Any]) -> Optional[str]:
    """Recompose ``--desktop-config``'s ``"proto:host:port"`` string, or ``None``.

    ``None`` (option left unset) when ``proto`` is not declared. An absent sibling becomes an
    empty segment because the wire form is positional.
    """
    proto = _walk(dump, _DESKTOP_ANCHOR)
    if proto is _MISSING:
        return None
    _, listen_ip = _sibling(dump, _DESKTOP_SECTION, "listen_ip")
    _, port = _sibling(dump, _DESKTOP_SECTION, "port")
    return f"{proto or ''}:{listen_ip or ''}:{str(port) if port is not None else ''}"


def flatten_profile_for_resolver(profile: ContainerProfile) -> Dict[OptionKey, Any]:
    """Flatten ``profile`` into the ``{OptionKey: value}`` mapping for ``OptionResolver.loadProfile()``.

    Only options the profile file declares are present.
    """
    # exclude_unset=True is required: otherwise every undeclared field would pin its option to None.
    dump: Dict[str, Any] = profile.model_dump(exclude_unset=True)
    flat: Dict[OptionKey, Any] = {}

    for dotted, option_key in PROFILE_FIELD_MAP.items():
        if dotted == _DESKTOP_ANCHOR:
            continue
        value = _walk(dump, dotted)
        if value is not _MISSING:
            flat[option_key] = value

    desktop_config = _compose_desktop_config(dump)
    if desktop_config is not None:
        flat[PROFILE_FIELD_MAP[_DESKTOP_ANCHOR]] = desktop_config

    return flat


def flatten_profile_user_config_overrides(profile: ContainerProfile) -> Dict[str, Any]:
    """Flatten ``profile``'s ``PROFILE_USER_CONFIG_MAP`` fields into a dotted-path-keyed mapping.

    Keyed by dotted profile path (the operator-facing name) for
    :func:`~exegol.profile.ProfileUserConfigTier.build_profile_user_config_tier`. A key is
    present exactly when the file declared it, even as ``null``.
    """
    dump: Dict[str, Any] = profile.model_dump(exclude_unset=True)
    flat: Dict[str, Any] = {}

    for dotted in PROFILE_USER_CONFIG_MAP:
        value = _walk(dump, dotted)
        if value is not _MISSING:
            flat[dotted] = value

    return flat


def apply_profile(profile: ContainerProfile) -> None:
    """Install ``profile``'s two resolver tiers. Does not mutate ``UserConfig``.

    Must be called before ``ExegolManager.__loadOrInstallImage()``, which reads
    ``image.custom_images``. The two installs are order-independent (rank lives in
    ``resolve()``). The ``cast()`` calls are typing-only: ``Mapping`` is invariant in its key.
    """
    # Function-local import: ProfileUserConfigTier imports this module.
    from exegol.profile import ProfileUserConfigTier

    profile_user_config = ProfileUserConfigTier.build_profile_user_config_tier(profile)
    OptionResolver().loadProfileUserConfig(cast(Mapping[str, Any], profile_user_config))
    OptionResolver().loadProfile(cast(Mapping[str, Any], flatten_profile_for_resolver(profile)))
