#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.manager.ExegolController import ExegolController
from wrapper.utils.ExeLog import logger, console, ExeLog


def main():
    # Set logger verbosity depending on user input
    ExeLog.setVerbosity(ParametersManager().verbosity, ParametersManager().quiet)
    # Start Main controller & Executing action selected by user CLI
    ExegolController.call_action()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.empty_line()
        logger.info("Exiting")
    except Exception:
        console.print_exception(show_locals=True)
