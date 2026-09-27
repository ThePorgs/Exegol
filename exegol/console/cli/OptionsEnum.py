from enum import Enum
from typing import List, Optional


class SentinelUpdateStrategy(Enum):
    """Sentinel per-container config update strategy.

    ``value`` is the stable internal key persisted in the immutable container label and in
    ``config.yml``; ``display`` is the human-facing name. Using the enum everywhere avoids
    hardcoded ``"on_restart"`` / ``"disabled"`` string literals in comparisons across the code.
    """
    ON_RESTART = "on_restart"
    DISABLED = "disabled"

    @property
    def display(self) -> str:
        return {
            SentinelUpdateStrategy.ON_RESTART: "On restart",
            SentinelUpdateStrategy.DISABLED: "Disabled",
        }[self]

    @classmethod
    def values(cls) -> List[str]:
        """Ordered list of the valid internal keys (usable as argparse/validation choices)."""
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: Optional[str]) -> Optional["SentinelUpdateStrategy"]:
        """Resolve an internal key back to its enum member, or None if unknown/absent."""
        for member in cls:
            if member.value == value:
                return member
        return None
