#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.manager.ExegolController import ExegolController
from wrapper.utils.ExeLog import logger, console, ExeLog


def main():
    # Start Main controller
    ctrl: ExegolController = ExegolController()
    # Get Parameters singleton
    param: ParametersManager = ParametersManager()
    # Set logger verbosity depending on user input
    ExeLog.setVerbosity(param.verbosity, param.quiet)
    # Executing action selected by user CLI
    ctrl.call_action()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.empty_line()
        logger.info("Exiting")
    except Exception:
        console.print_exception(show_locals=True)
