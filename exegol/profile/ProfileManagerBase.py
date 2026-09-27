"""The discovery/selection surface shared by both profile managers.

``ContainerProfileManager`` and ``SentinelProfileManager`` share the on-disk shape
``<component_path>/<sourcekey>/...`` and the ``sourcekey.name`` selection syntax. This base
owns the scan root, the grouped listing and selection resolution. Loading, listing rows
and detail rendering are only declared: a container file is one whole profile (a bad file
is skipped alone) while a Sentinel file is a fragment merged per source (a bad file drops
the source).

Plain class rather than ``abc.ABC``: ``ABCMeta`` conflicts with ``MetaSingleton``.
Nothing here terminates the process; failures log an error and return ``None``.
"""

from pathlib import Path
from typing import Dict, Generic, List, Optional, Tuple, TypeVar

from rich.console import RenderableType
from rich.markup import escape

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger

#: Profile model stored by a concrete manager (``ContainerProfile`` or Sentinel ``Profile``).
ProfileT = TypeVar("ProfileT")


class ProfileManagerBase(Generic[ProfileT]):
    """Common root of the container and Sentinel profile managers."""

    #: Noun used in diagnostics ("Container profile" / "Sentinel profile").
    _PROFILE_KIND = "Profile"

    def __init__(self, profiles_path: Optional[Path] = None) -> None:
        # An explicit path scopes the manager to that tree (every subdirectory is a source)
        # instead of reading UserConfig, which keeps tmp_path-based tests off ~/.exegol.
        self._explicit_path: bool = profiles_path is not None
        # Conditional expression so the default, which reads (and may rewrite) the user
        # config file, is only evaluated when no explicit path was given.
        self._component_path: Path = profiles_path if profiles_path is not None else self._default_component_path()
        # sourcekey -> {name: profile}, filled by each subclass's scan.
        self._profiles: Dict[str, Dict[str, ProfileT]] = {}

    # ------------------------------------------------------------------
    # The subclass contract: hooks every concrete manager must define. They raise
    # NotImplementedError (repo convention, and ABCMeta conflicts with MetaSingleton), so a
    # missing override fails on first call rather than at instantiation.
    # ------------------------------------------------------------------

    def _default_component_path(self) -> Path:
        """The on-disk root to scan when no explicit path was given (a ``UserConfig`` field)."""
        raise NotImplementedError

    def load_profiles(self) -> bool:
        """Scan every enumerated source root and fill ``_profiles``. False on failure.

        Per-manager because a bad file means different things (see module docstring).
        Every method reading ``_profiles`` assumes this ran first.
        """
        raise NotImplementedError

    def list_rows(self) -> List[Dict[str, str]]:
        """Rows for the LIST form of `exegol info`: one row per discovered profile.

        Dict key order is column order. Cells must be table-ready (escaped): the dict table
        passes them to Rich as markup. Use :meth:`render_source` for the source cell.
        """
        raise NotImplementedError

    def describe(self, profile: ProfileT, title: str) -> Optional["RenderableType"]:
        """The DETAIL form of `exegol info <flag> <name>`: one renderable, or ``None``.

        ``None`` means the profile declares nothing; the caller says so instead of printing
        an empty table. Renders what the file declares, not every model field. ``title`` is
        composed (and escaped) by the caller. Output must be markup-safe, as for
        :meth:`list_rows`.
        """
        raise NotImplementedError

    def _effective_source_specs(self) -> Dict[str, Dict[str, str]]:
        """The declared source specs that survived any licence filter: ``{sourcekey: spec}``.

        Defaults to ``{}`` (no source concept), which is also the answer for a
        self-contained manager. :meth:`missing_git_source_roots` is built on it.
        """
        return {}

    def missing_git_source_roots(self) -> List[str]:
        """Source keys declared with ``git:`` whose clone directory does not exist yet, sorted.

        Reads the post-licence-filter specs, so git sources a licence does not allow never
        show up here. A self-contained manager declares no sources and returns ``[]``.
        Only one ``is_dir()`` per source: this runs on every profile read surface.
        """
        if self._explicit_path:
            return []
        return sorted(key for key, spec in self._effective_source_specs().items()
                      # A non-dict spec is not a source at all.
                      if isinstance(spec, dict) and spec.get("git")
                      and not (self._component_path / key).is_dir())

    #: The shipped first-party namespace, rendered green by :meth:`render_source`.
    _OFFICIAL_SOURCE_KEY = ConstantConfig.SENTINEL_CORE_SOURCE_KEY

    def render_source(self, source_key: str) -> str:
        """The source key as a table cell: escaped, then coloured by kind of source.

        Official ``core`` is green, a ``git:`` source is ``gold3`` (the colour used for
        Enterprise licences, which git sources require), a local source is plain. Escaping
        happens before adding tags so operator text cannot inject markup.
        """
        label = escape(source_key)
        if source_key == self._OFFICIAL_SOURCE_KEY:
            return f"[green]{label}[/green]"
        spec = self._effective_source_specs().get(source_key)
        if isinstance(spec, dict) and spec.get("git"):
            return f"[gold3]{label}[/gold3]"
        return label

    @property
    def component_path(self) -> Path:
        """The on-disk root this manager scans.

        Exposed so the empty-state message names the real directory, even when it differs
        from the ``UserConfig`` default.
        """
        return self._component_path

    def get_namespaced_profiles(self) -> Dict[str, Dict[str, ProfileT]]:
        """Return every loaded profile grouped by source: ``{sourcekey: {name: profile}}``.

        A sorted copy (both levels), so listings are stable regardless of scan order.
        Sources without profiles are omitted.
        """
        return {source_key: {name: mapping[name] for name in sorted(mapping)}
                for source_key, mapping in sorted(self._profiles.items()) if mapping}

    def get_profile(self, selection: str) -> Optional[ProfileT]:
        """Return the profile named by ``selection``, or ``None`` (with an error) if unresolvable."""
        resolved = self.resolve_profile_selection(selection)
        if resolved is None:
            return None
        source_key, name = resolved
        return self._profiles[source_key][name]

    def resolve_profile_selection(self, selection: str) -> Optional[Tuple[str, str]]:
        """Resolve a user selection to a concrete ``(sourcekey, name)`` pair.

        Accepts ``sourcekey.name`` (forces that source) or a bare ``name`` (resolves to the
        single source defining it). Unknown or ambiguous selections log an error listing the
        options and return ``None``.

        Never ``logger.critical``: this runs from listings, tab-completion and the restart
        path (after the container was stopped). Callers that must abort, such as container
        creation, escalate the ``None`` themselves.
        """
        # `selection` is operator-typed: escape it wherever it reaches the markup logger.
        if "." in selection:
            source_key, _, name = selection.partition(".")
            if name in self._profiles.get(source_key, {}):
                return source_key, name
            logger.error(f"{self._PROFILE_KIND} '{escape(selection)}' not found "
                         f"(source '{escape(source_key)}' defines no profile '{escape(name)}').")
            return None
        owners = sorted(src for src, profiles in self._profiles.items() if selection in profiles)
        if not owners:
            logger.error(f"{self._PROFILE_KIND} '{escape(selection)}' not found.")
            return None
        if len(owners) > 1:
            options = " ".join(f"'{escape(src)}.{escape(selection)}'" for src in owners)
            logger.error(f"{self._PROFILE_KIND} name '{escape(selection)}' is ambiguous: it is defined by "
                         f"{len(owners)} sources ({escape(', '.join(owners))}). Re-run with an explicit "
                         f"source-qualified name to remove the ambiguity: {options}")
            return None
        return owners[0], selection
