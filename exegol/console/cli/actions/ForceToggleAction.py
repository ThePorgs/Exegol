import argparse
from typing import Any, List, Optional, Sequence, Set, Union


class ForceToggleAction(argparse.Action):
    """store_true / store_false on ONE dest: ``--log`` writes ``True``, ``--no-log`` writes ``False``.

    ``default=None`` keeps the tri-state, so the profile, config.yml and builtin tiers stay
    reachable when neither half is typed. ``nargs=0`` stops a bare short flag from consuming
    the next token (``exegol start -S mycontainer``).

    Supplying both halves is refused via ``parser.error()`` (exit code 2). Stock
    ``BooleanOptionalAction`` is not reused because it resolves a contradiction last-wins.
    """

    #: Prefix of the negative spelling. Short flags are only declared on the positive half.
    NEGATIVE_PREFIX = "--no-"

    def __init__(self,
                 option_strings: Sequence[str],
                 dest: str,
                 default: Optional[bool] = None,
                 required: bool = False,
                 help: Optional[str] = None) -> None:
        """Register every spelling of one pair against a single dest."""
        self.__negatives: Set[str] = {option for option in option_strings
                                      if option.startswith(self.NEGATIVE_PREFIX)}
        super().__init__(option_strings=list(option_strings),
                         dest=dest,
                         nargs=0,
                         default=default,
                         required=required,
                         help=help)

    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 values: Union[str, Sequence[Any], None],
                 option_string: Optional[str] = None) -> None:
        """Write the typed direction to the dest, refusing a contradictory command line.

        Repeating the same half is a no-op. The refusal happens at parse time, before any
        Docker call.
        """
        # Unreachable through `parse_args()`; the direction is carried by the spelling, so refuse.
        if option_string is None:
            raise ValueError(f"{type(self).__name__} was invoked with no option string, so the "
                             f"direction of '{self.dest}' cannot be read. The direction of a "
                             f"toggle is carried by the spelling that was typed.")
        direction = option_string not in self.__negatives
        current = getattr(namespace, self.dest, None)
        if current is not None and current != direction:
            opposite = "/".join(option for option in self.option_strings
                                if (option in self.__negatives) is direction)
            parser.error(f"argument {'/'.join(self.option_strings)}: both directions supplied "
                         f"({option_string} contradicts the earlier {opposite}); "
                         f"a toggle cannot be forced on and off at once, pick one.")
        setattr(namespace, self.dest, direction)

    def negativeOf(self, option_string: str) -> Optional[str]:
        """The declared negative sibling of one long positive spelling, if there is one."""
        candidate = f"{self.NEGATIVE_PREFIX}{option_string[2:]}"
        return candidate if candidate in self.__negatives else None

    def positiveSpellings(self) -> List[str]:
        """Every spelling of this pair that means "enable", in declaration order."""
        return [option for option in self.option_strings if option not in self.__negatives]
