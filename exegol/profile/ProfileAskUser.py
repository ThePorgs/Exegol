"""Ask the operator for a value a container profile declared a policy about.

``network.hostname_ask_user`` and ``metadata.comment_ask_user`` do not carry a value: each
says that the value of the field beside it (``network.hostname`` / ``metadata.comment``)
should be asked for at container creation, with the profile's own declared value offered as
the prompt default. That lets a shared profile carry a naming policy ("always name the box
for the engagement") without freezing one operator's answer into every container.

Both keys go through the single helper below, so the two cannot drift into two different
notions of "ask".
"""

from typing import Optional

from exegol.config.OptionResolver import OptionKey, OptionResolver, OptionSource
from exegol.console.ExegolPrompt import ExegolRich, stdinCanAnswer
from exegol.utils.ExeLog import logger


async def ask_user_for_value(ask_key: OptionKey,
                             value_key: OptionKey,
                             prompt: str,
                             fallback_default: Optional[str] = None) -> Optional[str]:
    """Return the value for ``value_key``, asking the operator when ``ask_key`` says to.

    ``prompt`` is a literal: no operator-supplied value is ever interpolated into it.
    ``ExegolRich.Ask`` renders its prompt through ``Text.from_markup``, so a ``[`` in a
    third-party profile's value would be parsed as markup and an unmatched tag would raise
    ``MarkupError`` out of container creation. The ``default=`` path is safe because rich
    builds it with ``Text(f"({default})")``, which is not markup-parsed. Any future
    interpolation into the prompt string must go through ``rich.markup.escape`` first.
    """
    resolved = OptionResolver().resolve(value_key)

    # A CLI-tier test, deliberately: the operator already answered by typing the flag, so
    # there is nothing left to ask. `isExplicitOrProfile()` would be wrong here (it reports
    # True for a present key, so an explicitly-written YAML null would read as an answer),
    # and `Resolved.stated` would be wrong too (it is true for a profile-supplied value,
    # which is precisely the case that should still prompt — that value is the offered
    # default).
    if resolved.source is OptionSource.CLI:
        return resolved.value

    # Presence is not the question: a written null resolves to None and correctly means
    # "do not ask", as does an omitted key falling through to `builtin_default=False`.
    if not OptionResolver().get(ask_key):
        return resolved.value

    # The wrapper's single terminal gate. A shared profile setting an ask flag would
    # otherwise hang a scripted `exegol start` on a read from a stdin nobody is typing into.
    if not stdinCanAnswer():
        logger.verbose(f"Profile asks for [blue]{value_key.value}[/blue], but stdin cannot answer: "
                       f"keeping the value that would otherwise apply.")
        return resolved.value

    default = resolved.value if resolved.value else fallback_default
    if default:
        return await ExegolRich.Ask(prompt, default=default)
    return await ExegolRich.Ask(prompt)
