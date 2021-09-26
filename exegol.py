#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from wrapper.utils.ExeLog import logger, console

# logger.setLevel(logging.getLevelName("VERBOSE"))
logger.setLevel(logging.DEBUG)


def main():
    pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Exiting")
    except Exception:
        console.print_exception(show_locals=True)
