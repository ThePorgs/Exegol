#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from wrapper.utils.ExeLog import logger, console
from wrapper.console.ExegolController import ExegolController
from wrapper.console.ExegolArgs import ParametersManager

# logger.setLevel(logging.getLevelName("VERBOSE"))
logger.setLevel(logging.DEBUG)


def main():
    ctrl = ExegolController()
    param = ParametersManager()
    print(param.verbosity)
    pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Exiting")
    except Exception:
        console.print_exception(show_locals=True)
