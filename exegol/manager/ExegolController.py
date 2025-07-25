import asyncio
import http
import logging

try:
    import docker
    import git
    import requests
    import urllib3
    import supabase
    import httpx
    import postgrest
    import contextlib

    from exegol.utils.ExeLog import logger, ExeLog, console
    from exegol.utils.DockerUtils import DockerUtils
    from exegol.console.cli.ParametersManager import ParametersManager
    from exegol.console.cli.actions.ExegolParameters import Command
    from exegol.manager.ExegolManager import ExegolManager
    from exegol.manager.TaskManager import TaskManager
    from exegol.utils.SessionHandler import SessionHandler
except ModuleNotFoundError as e:
    print("Mandatory dependencies are missing:", e)
    print("Please install them with python3 -m pip install --upgrade -r requirements.txt")
    exit(1)
except ImportError as e:
    print("An error occurred while loading the dependencies!")
    print()
    if "git executable" in e.msg:
        print("Git is missing in your PATH, it must be installed locally on your computer.")
        print()
    print("Details:")
    print(e)
    exit(1)
except KeyboardInterrupt:
    exit(1)


class ExegolController:
    """Main controller of exegol"""

    # Get action selected by user
    # (ParametersManager must be loaded from ExegolController first to load every Command subclass)
    __action: Command = ParametersManager().getCurrentAction()

    @classmethod
    async def call_action(cls) -> int:
        """Dynamically retrieve the main function corresponding to the action selected by the user
        and execute it on the main thread"""
        try:
            await ExegolManager.print_version()
            DockerUtils()  # Init dockerutils
            await ExegolManager.print_debug_banner()
            # Check for missing parameters
            missing_params = cls.__action.check_parameters()
            if len(missing_params) == 0:
                # Fetch main operation function
                main_action = cls.__action()
                return_code = 0
                if main_action is not None:
                    TaskManager.add_task(
                        SessionHandler().reload_session(),
                        TaskManager.TaskId.LoadLicense)
                    # Execute main function
                    await main_action()
                await TaskManager.wait_for_all()
                return return_code
            else:
                # TODO review required parameters
                logger.error(f"These parameters are mandatory but missing: {','.join(missing_params)}")
                return 1
        except SystemExit as err:
            logger.empty_line()
            logger.info("Exiting...")
            await TaskManager.wait_for_all(exit_mode=True)
            return 1 if err.code is None else int(err.code)
        except (KeyboardInterrupt, asyncio.CancelledError, EOFError):
            logger.empty_line()
            logger.info("Exiting...")
            await TaskManager.wait_for_all(exit_mode=True)
            return 1


def print_exception_banner() -> None:
    logger.error("It seems that something unexpected happened ...")
    logger.error("To draw our attention to the problem and allow us to fix it, you can share your error with us "
                 "(by [orange3]copying and pasting[/orange3] it with this syntax: ``` <error> ```) "
                 "by creating a GitHub issue at this address: https://github.com/ThePorgs/Exegol/issues")
    logger.success("Thank you for your collaboration!")


def main() -> int:
    """Exegol main console entrypoint"""
    try:
        # Set logger verbosity depending on user input
        ExeLog.setVerbosity(ParametersManager().verbosity, ParametersManager().quiet)
        # Start Main controller & Executing action selected by user CLI
        return asyncio.run(ExegolController.call_action())
    except (KeyboardInterrupt, asyncio.CancelledError, EOFError):
        return 2
    except git.exc.GitCommandError as git_error:
        print_exception_banner()
        # Printing git stderr as raw to avoid any Rich parsing error
        logger.debug("Full git output:")
        logger.raw(git_error, level=logging.DEBUG)
        logger.empty_line()
        error = git_error.stderr.strip().split(": ")[-1].strip("'")
        logger.error("Git error received:")
        # Printing git error as raw to avoid any Rich parsing error
        logger.raw(error, level=logging.ERROR)
        logger.empty_line()
        logger.error(f"A critical error occurred while running this git command: {' '.join(git_error.command)}")
    except SystemExit as e:
        if e.code is not None:
            return int(e.code)
    except Exception:
        print_exception_banner()
        console.print_exception(show_locals=True, suppress=[docker, requests, git, urllib3, http, httpx, postgrest, contextlib, supabase, asyncio])
    return 1
