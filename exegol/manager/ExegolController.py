from exegol.console.cli.ParametersManager import ParametersManager
from exegol.console.cli.actions.ExegolParameters import Command
from exegol.utils.ExeLog import logger, ExeLog, console


class ExegolController:
    """Main controller of exegol"""

    # Get action selected by user
    # (ParametersManager must be loaded from ExegolController first to load every Command subclass)
    __action: Command = ParametersManager().getCurrentAction()

    @classmethod
    def call_action(cls):
        """Dynamically retrieve the main function corresponding to the action selected by the user
        and execute it on the main thread"""
        # Check for missing parameters
        missing_params = cls.__action.check_parameters()
        if len(missing_params) == 0:
            # Fetch main operation function
            main_action = cls.__action()
            # Execute main function
            main_action()
        else:
            # TODO review required parameters
            logger.error(f"These parameters are mandatory but missing: {','.join(missing_params)}")


def main():
    """Exegol main console entrypoint"""
    try:
        # Set logger verbosity depending on user input
        ExeLog.setVerbosity(ParametersManager().verbosity, ParametersManager().quiet)
        # Start Main controller & Executing action selected by user CLI
        ExegolController.call_action()
    except KeyboardInterrupt:
        logger.empty_line()
        logger.info("Exiting")
    except Exception:
        logger.error("It seems that something unexpected happened ...")
        logger.error("To draw our attention to the problem and allow us to fix it, you can share your error with us (by [orange3]copying and pasting[/orange3] it with this syntax: ``` <error> ```) by creating a GitHub issue at this address: https://github.com/ShutdownRepo/Exegol/issues")
        logger.success("Thank you for your collaboration!")
        console.print_exception(show_locals=True)
