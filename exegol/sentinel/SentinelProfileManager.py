"""Discovery and loading of Sentinel triggers, actions and profiles from disk.

Layout: ``<component_path>/<sourcekey>/**/*.yml``. A source is a namespace merged across
files, so one unparseable file drops the whole source (``ContainerProfileManager`` only
skips the file).

Nothing here may terminate the process (no ``logger.critical``): this code runs on the
restart path, where exiting would leave the container stopped.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from rich import box
from rich.console import Group, RenderableType
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.config.OptionResolver import OptionKey, OptionResolver
from exegol.config.YamlConfigLoader import load_yaml_file
from exegol.profile.ProfileManagerBase import ProfileManagerBase
from exegol.sentinel.SentinelProfile import (
    DEFAULT_SOURCE_KEY,
    DEFAULT_TRIGGER_SYSTEM,
    Action,
    ActionBase,
    CompositeTrigger,
    LogOutputConfig,
    LogRotationConfig,
    Profile,
    ProfileRule,
    SentinelConfig,
    Trigger,
    TriggerBase,
    resolve_reference,
)
from exegol.utils import FsUtils
from exegol.utils.ExeLog import logger
from exegol.utils.RegexUtils import sanitize_source_url
from exegol.utils.SizeUtils import parse_size_to_bytes


# Deliberately NOT a MetaSingleton: the singleton ignores later constructor arguments, and
# tests/sentinel/ builds managers on distinct temporary trees without evicting it.
class SentinelProfileManager(ProfileManagerBase[Profile]):
    """
    Manage Sentinel profiles, triggers and actions.
    Parses YAML files, validates them and generates consolidated configuration.
    """

    _PROFILE_KIND = "Sentinel profile"

    def __init__(self, profiles_path: Optional[Path] = None):
        # An explicit path makes the manager self-contained: it never reads the global config.
        super().__init__(profiles_path)
        if not self._component_path.is_dir():
            FsUtils.mkdir(self._component_path)
        # Global configuration is read once, here, and only when not self-contained.
        self._configured_sources: Dict[str, Dict[str, str]]
        self.__default_log_rotation: Dict[str, Any]
        self.__default_log_output: Dict[str, Any]
        if profiles_path is None:
            # Keep `OptionResolver().get(...)` inline (not via a `UserConfig()` local): the
            # direct-read check cannot see reads through a local. A container profile can
            # never override `sentinel_sources`.
            self._configured_sources = OptionResolver().get(OptionKey.SENTINEL_SOURCES)
            # The four settings form one retention policy, resolved together.
            rotation_enabled = OptionResolver().get(OptionKey.SENTINEL_LOG_ROTATION_ENABLED)
            rotation_max_size = OptionResolver().get(OptionKey.SENTINEL_LOG_ROTATION_MAX_SIZE)
            rotation_max_files = OptionResolver().get(OptionKey.SENTINEL_LOG_ROTATION_MAX_FILES)
            rotation_compress = OptionResolver().get(OptionKey.SENTINEL_LOG_ROTATION_COMPRESS)
            self.__default_log_rotation = {
                "enabled": rotation_enabled,
                # Normalised to bytes here: neither the resolver nor the container parses units.
                "max_size": parse_size_to_bytes(rotation_max_size),
                "max_files": rotation_max_files,
                "compress": rotation_compress,
            }
            # The three inline-output settings, resolved like the rotation family above.
            # `enabled` is registered but permanently profile-tier dead, so it can only ever
            # answer from config.yml; `max_size` and `truncation` ARE profile-overridable,
            # and going through the resolver is what lets a profile reach them at all.
            output_enabled = OptionResolver().get(OptionKey.SENTINEL_LOG_OUTPUT_ENABLED)
            output_max_size = OptionResolver().get(OptionKey.SENTINEL_LOG_OUTPUT_MAX_SIZE)
            output_truncation = OptionResolver().get(OptionKey.SENTINEL_LOG_OUTPUT_TRUNCATION)
            self.__default_log_output = {
                "enabled": output_enabled,
                # Normalised to bytes here: neither the resolver nor the container parses units.
                "max_size": parse_size_to_bytes(output_max_size),
                "truncation": output_truncation,
            }
            # Create the 'local' directory only while 'local' is declared as a `path:` source.
            local_spec = self._configured_sources.get(ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY)
            if local_spec and local_spec.get("path"):
                local_dir = EnvInfo.expand_user(local_spec["path"])
                if not local_dir.is_dir():
                    FsUtils.mkdir(local_dir)
        else:
            # Self-contained: rotation defaults come from the model (max_size already in bytes).
            self._configured_sources = {}
            self.__default_log_rotation = LogRotationConfig().model_dump()
            self.__default_log_output = LogOutputConfig().model_dump()
        # Per-namespace stores: sourcekey -> {name: X}. ``self._profiles`` is set by the base class.
        self.__triggers: Dict[str, Dict[str, Trigger]] = {}
        self.__actions: Dict[str, Dict[str, Action]] = {}
        # sourcekey -> on-disk root dir (used for _meta provenance / SHA read-back).
        self.__source_roots: Dict[str, Path] = {}
        # Sources dropped by load_profiles() because one of their files failed to parse.
        # Kept because the stores have already been emptied of them: without this, "the
        # source was dropped" and "the source never defined it" are indistinguishable at
        # lookup time, and the second was reported for the first -- sending the operator
        # hunting for a missing profile instead of fixing the YAML that was broken.
        self.__dropped_sources: Set[str] = set()
        # Flattened bare-name view of all namespaces, kept for backward-compatible
        # direct access (e.g. legacy single-source tests / callers).
        self.__config = SentinelConfig()

    def _default_component_path(self) -> Path:
        """Where Sentinel profiles live when the manager was not given an explicit path."""
        # A profile can never override this path (it would choose which profiles are read).
        return OptionResolver().get(OptionKey.SENTINEL_PROFILE_PATH)

    def _effective_source_specs(self) -> Dict[str, Dict[str, str]]:
        """The declared sources: the licence quota only applies to container-profile sources."""
        return self._configured_sources

    def __reset_stores(self) -> None:
        self.__triggers = {}
        self.__actions = {}
        self._profiles = {}
        self.__source_roots = {}
        self.__dropped_sources = set()
        self.__config = SentinelConfig()

    def __rebuild_flat_view(self) -> None:
        """Mirror the namespaced stores into the flat ``self.__config`` (bare names).

        Later namespaces win on a bare-name clash — this view is only for
        backward-compatible direct access; the authoritative stores are namespaced.
        """
        flat_t: Dict[str, Trigger] = {}
        flat_a: Dict[str, Action] = {}
        flat_p: Dict[str, Profile] = {}
        for mapping_t in self.__triggers.values():
            flat_t.update(mapping_t)
        for mapping_a in self.__actions.values():
            flat_a.update(mapping_a)
        for mapping_p in self._profiles.values():
            flat_p.update(mapping_p)
        self.__config.triggers = flat_t
        self.__config.actions = flat_a
        self.__config.profiles = flat_p

    def __scan_source_root(self, source_key: str, root_dir: Path, recursive: bool = True) -> bool:
        """Load every profile YAML under ``root_dir`` into the ``source_key`` namespace.

        A missing root is skipped with a warning. Returns False only when a file fails to
        parse/validate; an empty file is tolerated (the ``errors`` list tells them apart).
        """
        if not root_dir.is_dir():
            logger.warning(f"Sentinel source root '{source_key}' ({root_dir}) not found. Skipping.")
            return True
        triggers = self.__triggers.setdefault(source_key, {})
        actions = self.__actions.setdefault(source_key, {})
        profiles = self._profiles.setdefault(source_key, {})
        # Both extensions.
        patterns = ("**/*.yml", "**/*.yaml") if recursive else ("*.yml", "*.yaml")
        candidates: Set[Path] = set()
        for pattern in patterns:
            candidates.update(root_dir.glob(pattern))
        file_errors: List[Path] = []
        scanned = 0
        merged = 0
        for yaml_file in sorted(candidates):
            # Skip every dot-path (.github/, .pre-commit-config.yaml...): under strict validation
            # they would drop the whole source. Relative to root_dir, since ~/.exegol is dotted.
            if any(part.startswith(".") for part in yaml_file.relative_to(root_dir).parts):
                continue
            scanned += 1
            file_config = load_yaml_file(yaml_file, SentinelConfig, errors=file_errors)
            if file_config is None:
                # Either empty (tolerated, nothing to merge) or invalid (already
                # recorded in file_errors by name, with a per-error diagnostic).
                continue
            for name, t in file_config.triggers.items():
                triggers[name] = t
                merged += 1
            for name, a in file_config.actions.items():
                actions[name] = a
                merged += 1
            for name, p in file_config.profiles.items():
                profiles[name] = p
                merged += 1
        if not file_errors and scanned and not merged:
            # Files present and valid, yet nothing loaded: say so.
            logger.warning(f"Sentinel source '{source_key}' ({root_dir}): {scanned} YAML file(s) found "
                           f"but 0 trigger/action/profile loaded. Check that the files declare a "
                           f"'triggers:', 'actions:' or 'profiles:' block.")
        return not file_errors

    def __enumerate_roots(self) -> Dict[str, Path]:
        """Build ``{sourcekey: root_dir}`` for the core + configured sources.

        ``core`` -> ``component_path/core``; each configured git-source key ->
        ``component_path/<key>``; each local ``path:`` source -> its configured dir
        (scanned in place).

        When the manager was created with an explicit ``profiles_path`` it is self-contained:
        it enumerates every on-disk namespace subdirectory under that path and does not read
        the global UserConfig sources (which are scoped to the default component path).
        """
        roots: Dict[str, Path] = {}
        component_path = self._component_path
        core_root = component_path / DEFAULT_SOURCE_KEY
        if core_root.is_dir():
            roots[DEFAULT_SOURCE_KEY] = core_root
        if self._explicit_path:
            # Self-contained: each subdirectory under the given path is a source namespace.
            for child in sorted(component_path.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    roots[child.name] = child
            return roots
        # Sources captured once in __init__.
        for key, spec in self._configured_sources.items():
            if not isinstance(spec, dict):
                continue
            local_path = spec.get("path")
            if local_path:
                roots[key] = EnvInfo.expand_user(local_path)
            else:
                roots[key] = component_path / key
        return roots

    def load_profiles(self) -> bool:
        """
        Load all YAML profiles from the enumerated namespaced source roots.
        Returns True if successful, False otherwise.
        """
        if not self._component_path or not self._component_path.is_dir():
            logger.warning(f"Sentinel profiles directory {self._component_path} not found.")
            return False

        self.__reset_stores()

        # Migration aid: loose files directly under component_path are no longer loaded.
        orphans = [p for p in self._component_path.glob("*.yml")] + [p for p in self._component_path.glob("*.yaml")]
        if orphans:
            logger.warning(f"{len(orphans)} Sentinel profile file(s) found directly under "
                           f"{self._component_path} are no longer loaded. Move them into a source "
                           f"subdirectory (e.g. '{ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY}/').")

        # A parse failure drops only its source, so a broken team source cannot abort
        # container creation with a profile from a healthy one.
        failed_sources: List[str] = []
        for source_key, root in self.__enumerate_roots().items():
            self.__source_roots[source_key] = root
            if not self.__scan_source_root(source_key, root, recursive=True):
                failed_sources.append(source_key)

        self.__dropped_sources = set(failed_sources)
        for source_key in failed_sources:
            logger.warning(f"Sentinel source '{source_key}' contains invalid profile file(s); its whole "
                           f"namespace is dropped. Profiles from the other sources are still available.")
            self.__triggers.pop(source_key, None)
            self.__actions.pop(source_key, None)
            self._profiles.pop(source_key, None)
            self.__source_roots.pop(source_key, None)

        self.__rebuild_flat_view()
        if failed_sources and not self.__source_roots:
            # No healthy source left.
            return False
        # A profile from a dropped source surfaces later as "profile not found", with the
        # hint resolve_profile_selection() adds from __dropped_sources.
        return self.validate_references()

    def resolve_profile_selection(self, selection: str) -> Optional[Tuple[str, str]]:
        """Resolve a selection, adding why when a dropped source may have defined it.

        The base class cannot say this: it only sees the surviving stores, so "not found"
        is the only answer it can give, and for a name that lived in a source dropped for a
        parse error that answer is false and points at the wrong fix.

        A source-qualified name whose source was dropped short-circuits before the base
        resolver: the base would state as fact that the source defines no such profile, but
        the store it reads was emptied by the drop, so it cannot know either way. Every
        other selection keeps the base's branch logic and only gains the hint after it.
        """
        if "." in selection:
            source_key, _, name = selection.partition(".")
            if source_key in self.__dropped_sources:
                logger.error(f"{self._PROFILE_KIND} '{escape(selection)}' cannot be resolved: source "
                             f"'{escape(source_key)}' was dropped for invalid profile file(s), so whether "
                             f"it defines '{escape(name)}' is unknown; fix the parse error above.")
                return None
        resolved = super().resolve_profile_selection(selection)
        if resolved is None and self.__dropped_sources:
            logger.error(f"Note that {len(self.__dropped_sources)} Sentinel source(s) were dropped for "
                         f"invalid profile file(s) ({escape(', '.join(sorted(self.__dropped_sources)))}); "
                         f"if it lived there, fix the parse error above rather than the name.")
        return resolved

    def list_rows(self) -> List[Dict[str, str]]:
        """Rows for the Sentinel profile listing: Source, Profile, rules count.

        Cells are escaped here: ``__buildDictTable`` does not.
        """
        rows: List[Dict[str, str]] = []
        profiles_by_source = self.get_namespaced_profiles()
        for source_key in sorted(profiles_by_source):
            source_label = self.render_source(source_key)
            for name in sorted(profiles_by_source[source_key]):
                profile = profiles_by_source[source_key][name]
                rows.append({"source": source_label,
                             "profile": escape(name),
                             "rules": str(len(profile.rules))})
        return rows

    #: Same marker as ``ContainerProfileManager``.
    _PROFILE_EMPTY_MARKER = "<declared, empty>"

    def __flatten(self, value: Any, prefix: str, out: List[Dict[str, str]]) -> None:
        """Recursively flatten ``value`` into dotted-path ``option``/``value`` rows.

        Used for empty-rules profiles and the ``config`` block. Lists of mappings are
        indexed (``rules[1].actions``); scalar lists are joined.
        """
        if isinstance(value, dict):
            if value:
                for key, sub_value in value.items():
                    # Keys are operator-authored too: escape them.
                    segment = escape(str(key))
                    self.__flatten(sub_value, f"{prefix}.{segment}" if prefix else segment, out)
            elif prefix:
                out.append({"option": prefix, "value": self._PROFILE_EMPTY_MARKER})
            return
        if isinstance(value, list) and any(isinstance(item, (dict, list)) for item in value):
            # 1-based brackets: `rules[1]` reads as "the first rule", `rules.0` as a field.
            for index, item in enumerate(value, start=1):
                self.__flatten(item, f"{prefix}[{index}]" if prefix else f"[{index}]", out)
            return
        out.append({"option": prefix, "value": self.__render(value)})

    def __render(self, value: Any) -> str:
        """Render one declared value as a markup-escaped string."""
        if isinstance(value, bool):
            # YAML spelling, not Python's True/False.
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, list):
            return escape(", ".join(str(item) for item in value)) or self._PROFILE_EMPTY_MARKER
        return escape(str(value))

    # Glyphs keep triggers and actions apart on wrapped lines; italic emojis render skewed.
    _TRIGGER_BULLET = "[not italic]:zap: [/not italic]"
    _ACTION_BULLET = "[not italic]:gear: [/not italic]"

    def describe(self, profile: Profile, title: str) -> Optional[RenderableType]:
        """Detail view of `exegol info --sentinel <name>`: one table row per rule.

        Triggers render as a tree (composites nest, inline members are summarised).
        Unresolved references are labelled, never omitted. An empty ``rules`` list falls
        back to the flat table; a profile declaring nothing returns ``None``. All labels
        are escaped.
        """
        dump = profile.model_dump(exclude_unset=True)
        if not dump:
            return None
        if not profile.rules:
            # Local import: ExegolTUI is heavy and unneeded on non-rendering paths.
            from exegol.console.TUI import ExegolTUI
            rows: List[Dict[str, str]] = []
            self.__flatten(dump, "", rows)
            return ExegolTUI.buildDictTable(rows, title=title)
        # Needed to resolve bare references; `None` if the profile is not in this manager.
        source_key = self.__source_of(profile)
        # Same styling as ExegolTUI.printTable, plus lines between multi-line rule rows.
        table = Table(title=title, show_header=True, header_style="bold blue", border_style="grey35",
                      box=box.SQUARE, title_justify="left",
                      show_lines=True)
        table.add_column("Rule")
        # Rule-level operator in its own column, apart from nested composite operators.
        table.add_column("Logic")
        table.add_column("Triggers")
        table.add_column("Actions")
        for index, rule in enumerate(profile.rules, start=1):
            operator, refs = self.__rule_logic(rule)
            # The tree is only there for its guide lines.
            triggers = Tree("", hide_root=True, guide_style="grey35")
            for ref in refs:
                self.__grow_trigger(triggers, ref, source_key, frozenset())
            actions = Tree("", hide_root=True, guide_style="grey35")
            for action_ref in rule.actions:
                self.__grow_action(actions, action_ref, source_key)
            table.add_row(f"[bold]#{index}[/bold]", f"[bold magenta]{operator}[/bold magenta]", triggers, actions)
        config = self.__describe_config(profile)
        if config is None:
            return table
        # The config block is per-profile, so it goes below the per-rule table.
        return Group(table, config)

    @staticmethod
    def __rule_logic(rule: ProfileRule) -> Tuple[str, List[str]]:
        """Split a rule's trigger declaration into ``(operator, refs)``; a bare list is ``AND``."""
        if isinstance(rule.triggers, list):
            return "AND", rule.triggers
        return rule.triggers.operator, rule.triggers.refs

    def __source_of(self, profile: Profile) -> Optional[str]:
        """The namespace key ``profile`` was loaded into, or ``None``.

        Matched by identity: two sources may declare equal profiles.
        """
        for source_key, mapping in self._profiles.items():
            for candidate in mapping.values():
                if candidate is profile:
                    return source_key
        return None

    def __grow_trigger(self, parent: Tree, item: Any, source_key: Optional[str], seen: "frozenset[Tuple[str, str]]") -> None:
        """Render one trigger member: a reference (``str`` or ``{"trigger": ref}``), an inline
        trigger, or a sub-composite. Recurses into composite members."""
        if isinstance(item, TriggerBase):
            # One renderer for parsed and dumped members.
            item = item.model_dump()
        if isinstance(item, dict) and isinstance(item.get("trigger"), str):
            # `- trigger: other_name`, the long form of a bare reference.
            item = item["trigger"]
        if isinstance(item, str):
            self.__grow_trigger_ref(parent, item, source_key, seen)
            return
        if isinstance(item, dict):
            self.__grow_inline_trigger(parent, item, source_key, seen)
            return
        # Unreachable through the model; render rather than crash.
        parent.add(f"{self._TRIGGER_BULLET}{self.__render(item)}")

    def __grow_trigger_ref(self, parent: Tree, ref: str, source_key: Optional[str], seen: "frozenset[Tuple[str, str]]") -> None:
        """Render a NAMED trigger reference, expanding it when it resolves to a composite."""
        label = escape(ref)
        if ref.lower() in DEFAULT_TRIGGER_SYSTEM:
            # `always` / `never` are system triggers, not on disk.
            parent.add(f"{self._TRIGGER_BULLET}[green]{label}[/green] [bright_black](system)[/bright_black]")
            return
        resolved = self.__resolve_trigger(ref, source_key)
        if resolved is None:
            # Marked explicitly: the rule cannot fire as written.
            parent.add(f"{self._TRIGGER_BULLET}{label} [red](unresolved)[/red]")
            return
        src, name, trigger = resolved
        if not isinstance(trigger, CompositeTrigger):
            parent.add(f"{self._TRIGGER_BULLET}{label} [bright_black]({self.__entity_kind(trigger)})[/bright_black]")
            return
        key = (src, name)
        if key in seen:
            # Reference cycle between composites: stop and say so.
            parent.add(f"{self._TRIGGER_BULLET}{label} [bright_black](cycle)[/bright_black]")
            return
        branch = parent.add(f"{self._TRIGGER_BULLET}{label} [bold magenta]({trigger.trigger.operator})[/bold magenta]")
        for member in trigger.trigger.triggers:
            # Members resolve against the composite's own source, as in get_consolidated_config().
            self.__grow_trigger(branch, member, src, seen | {key})

    def __grow_inline_trigger(self, parent: Tree, data: Dict[str, Any], source_key: Optional[str],
                              seen: "frozenset[Tuple[str, str]]") -> None:
        """Render an anonymous inline trigger, labelled by its kind key and summarised by its options."""
        kind = next(iter(data), "")
        options = data.get(kind)
        if kind == "trigger" and isinstance(options, dict):
            operator = str(options.get("operator", "AND"))
            branch = parent.add(f"{self._TRIGGER_BULLET}[bright_black]inline[/bright_black] "
                                f"[bold magenta]({escape(operator)})[/bold magenta]")
            for member in options.get("triggers", []):
                # Anonymous: members resolve against the enclosing source.
                self.__grow_trigger(branch, member, source_key, seen)
            return
        parent.add(f"{self._TRIGGER_BULLET}[bright_black]inline {escape(str(kind))}:[/bright_black] "
                   f"{self.__render_options(options)}")

    def __render_options(self, options: Any) -> str:
        """Summarise an inline trigger's options on one line as ``key=value`` pairs."""
        if isinstance(options, dict):
            return ", ".join(f"[blue]{escape(str(key))}[/blue]={self.__render(value)}"
                             for key, value in options.items()) or self._PROFILE_EMPTY_MARKER
        return self.__render(options)

    def __grow_action(self, parent: Tree, ref: str, source_key: Optional[str]) -> None:
        """Render one action reference as a leaf, annotated with its resolved kind."""
        label = escape(ref)
        resolved = self.__resolve_action(ref, source_key)
        if resolved is None:
            parent.add(f"{self._ACTION_BULLET}{label} [red](unresolved)[/red]")
            return
        parent.add(f"{self._ACTION_BULLET}{label} [bright_black]({self.__entity_kind(resolved)})[/bright_black]")

    def __resolve_trigger(self, ref: str, source_key: Optional[str]) -> Optional[Tuple[str, str, Trigger]]:
        """Resolve a trigger ref to ``(sourcekey, name, trigger)``, or ``None``."""
        if source_key is None:
            return None
        available = {src: set(mapping.keys()) for src, mapping in self.__triggers.items()}
        try:
            src, name = resolve_reference(ref, source_key, available)
        except KeyError:
            return None
        return src, name, self.__triggers[src][name]

    def __resolve_action(self, ref: str, source_key: Optional[str]) -> Optional[Action]:
        """Resolve an action ref to its model, or ``None``."""
        if source_key is None:
            return None
        available = {src: set(mapping.keys()) for src, mapping in self.__actions.items()}
        try:
            src, name = resolve_reference(ref, source_key, available)
        except KeyError:
            return None
        return self.__actions[src][name]

    @staticmethod
    def __entity_kind(entity: Union[TriggerBase, ActionBase]) -> str:
        """The YAML key declaring this trigger's or action's kind (the model's single field name)."""
        return escape(next(iter(type(entity).model_fields), "unknown"))

    def __describe_config(self, profile: Profile) -> Optional[Panel]:
        """The profile-level ``config`` block as a panel of flattened rows, or ``None`` if empty."""
        if profile.config is None:
            return None
        rows: List[Dict[str, str]] = []
        self.__flatten(profile.config.model_dump(exclude_unset=True), "", rows)
        if not rows:
            # `config: {}`: no empty panel.
            return None
        body = "\n".join(f"[blue]{row['option']}[/blue]: {row['value']}" for row in rows)
        return Panel(body, title="[not italic]:wrench: [/not italic][bold blue]config[/bold blue]",
                     title_align="left", border_style="grey35", box=box.SQUARE, expand=False)

    def validate_references(self) -> bool:
        """
        Validate that all triggers and actions referenced in profiles resolve
        through the namespace model (bare -> current source then core;
        ``sourcekey.name`` -> that source). Default triggers (always/never) are
        always valid.
        """
        trig_avail: Dict[str, Set[str]] = {src: set(m.keys()) for src, m in self.__triggers.items()}
        act_avail: Dict[str, Set[str]] = {src: set(m.keys()) for src, m in self.__actions.items()}

        valid = True

        def validate_trigger_ref(ref: str, source: str, origin: str, seen: Set[Tuple[str, str]]) -> bool:
            """Validate a trigger ref and, for a composite, every sub-ref it fans out to.

            A composite's sub-refs are resolved relative to the source that OWNS the
            composite (same rule as consolidation). ``seen`` guards against a reference
            cycle between two composites."""
            if ref.lower() in DEFAULT_TRIGGER_SYSTEM:
                return True
            try:
                src, resolved_name = resolve_reference(ref, source, trig_avail)
            except KeyError:
                # escape(): unlike entity names, references are not charset-validated.
                logger.error(f"Profile '{origin}' references unknown trigger '{escape(ref)}'")
                return False
            key = (src, resolved_name)
            if key in seen:
                return True
            seen.add(key)
            trig = self.__triggers[src][resolved_name]
            if not isinstance(trig, CompositeTrigger):
                return True
            sub_valid = True
            for item in trig.trigger.triggers:
                if isinstance(item, str):
                    sub_ref: Optional[str] = item
                elif isinstance(item, dict) and isinstance(item.get("trigger"), str):
                    sub_ref = item["trigger"]
                else:
                    # Inline/anonymous trigger object — nothing to resolve.
                    continue
                assert sub_ref is not None
                if not validate_trigger_ref(sub_ref, src, origin, seen):
                    sub_valid = False
            return sub_valid

        for source_key, profiles in self._profiles.items():
            for name, profile in profiles.items():
                origin_label = f"{source_key}.{name}"
                for rule in profile.rules:
                    # Rule triggers are either a List[str] or ProfileRuleTriggers (operator/refs)
                    t_refs = rule.triggers if isinstance(rule.triggers, list) else rule.triggers.refs
                    for t_ref in t_refs:
                        if not validate_trigger_ref(t_ref, source_key, origin_label, set()):
                            valid = False
                    for a_ref in rule.actions:
                        try:
                            resolve_reference(a_ref, source_key, act_avail)
                        except KeyError:
                            # escape() for the reason the trigger arm above states.
                            logger.error(f"Profile '{source_key}.{name}' references unknown action '{escape(a_ref)}'")
                            valid = False
        return valid

    @staticmethod
    def __read_commit_sha(root: Path) -> Optional[str]:
        """Return the HEAD commit SHA of an on-disk git checkout, or None.

        Read synchronously via GitPython so it is usable from the sync
        consolidation path: ``get_consolidated_config`` runs under the app's
        asyncio loop, where ``GitUtils``' async ``initialize()`` is unavailable,
        and this file is the only module in scope. Mirrors
        ``GitUtils.get_commit_sha()`` (HEAD hexsha read from disk).
        """
        try:
            from git import Repo
            return Repo(str(root)).head.commit.hexsha
        except Exception as e:
            logger.debug(f"Unable to read commit SHA for sentinel source at {root}: {e}")
            return None

    def __build_meta_sources(self) -> Dict[str, Dict[str, Any]]:
        """Build the inert ``_meta.sources`` provenance block for every loaded source.

        For each source records ``type`` (git|path), ``url``/``path``, ``ref`` and
        ``commit``; ``commit`` is the HEAD SHA read from the on-disk git checkout
        at consolidation time and is ``None`` for local ``path:`` sources.
        """
        # Captured in __init__ (empty for a self-contained manager) — never re-reads the
        # global UserConfig, and no bare `except Exception: pass` hiding real errors.
        configured = self._configured_sources
        meta: Dict[str, Dict[str, Any]] = {}
        for source_key, root in self.__source_roots.items():
            spec = configured.get(source_key, {})
            if not isinstance(spec, dict):
                spec = {}
            is_git = (root / ".git").exists()
            if is_git:
                meta[source_key] = {
                    "type": "git",
                    # Credential-safe: the raw URL may embed an HTTPS token, and this block is
                    # bind-mounted into the container and shipped to the SIEM, where no
                    # credential may leak.
                    "url": sanitize_source_url(spec.get("git") or spec.get("url")),
                    "ref": spec.get("ref"),
                    "commit": self.__read_commit_sha(root),
                }
            else:
                meta[source_key] = {
                    "type": "path",
                    "path": str(root),
                    "ref": None,
                    "commit": None,
                }
        return meta

    def get_default_config(self) -> Dict:
        """Build the deployed config for a Sentinel container that has no profile.

        Same outer shape as ``get_consolidated_config`` — a ``profile`` node with a
        complete ``config`` block, empty ``rules``/``triggers``/``actions`` and the inert
        ``_meta`` sibling — so the in-container config read finds ``profile.config.log_output``
        whether or not a profile resolved. Without it the spawn.sh recorder gate would decide
        on a missing file and the machine default from ``sentinel.log_output`` would be
        unreachable.

        Built here rather than in ``ContainerConfig`` so the ``_meta`` assembly and the
        default blocks cannot drift between the two paths.
        """
        return {
            "profile": {
                "rules": [],
                "config": {
                    # Copies, never the shared dicts — same idiom as the backfill in
                    # get_consolidated_config: a later mutation of one container's config
                    # must not be able to reach into this manager's defaults.
                    "log_rotation": dict(self.__default_log_rotation),
                    "log_output": dict(self.__default_log_output),
                },
            },
            "triggers": {},
            "actions": {},
            # No profile means no source contributed anything to this config, so an empty
            # sources map is the honest provenance; the block's SHAPE stays identical to
            # the profile path's, which is what the SIEM side keys off.
            "_meta": {"sources": self.__build_meta_sources()},
        }

    def get_consolidated_config(self, profile_name: str, current_source: Optional[str] = None) -> Optional[Dict]:
        """
        Generate a consolidated configuration for a specific profile.

        References are resolved host-side into flattened ``"<sourcekey>.<name>"``
        keys (the runner treats them as opaque dict keys) so same-named
        cross-source triggers/actions never collide. Only required triggers/actions
        are emitted, and an inert ``_meta`` provenance sibling is attached.
        """
        if current_source is None:
            resolved = self.resolve_profile_selection(profile_name)
            if resolved is None:
                return None
            current_source, profile_name = resolved
        elif profile_name not in self._profiles.get(current_source, {}):
            logger.error(f"Sentinel profile '{current_source}.{profile_name}' not found.")
            return None
        target_profile = self._profiles[current_source][profile_name]

        trig_avail: Dict[str, Set[str]] = {src: set(m.keys()) for src, m in self.__triggers.items()}
        act_avail: Dict[str, Set[str]] = {src: set(m.keys()) for src, m in self.__actions.items()}

        # Flattened-key stores of the entries actually required by this profile.
        required_triggers: Dict[str, Dict] = {}
        required_actions: Dict[str, Dict] = {}
        visited: Set[Tuple[str, str]] = set()

        def flat(src: str, name: str) -> str:
            return f"{src}.{name}"

        def resolve_trigger_ref(ref: str, source: str) -> Optional[str]:
            """Resolve a trigger ref to a flattened key, collecting it (and any
            composite sub-triggers) into ``required_triggers``. Defaults pass through."""
            if ref.lower() in DEFAULT_TRIGGER_SYSTEM:
                return ref
            try:
                src, name = resolve_reference(ref, source, trig_avail)
            except KeyError:
                # escape(): a MarkupError here would abort container creation.
                logger.error(f"Profile '{current_source}.{profile_name}' references unknown trigger '{escape(ref)}'")
                return None
            fkey = flat(src, name)
            key = (src, name)
            if key not in visited:
                visited.add(key)
                trig = self.__triggers[src][name]
                dumped = trig.model_dump()
                # Rewrite composite sub-refs to flattened keys, resolved relative to
                # the source that OWNS this composite trigger.
                if isinstance(trig, CompositeTrigger):
                    sub_list = dumped.get("trigger", {}).get("triggers", [])
                    new_sub: List[Any] = []
                    for item in sub_list:
                        if isinstance(item, str):
                            resolved = resolve_trigger_ref(item, src)
                            if resolved is None:
                                # Fail closed: keeping an unresolvable sub-ref would let the
                                # runner silently drop it, turning an AND composite into a
                                # more permissive one and an OR composite into a narrower one.
                                return None
                            new_sub.append(resolved)
                        elif isinstance(item, dict) and isinstance(item.get("trigger"), str):
                            resolved = resolve_trigger_ref(item["trigger"], src)
                            if resolved is None:
                                return None
                            new_sub.append({"trigger": resolved})
                        else:
                            # Inline/anonymous trigger dict — kept verbatim.
                            new_sub.append(item)
                    dumped["trigger"]["triggers"] = new_sub
                required_triggers[fkey] = dumped
            return fkey

        def resolve_action_ref(ref: str) -> Optional[str]:
            try:
                src, name = resolve_reference(ref, current_source, act_avail)
            except KeyError:
                # escape(), same reason as the trigger arm above.
                logger.error(f"Profile '{current_source}.{profile_name}' references unknown action '{escape(ref)}'")
                return None
            fkey = flat(src, name)
            if fkey not in required_actions:
                required_actions[fkey] = self.__actions[src][name].model_dump()
            return fkey

        # Rewrite every rule's trigger/action refs to their flattened keys.
        # Fail closed: an unresolvable ref aborts the whole consolidation rather than being
        # filtered out of the emitted rule. Silently dropping a condition mutates the rule's
        # meaning — an AND rule becomes MORE permissive (actions fire on commands they were
        # never meant to) and an OR rule loses audit coverage — while still deploying a
        # config that looks valid. For an audit system that is a correctness failure.
        new_rules: List[Dict[str, Any]] = []
        for rule in target_profile.rules:
            if isinstance(rule.triggers, list):
                new_trigs = [resolve_trigger_ref(r, current_source) for r in rule.triggers]
                if any(t is None for t in new_trigs):
                    logger.error(f"Sentinel profile '{current_source}.{profile_name}' has a rule with an unresolvable "
                                 f"trigger reference; refusing to generate a partial configuration.")
                    return None
                rule_triggers_out: Any = new_trigs
            else:
                new_refs = [resolve_trigger_ref(r, current_source) for r in rule.triggers.refs]
                if any(t is None for t in new_refs):
                    logger.error(f"Sentinel profile '{current_source}.{profile_name}' has a rule with an unresolvable "
                                 f"trigger reference; refusing to generate a partial configuration.")
                    return None
                rule_triggers_out = {"operator": rule.triggers.operator, "refs": new_refs}
            new_actions = [resolve_action_ref(a) for a in rule.actions]
            if any(a is None for a in new_actions):
                logger.error(f"Sentinel profile '{current_source}.{profile_name}' has a rule with an unresolvable "
                             f"action reference; refusing to generate a partial configuration.")
                return None
            new_rules.append({"triggers": rule_triggers_out, "actions": new_actions})

        profile_dump = target_profile.model_dump()
        profile_dump["rules"] = new_rules

        consolidated: Dict[str, Any] = {
            "profile": profile_dump,
            "triggers": required_triggers,
            "actions": required_actions,
        }

        # always emit a complete profile.config.log_rotation block so the in-container
        # script receives valid rotation settings even from config-less or older profiles.
        # When the profile provides its own log_rotation block, model_dump() already preserved it.
        if target_profile.config is None:
            consolidated["profile"]["config"] = {}
        if target_profile.config is None or target_profile.config.log_rotation is None:
            # Captured in __init__ so a self-contained manager never touches the user's config.
            consolidated["profile"]["config"]["log_rotation"] = dict(self.__default_log_rotation)
        # Same all-or-nothing precedence for log_output: the in-container logger reads
        # one config, so a config-less or older profile must still receive a complete
        # block rather than fall back to defaults hidden in the container script.
        if target_profile.config is None or target_profile.config.log_output is None:
            consolidated["profile"]["config"]["log_output"] = dict(self.__default_log_output)

        # Inert SIEM-facing provenance sibling; the runner ignores unknown top-level
        # keys, so the flat container contract is unchanged.
        consolidated["_meta"] = {"sources": self.__build_meta_sources()}
        return consolidated
