import argparse
from rich import print
from wrapper.utils.MetaSingleton import MetaSingleton
from wrapper.utils.ConstantConfig import ConstantConfig


class ExegolArgParse(argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        if message:
            print(message)


class Parser(metaclass=MetaSingleton):

    def __init__(self):
        self.__description = "This Python script is a wrapper for Exegol. It can be used to easily manage Exegol on " \
                           "your machine."
        self.examples = {
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
        self.__modes = {
            "release": "(default) downloads a pre-built image (from DockerHub) (faster)",
            "sources": "builds from the local sources in {} (pull from GitHub then docker build, local edits won't be overwritten)".format(
                ConstantConfig.root_path
            )
        }

        modes_help = ""
        for mode in self.__modes.keys():
            modes_help += f"{mode}\t\t{self.__modes[mode]}\n"

        self.__actions = {
            "start": "automatically start, resume, create or enter an Exegol container",
            "stop": "stop an Exegol container in a saved state",
            "install": "install Exegol image (build or pull depending on the chosen install --mode)",
            "update": "update Exegol image (build or pull depending on the chosen update --mode)",
            "remove": "remove Exegol image(s) and/or container(s)",
            "exec": "execute a command on an Exegol container",
            "info": "print info on containers and local & remote images (name, size, state, ...)",
            "version": "print current version",
        }
        self.__options = [
            {
                "title": "[blue]Optional arguments[/blue]",
                "description": "",
                "options": [
                    {
                        "args": ["-k", "--insecure"],
                        "kwargs": {
                            "dest": "verify",
                            "action": "store_false",
                            "default": True,
                            "required": False,
                            "help": "Allow insecure server connections for web requests (default: False)"
                        }
                    },
                    {
                        "args": ["-q", "--quiet"],
                        "kwargs": {
                            "dest": "quiet",
                            "action": "store_true",
                            "default": False,
                            "help": "show no information at all"
                        }
                    },
                    {
                        "args": ["-v", "--verbose"],
                        "kwargs": {
                            "dest": "verbosity",
                            "action": "count",
                            "default": 0,
                            "help": "verbosity level (-v for verbose, -vv for debug)"
                        }
                    }
                ]
            },
            {
                "target": ["start"],
                "title": "[blue]Default start options[/blue]",
                "description": 'The following options are enabled by default. They can all be disabled with the '
                               'advanced option "--no-default". They can then be enabled back separately, '
                               'for example "exegol --no-default --X11 start"',
                "options": [
                    {
                        "args": ["-x", "--x11"],
                        "kwargs": {
                            "action": "store_true",
                            "dest": "X11",
                            "help": "enable display sharing to run GUI-based applications",
                        }
                    },
                    {
                        "args": ["--host-timezones"],
                        "kwargs": {
                            "action": "store_true",
                            "dest": "host_timezones",
                            "help": "let the container share the host's timezones configuration",
                        }
                    },
                    {
                        "args": ["--host-network"],
                        "kwargs": {
                            "action": "store_true",
                            "dest": "host_network",
                            "help": "let the container share the host's timezones configuration",
                        }
                    },
                    {
                        "args": ["--bind-resource"],
                        "kwargs": {
                            "action": "store_true",
                            "dest": "bind_resources",
                            "help": f"mount the /opt/resources of the container in a subdirectory of host\'s {ConstantConfig.root_path + '/shared-resources'}",
                        }
                    },
                    {
                        "args": ["-s", "--shell"],
                        "kwargs": {
                            "dest": "shell",
                            "action": "store",
                            "choices": {"zsh", "bash", "tmux"},
                            "default": "zsh",
                            "help": "select shell to start when entering Exegol (Default: zsh)",
                        }
                    },
                    {
                        "args": ["-e", "--exec"],
                        "kwargs": {
                            "dest": "exec",
                            "action": "store",
                            "help": "execute a command on exegol container",
                        }
                    }
                ]
            },
            {
                "target": ["start"],
                "title": "[blue]Advanced start options[/blue]",
                "description": "",
                "options": [
                    {
                        "args": ["-t", "--container-tag"],
                        "kwargs": {
                            "dest": "containertag",
                            "action": "store",
                            "help": "tag to use in the container name"
                        }
                    },
                    {
                        "args": ["--no-default"],
                        "kwargs": {
                            "dest": "no_default",
                            "action": "store_true",
                            "default": False,
                            "help": "disable the default start options (e.g. --X11, --host-network)"
                        }
                    },
                    {
                        "args": ["--privileged"],
                        "kwargs": {
                            "dest": "privileged",
                            "action": "store_true",
                            "default": False,
                            "help": "(dangerous) give extended privileges at the container creation (e.g. needed to "
                                    "mount things, to use wifi or bluetooth) "
                        }
                    },
                    {
                        "args": ["-d", "--device"],
                        "kwargs": {
                            "dest": "device",
                            "action": "store",
                            "help": "add a host device at the container creation"
                        }
                    },
                    {
                        "args": ["-c", "--custom-options"],
                        "kwargs": {
                            "dest": "custom_options",
                            "action": "store",
                            "default": "",
                            "help": "specify custom options for the container creation"
                        }
                    },
                    {
                        "args": ["-cwd", "--cwd-mount"],
                        "kwargs": {
                            "dest": "mount_current_dir",
                            "action": "store_true",
                            "help": "mount current dir to container's /workspace"
                        }
                    }
                ]
            },
            {
                "target": ["install", "update"],
                "title": "[blue]Install/update options[/blue]",
                "description": "",
                "options": [
                    {
                        "args": ["-m", "--mode"],
                        "kwargs": {
                            "dest": "mode",
                            "action": "store",
                            "choices": self.__modes.keys(),
                            "default": "release",
                            "help": modes_help
                        }
                    }
                ]
            }
        ]

        self.__init_parser()
        self.__set_positionals()
        self.__set_options(self.parser)
        self.option = self.parser.parse_args()

    def __init_parser(self):
        epilog = "[bold green]Examples:[/bold green]\n"
        for example in self.examples.keys():
            epilog += "  {}\t{}\n".format(example, self.examples[example])

        self.parser = ExegolArgParse(
            description=self.__description,
            epilog=epilog,
            formatter_class=argparse.RawTextHelpFormatter,
        )

    def __set_positionals(self):
        self.parser._positionals.title = "[bold green]Required arguments[/bold green]"
        self.subParser = self.parser.add_subparsers(help="Commands help")
        for action in self.__actions.keys():
            sp = self.subParser.add_parser(action, help=self.__actions[action])
            sp.set_defaults(action=action)
            self.__set_options(sp, action)
        pass

    def __set_options(self, parser, target=None):
        for options in self.__options:
            if "target" not in options:
                parser._optionals.title = options["title"]
                for option in options["options"]:
                    parser.add_argument(*option["args"], **option["kwargs"])
            if "target" in options and (target in options["target"] or not target):
                arg_group = parser.add_argument_group(options["title"], description=options["description"])
                for option in options["options"]:
                    arg_group.add_argument(*option["args"], **option["kwargs"])