from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from rich.markup import escape

from exegol.model.SelectableInterface import SelectableInterface

if TYPE_CHECKING:
    # Avoids importing exegol.profile (and UserConfig()) at import time.
    from exegol.profile.ContainerProfile import ContainerProfile


class ContainerProfileSelectable(SelectableInterface):
    """Pairs a container profile with its name so the TUI picker can select it by ``getKey()``.

    Kept behaviour-free: the named ``--profile <name>`` path never builds this wrapper, so any
    logic added here would make the two selection paths diverge.
    """

    def __init__(self, source_key: str, name: str, profile: "ContainerProfile",
                 qualified: bool = False, source_label: Optional[str] = None) -> None:
        self.source_key: str = source_key
        self.name: str = name
        self.profile: "ContainerProfile" = profile
        # True when the bare name is ambiguous across sources (computed by wrapNamespaced).
        self.qualified: bool = qualified
        # Pre-rendered (escaped, colour-tagged) Source cell, or None.
        self.source_label: Optional[str] = source_label

    def getSourceLabel(self) -> str:
        """Return the table-ready Source cell: the rendered label if supplied, else the escaped key.

        Always already escaped, so the table builder must not escape it again.
        """
        if self.source_label is not None:
            return self.source_label
        return escape(self.source_key)

    @classmethod
    def wrapNamespaced(cls, profiles_by_source: Dict[str, Dict[str, "ContainerProfile"]],
                       render_source: Optional[Callable[[str], str]] = None) -> List["ContainerProfileSelectable"]:
        """Wrap a ``{source_key: {name: profile}}`` namespace, qualifying ambiguous names.

        Uses the same uniqueness rule as ``resolve_profile_selection()`` so the picker and
        ``--profile <name>`` agree. Input order is kept (already sorted by the manager).
        """
        owners: Dict[str, int] = {}
        for mapping in profiles_by_source.values():
            for name in mapping:
                owners[name] = owners.get(name, 0) + 1
        # One label per source, not per profile.
        labels = ({source_key: render_source(source_key) for source_key in profiles_by_source}
                  if render_source is not None else {})
        return [cls(source_key, name, profile, qualified=owners[name] > 1,
                    source_label=labels.get(source_key))
                for source_key, mapping in profiles_by_source.items()
                for name, profile in mapping.items()]

    def getKey(self) -> str:
        """Universal unique key getter (from SelectableInterface).

        The bare name when unique across sources, ``source_key.name`` otherwise.
        """
        if self.qualified:
            return f"{self.source_key}.{self.name}"
        return self.name

    def getDescription(self) -> str:
        """Return the profile's description, or ``""`` when there is no metadata or no description.

        This is ``metadata.description`` — what the PROFILE is for — and NOT ``metadata.comment``,
        which is the CONTAINER's own comment (``OptionKey.COMMENT``), applied to every container
        the profile creates.

        Returned raw (unescaped): escaping happens at the Rich rendering site.
        """
        if self.profile.metadata is None or self.profile.metadata.description is None:
            return ""
        return self.profile.metadata.description
