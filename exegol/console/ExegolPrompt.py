import rich.prompt


def Confirm(question: str, default: bool) -> bool:
    """Quick function to format rich Confirmation and options on every exegol interaction"""
    default_text = "[bright_magenta][Y/n][/bright_magenta]" if default else "[bright_magenta]\[y/N][/bright_magenta]"
    formatted_question = f"[bold blue][?][/bold blue] {question} {default_text}"
    return rich.prompt.Confirm.ask(
        formatted_question,
        show_choices=False,
        show_default=False,
        default=default)
