import rich.prompt
from rich.text import TextType

from exegol.utils.ExeLog import console, ConsoleLock


class ExegolRich:

    # These methods cannot be run from another Thread

    @staticmethod
    async def Ask(prompt: TextType = "", **kwargs) -> str:
        """Quick function to format rich Prompt and options on every exegol interaction"""
        async with ConsoleLock:
            return rich.prompt.Prompt.ask(prompt, console=console, **kwargs)

    @staticmethod
    async def Confirm(question: str, default: bool) -> bool:
        """Quick function to format rich Confirmation and options on every exegol interaction"""
        default_text = "[bright_magenta][Y/n][/bright_magenta]" if default else "[bright_magenta]\\[y/N][/bright_magenta]"
        formatted_question = f"[bold blue][?][/bold blue] {question} {default_text}"
        async with ConsoleLock:
            return rich.prompt.Confirm.ask(
                formatted_question,
                show_choices=False,
                show_default=False,
                console=console,
                default=default)

    @staticmethod
    async def Acknowledge(message: str) -> None:
        """Quick function to format rich Confirmation and options on every exegol interaction"""
        formatted_question = f"[bold blue][>][/bold blue] {message} [bright_magenta][Press ENTER to acknowledge][/bright_magenta]"
        async with ConsoleLock:
            rich.prompt.Prompt.ask(
                formatted_question,
                show_choices=False,
                show_default=False,
                console=console)
