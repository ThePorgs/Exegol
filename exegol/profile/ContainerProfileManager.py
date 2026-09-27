"""Discovery and loading of container configuration profiles from disk.

A profile is addressed as ``<sourcekey>.<file stem>``. Source keys are exactly what
``config.profile.sources`` declares (``local`` is an ordinary source seeded on first setup).

Nothing here may terminate the process (no ``logger.critical``): this code runs from
``exegol info`` and tab-completion.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from rich.markup import escape
from rich.tree import Tree

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.config.OptionResolver import OptionKey, OptionResolver
from exegol.config.YamlConfigLoader import load_yaml_file
from exegol.profile.ContainerProfile import ContainerProfile
from exegol.profile.ProfileManagerBase import ProfileManagerBase
from exegol.utils import FsUtils
from exegol.utils.ExeLog import logger
from exegol.utils.MetaSingleton import MetaSingleton
from exegol.utils.RegexUtils import is_valid_sentinel_entity_name, is_valid_sentinel_source_key
from exegol.utils.SessionHandler import SessionHandler


class ContainerProfileManager(ProfileManagerBase[ContainerProfile], metaclass=MetaSingleton):
    """Load, list and resolve container profiles.

    Method names are ``snake_case`` to mirror ``SentinelProfileManager``; shared logic lives on
    ``ProfileManagerBase``.
    """

    _PROFILE_KIND = "Container profile"

    def __init__(self, profiles_path: Optional[Path] = None) -> None:
        super().__init__(profiles_path)
        # Declared sources are read once, here. Keep `OptionResolver().get(...)` inline (not
        # via a `UserConfig()` local): the direct-read check cannot see reads through a local.
        self._configured_sources: Dict[str, Dict[str, str]]
        # Declared sources that survived the licence filter; empty until `load_profiles()`.
        self.__effective_sources: Dict[str, Dict[str, str]] = {}
        if profiles_path is None:
            self._configured_sources = OptionResolver().get(OptionKey.PROFILE_SOURCES)
            # Create the 'local' directory only while 'local' is declared as a `path:` source,
            # so removing the entry actually disables it.
            local_spec = self._configured_sources.get(ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY)
            if local_spec and local_spec.get("path"):
                local_dir = EnvInfo.expand_user(local_spec["path"])
                if not local_dir.is_dir():
                    FsUtils.mkdir(local_dir)
        else:
            # Self-contained: scoped to the given tree, no declared sources.
            self._configured_sources = {}

    def _default_component_path(self) -> Path:
        """Where container profiles live when the manager was not given an explicit path."""
        # `get()` is safe here (runs after parsing). A profile can never override this path:
        # it would choose which profiles are read.
        return OptionResolver().get(OptionKey.PROFILE_COMPONENT_PATH)

    def _effective_source_specs(self) -> Dict[str, Dict[str, str]]:
        """The declared sources that survived the licence filter (empty until :meth:`load_profiles`).

        Post-filter, so callers are never prompted to fetch a source the loader drops.
        """
        return self.__effective_sources

    @staticmethod
    def __quoted(keys: List[str]) -> str:
        """Render ``keys`` as a comma-separated quoted list, escaped for Rich markup."""
        return ", ".join(f"'{escape(key)}'" for key in keys)

    def __applySourceLicenceFilter(self) -> Dict[str, Dict[str, str]]:
        """Trim the declared sources to the set this licence tier may load.

        Enterprise loads everything. Professional (the lowest tier reaching this class) loads
        a single ``path:`` source: git sources are dropped first, then the alphabetically
        first survivor wins, so an unusable git source cannot consume the allowance. The
        explicit ``sorted()`` is required: a hand-written config keeps its file order.

        Emits at most one warning per call (details go to verbose), never critical.
        """
        if self._explicit_path:
            # Self-contained: offline and licence-free.
            return self._configured_sources
        # Same predicate as the fetch gate, so load and fetch cannot disagree.
        if SessionHandler().enterprise_feature_access():
            return self._configured_sources

        skipped_git: List[str] = []
        local_keys: List[str] = []
        for key, spec in self._configured_sources.items():
            # Skipped like in __enumerate_roots.
            if not isinstance(spec, dict):
                continue
            if spec.get("git"):
                skipped_git.append(key)
            elif spec.get("path"):
                local_keys.append(key)
        survivors = sorted(local_keys)
        winner: Optional[str] = survivors[0] if survivors else None
        skipped_quota: List[str] = survivors[1:]
        effective: Dict[str, Dict[str, str]] = ({winner: self._configured_sources[winner]}
                                                if winner is not None else {})

        if skipped_git or skipped_quota:
            # Name every ignored key once, then explain in separate sentences.
            ignored = sorted(skipped_git + skipped_quota)
            line = f"Ignoring {len(ignored)} container profile source(s): {self.__quoted(ignored)}."
            if skipped_quota and winner is not None:
                # Name the winner: renaming a key is how the operator changes it.
                line += (f" Your licence tier allows a single local container profile source, "
                         f"using {self.__quoted([winner])}.")
            elif winner is not None:
                line += f" Using {self.__quoted([winner])}."
            else:
                line += " No container profile source is usable at this licence tier."
            if skipped_git:
                # Custom phrasing: `enterprise_access_message()` does not fit mid-line.
                line += " Git profile sources require an Enterprise licence: https://exegol.com/pricing"
            logger.warning(line)
            for key in skipped_git:
                logger.verbose(f"Container profile source {self.__quoted([key])} skipped: git sources are an "
                               f"Enterprise-only feature.")
            if winner is not None:
                # Always true when `skipped_quota` is non-empty; narrows the Optional.
                for key in skipped_quota:
                    logger.verbose(f"Container profile source {self.__quoted([key])} skipped: only one local "
                                   f"source loads at this licence tier, and {self.__quoted([winner])} sorts "
                                   f"first.")
        return effective

    def __enumerate_roots(self) -> Dict[str, Path]:
        """Build ``{sourcekey: root_dir}`` for every source namespace to scan."""
        roots: Dict[str, Path] = {}
        if self._explicit_path:
            # Self-contained: each non-dot subdirectory under the given path is a source.
            if self._component_path.is_dir():
                for child in sorted(self._component_path.iterdir()):
                    if not child.is_dir() or child.name.startswith("."):
                        continue
                    if not is_valid_sentinel_source_key(child.name):
                        logger.warning(f"Ignoring container profile source directory {child}: a source key may "
                                       f"only contain letters, digits, '_' or '-'.")
                        continue
                    roots[child.name] = child
            return roots
        # Only the licence-filtered declared sources; a stray directory on disk is not a source.
        # A `path:` source is scanned in place, a `git:` source under `component_path / key`.
        for key, spec in self.__effective_sources.items():
            if not isinstance(spec, dict):
                continue
            local_path = spec.get("path")
            if local_path:
                roots[key] = EnvInfo.expand_user(local_path)
            else:
                roots[key] = self._component_path / key
        return roots

    def __scan_source_root(self, source_key: str, root_dir: Path) -> bool:
        """Load every profile YAML under ``root_dir`` into the ``source_key`` namespace.

        A missing root is not a failure: verbose for an unfetched ``git:`` source (the fetch
        prompt covers it), a warning otherwise. A bad file is skipped; its siblings still load.
        """
        if not root_dir.is_dir():
            spec = self._effective_source_specs().get(source_key)
            location = f"'{escape(source_key)}' ({escape(str(root_dir))})"
            if isinstance(spec, dict) and spec.get("git"):
                logger.verbose(f"Container profile source root {location} not found: the source is declared "
                               f"with 'git:' and has not been fetched yet. Run `exegol update` to fetch it.")
            else:
                logger.warning(f"Container profile source root {location} not found. Skipping.")
            return True
        profiles = self._profiles.setdefault(source_key, {})
        # Both extensions; set + sorted() keeps the load order deterministic.
        candidates: Set[Path] = set()
        for pattern in ("**/*.yml", "**/*.yaml"):
            candidates.update(root_dir.glob(pattern))
        success = True
        # Files considered vs. profiles actually loaded (warn when none loaded).
        seen_files = 0
        loaded = 0
        for yaml_file in sorted(candidates):
            # Silently skip every dot-directory (.git, .github, ...).
            if any(part.startswith(".") for part in yaml_file.relative_to(root_dir).parts):
                continue
            seen_files += 1
            name = yaml_file.stem
            # The stem is the profile name: ASCII-only, no '.' (the source separator).
            if not is_valid_sentinel_entity_name(name):
                # escape(): an invalid name may contain Rich markup.
                logger.error(f"Ignoring container profile file {escape(str(yaml_file))}: the profile name "
                             f"'{escape(name)}' may only contain letters, digits, '_' and '-' "
                             f"('.' is the source separator).")
                success = False
                continue
            # Recursive glob: 'a/web.yml' and 'b/web.yml' collide; refuse the second loudly.
            if name in profiles:
                logger.error(f"Ignoring container profile file {escape(str(yaml_file))}: the profile name "
                             f"'{escape(name)}' is already defined by another file in source "
                             f"'{escape(source_key)}'. Rename one of them, a profile name must be unique "
                             f"within its source.")
                success = False
                continue
            errors: List[Path] = []
            profile = load_yaml_file(yaml_file, ContainerProfile, errors=errors)
            if profile is None:
                # An empty file is not a failure. Unlike Sentinel, only this file is dropped,
                # not the whole source: each file is a self-contained profile.
                if errors:
                    success = False
                continue
            profiles[name] = profile
            loaded += 1
        if seen_files and not loaded:
            # Otherwise "no profiles" would hide that every file was rejected.
            logger.warning(f"Container profile source '{escape(source_key)}' ({escape(str(root_dir))}): found "
                           f"{seen_files} file(s) but loaded 0 profiles. See the errors above.")
        return success

    def load_profiles(self) -> bool:
        """Load every profile from the enumerated source roots. Returns False on failure."""
        self._profiles = {}
        # Licence trim first, and before the early return below: `missing_git_source_roots()`
        # reads the result, even when component_path does not exist yet (fresh git-only setup).
        self.__effective_sources = self.__applySourceLicenceFilter()
        roots = self.__enumerate_roots()
        # Only fatal when there is nothing to enumerate: `path:` sources live outside
        # component_path, and missing roots are reported per source while scanning.
        if not roots and not self._component_path.is_dir():
            logger.warning(f"Container profile directory {self._component_path} not found.")
            return False
        success = True
        for source_key, root in roots.items():
            if not self.__scan_source_root(source_key, root):
                success = False
        return success

    def get_profile_by_source(self, source_key: str, name: str) -> Optional[ContainerProfile]:
        """Return the profile at an already-resolved ``(source_key, name)``, or ``None`` (silently)."""
        return self._profiles.get(source_key, {}).get(name)

    # ------------------------------------------------------------------
    # Renderings for `exegol info --profile [...]`: listing rows and the detail tree.
    # ------------------------------------------------------------------

    # "Declared as null" and "not declared" resolve differently, so they are shown apart.
    _PROFILE_NULL_MARKER = "<declared as null>"
    _PROFILE_EMPTY_MARKER = "<declared, empty>"

    #: Icon per top-level section, keyed by YAML field name; unlisted sections use the default.
    _SECTION_EMOJI: Dict[str, str] = {
        "version": ":label:",
        "image": ":package:",
        "network": ":globe_with_meridians:",
        "volumes": ":file_folder:",
        "customization": ":wrench:",
        "display": ":desktop_computer:",
        "vpn": ":locked_with_key:",
        "shell": ":shell:",
        "logging": ":scroll:",
        "system": ":shield:",
        "sentinel": ":satellite:",
        "metadata": ":memo:",
    }
    _SECTION_DEFAULT_EMOJI = ":small_blue_diamond:"

    def list_rows(self) -> List[Dict[str, str]]:
        """Rows for `exegol info --profile`: Source, Name, Description, like the interactive picker.

        Key order is column order. Every cell is escaped here: ``__buildDictTable`` does not.
        """
        rows: List[Dict[str, str]] = []
        for source_key, mapping in self.get_namespaced_profiles().items():
            source_label = self.render_source(source_key)
            for name, profile in mapping.items():
                description = (profile.metadata.description
                               if profile.metadata is not None and profile.metadata.description is not None
                               else "")
                rows.append({"source": source_label,
                             "name": escape(name),
                             # Same dash placeholder as the picker.
                             "description": escape(description) or "[bright_black]—[/bright_black]"})
        return rows

    def describe(self, profile: ContainerProfile, title: str) -> Optional[Tree]:
        """Detail view of `exegol info --profile <name>`: a Rich tree of the declared fields.

        ``None`` when the profile declares nothing. Only set fields are shown
        (``exclude_unset=True``), and every label and value is escaped.
        """
        dump = profile.model_dump(exclude_unset=True)
        if not dump:
            # Only an empty root means "declares nothing"; `network: {}` still renders.
            return None
        # Same grey as the wrapper's table borders.
        tree = Tree(title, guide_style="grey35")
        for key, value in dump.items():
            self.__grow_tree(tree, str(key), value, top_level=True)
        return tree

    def __grow_tree(self, parent: Tree, key: str, value: Any, top_level: bool = False) -> None:
        """Add ``key``/``value`` under ``parent``, recursing into sections and list entries."""
        label = escape(key)
        if top_level:
            emoji = self._SECTION_EMOJI.get(key, self._SECTION_DEFAULT_EMOJI)
            # Italic emojis render skewed in some terminals.
            label = f"[not italic]{emoji} [/not italic][bold blue]{label}[/bold blue]"
        else:
            label = f"[blue]{label}[/blue]"
        if isinstance(value, dict):
            if not value:
                # `network: {}`: a leaf with the empty marker, not an empty branch.
                parent.add(f"{label}: {self._PROFILE_EMPTY_MARKER}")
                return
            branch = parent.add(label)
            for sub_key, sub_value in value.items():
                self.__grow_tree(branch, str(sub_key), sub_value)
            return
        if isinstance(value, list) and any(isinstance(item, dict) for item in value):
            # A list of mappings becomes one child per entry; scalar lists stay a single leaf.
            branch = parent.add(f"{label} [bright_black]({len(value)})[/bright_black]")
            for index, item in enumerate(value, start=1):
                self.__grow_tree(branch, f"#{index}", item)
            return
        parent.add(f"{label}: {self.__render_value(value)}")

    def __render_value(self, value: Any) -> str:
        """Render one declared value as a markup-escaped string (values may be third-party)."""
        if value is None:
            return self._PROFILE_NULL_MARKER
        if isinstance(value, (list, tuple, set)):
            rendered = ", ".join(str(item) for item in value) or self._PROFILE_EMPTY_MARKER
        else:
            rendered = str(value)
        return escape(rendered)
