import argparse
from logging import CRITICAL

from wrapper.utils.ExeLog import logger


# Argparse overriding
class ExegolArgParse(argparse.ArgumentParser):
    # Using Exelog to print built-in parser message
    def _print_message(self, message, file=None):
        if message:
            logger.raw(message, level=CRITICAL, rich_parsing=True)


class Parser:
    __description = "This Python script is a wrapper for Exegol. It can be used to easily manage Exegol on " \
                    "your machine."
    __examples = {
        "install (↓ ~15GB max)": "exegol install",
        "check image updates": "exegol info",
        "get a shell\t": "exegol start",
        "run as daemon\t": "exegol exec -e bloodhound",
        "get a tmux shell": "exegol --shell tmux start",
        "use wifi/bluetooth": "exegol --privileged start",
        "use a Proxmark": "exegol --device /dev/ttyACM0 start",
        "use a LOGITacker": "exegol --device /dev/ttyACM0 start",
        "use an ACR122u": "exegol --device /dev/bus/usb/ start",
        "use an HackRF One": "exegol --device /dev/bus/usb/ start",
        "use an Crazyradio PA": "exegol --device /dev/bus/usb/ start",
    }

    def __init__(self, actions):

        self.__actions = actions

        self.parser = None
        self.__init_parser()
        self.__set_positionals()
        self.__set_options(self.parser)

    def __init_parser(self):
        epilog = "[bold green]Examples:[/bold green]\n"
        for k, v in self.__examples.items():
            epilog += "  {}\t{}\n".format(k, v)

        self.parser = ExegolArgParse(
            description=self.__description,
            epilog=epilog,
            formatter_class=argparse.RawTextHelpFormatter,
        )

    def __set_positionals(self):
        self.parser._positionals.title = "[bold green]Required arguments[/bold green]"
        self.subParser = self.parser.add_subparsers(help="Commands help")
        for action in self.__actions:
            sp = self.subParser.add_parser(action.name, help=action.__doc__)
            sp.set_defaults(action=action)
            self.__set_options(sp, target=[action])

    def __set_options(self, parser, target=None):
        global_set = False
        target = target if target else self.__actions
        for action in target:
            for groupArgs in action.groupArg:
                if groupArgs.is_global and not global_set:
                    global_set = True
                    parser._optionals.title = groupArgs.title
                    arg_group = parser
                else:
                    arg_group = parser.add_argument_group(groupArgs.title, description=groupArgs.description)
                for option in groupArgs.options:
                    try:
                        option = option["arg"]
                        arg_group.add_argument(*option.args, **option.kwargs)
                    except argparse.ArgumentError:
                        continue

    def get_parameters(self):
        options = self.parser.parse_args()
        return options
