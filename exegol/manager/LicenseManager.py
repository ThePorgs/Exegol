import platform
import time
from time import sleep
from typing import Dict, Optional, cast, Tuple

from rich.markdown import Markdown
from supabase import AsyncClient

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.console.ConsoleFormat import get_display_date
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.TUI import ExegolTUI
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.manager.TaskManager import TaskManager
from exegol.model.LicensesTypes import LicensesEnumeration, LicenseType, LicenseEnrollment, EnrollmentForm
from exegol.utils.ExeLog import logger, console
from exegol.utils.LocalDatastore import LocalDatastore
from exegol.utils.MUID import MUID
from exegol.utils.SessionHandler import SessionHandler
from exegol.utils.SupabaseUtils import SupabaseUtils


class LicenseManager:
    __singleton_instance: Optional["LicenseManager"] = None

    def __init__(self) -> None:
        self.__session = SessionHandler()
        self.__user_session: Optional[AsyncClient] = None

    @classmethod
    async def get(cls) -> "LicenseManager":
        if cls.__singleton_instance is None:
            cls.__singleton_instance = cls()
            if not LocalDatastore().is_eula_accepted():
                await cls.__singleton_instance.eula_process()
                # For non-interactive commands skip first-time activation
                if not ParametersManager().accept_eula:
                    await cls.__singleton_instance.activate_exegol()
                else:
                    cls.__singleton_instance.__session.display_license()
            else:
                cls.__singleton_instance.__session.display_license()
        return cls.__singleton_instance

    async def eula_process(self) -> None:
        if not ParametersManager().accept_eula:
            while not await ExegolRich.Confirm("I confirm that I've read and accepted the EULA (https://docs.exegol.com/legal/eula)", default=False):
                await self.display_eula()
        LocalDatastore().update_eula(True)

    async def activate_exegol(self, skip_prompt: bool = False) -> None:
        # Do you want to activate your Exegol?
        if skip_prompt or await ExegolRich.Confirm("Do you want to activate your Exegol subscription now?", default=False):
            try:
                if await self.enroll_machine():
                    await self.__session.reload_session()
            except KeyboardInterrupt as e:
                if self.__user_session is not None:
                    await self.__user_session.auth.sign_out({"scope": "local"})
                raise e
        else:
            LocalDatastore().update_eula(False)
            logger.warning("[green]Community[/green] plan (i.e., free) is strictly limited to personal, non-commercial, educational, or research purposes.")
            sleep(1)
            if not await ExegolRich.Confirm("I confirm that I'm not trying to rip off the developers, who put their blood, sweat, and tears into Exegol, and that I would absolutely support the project if I were using it professionally. I'm not *that* kind of person.", default=False):
                logger.error("Wrong answer")
                while True:
                    logger.error("PUNK!")
                    sleep(1)
            logger.success("You can now use Exegol [green]Community[/green] Edition! Enjoy :)")
            LocalDatastore().update_eula(True)
        self.__session.display_license(as_info=True)

    async def revoke_exegol(self) -> None:
        if self.__session.is_enrolled():
            logger.warning("You are about to revoke your Exegol license. This action cannot be undone.")
            logger.warning("If you've recently enrolled this machine, you [red]won't[/red] be able to reuse this license immediately on another machine.")
            if await ExegolRich.Confirm("Are you sure you want to revoke your license locally?", default=False):
                await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
                LocalDatastore().deactivate_license()
                logger.success("Exegol license successfully revoked.")
        else:
            logger.info("You don't have an active license to revoke.")

    def is_activated(self) -> bool:
        """Check if a valid license is available (license binding to an expired license while return False)"""
        return self.__session.get_license_type() != LicenseType.Community

    @staticmethod
    async def display_eula() -> None:
        if await ExegolRich.Confirm("Do you want to display EULA here?", default=True):
            # Display EULA
            with open(ConstantConfig.eula_path, 'r') as f:
                markdown = Markdown(f.read())
            console.print(markdown)

    async def enroll_machine(self) -> bool:
        # Login
        self.__user_session = await SupabaseUtils.login_user()
        # Enum license
        licenses_enum: Dict[str, LicensesEnumeration] = await SupabaseUtils.enum_licenses(self.__user_session.functions)

        if len(licenses_enum) == 0:
            logger.error("No active licenses assigned to this user are available.")
            return False
        # Select license variables
        selected_license_id: Optional[str] = None
        selected_license: Optional[Dict] = None
        revoke_previous_machine = False

        # Convert and process license ID and ISO datetime to printable date format
        table_data = {}
        id_match = {}
        i = 0
        for current_id, current_license in licenses_enum.items():
            i += 1
            current_license["valid_until"] = get_display_date(current_license["valid_until"])
            if current_license["last_seen"]:
                current_license["last_seen"] = get_display_date(current_license["last_seen"])
            table_data[str(i)] = current_license
            id_match[str(i)] = current_id

        while True:
            while selected_license_id is None:
                selected_license_id, selected_license = cast(Tuple[str, Dict],
                                                             await ExegolTUI.selectFromList(table_data, subject="a license ID", title="Select a license to enroll Exegol", default="1"))

                if selected_license.get("enrolled_on", ""):
                    logger.warning(f"The selected license is already used by another machine: [green]{selected_license.get('enrolled_on')}[/green]")
                    if not await ExegolRich.Confirm(f"Do you want to [red]revoke[/red] the license on [green]{selected_license.get('enrolled_on')}[/green] ?", default=True):
                        selected_license_id = None
                    else:
                        revoke_previous_machine = True
            if selected_license is None:
                logger.critical("No license was selected. Exiting.")
                raise CancelOperation
            try:
                # Check if the license type is known to the wrapper
                LicenseType[selected_license.get("type", "Unknown")]
            except KeyError as e:
                logger.critical("This license type is not supported the current version of the wrapper. Please update your wrapper first.")
                raise e
            try:
                current_os = EnvInfo.getHostOs().value.lower()
            except RuntimeError:
                # Fallback mthd if docker not yet init
                current_os = platform.system().lower()
                if current_os == "darwin":
                    current_os = "Mac"
            # Enroll
            enroll_form: EnrollmentForm = {
                "machine_id": MUID.get_current_muid(),
                "machine_name": platform.node(),
                "machine_os": current_os,
                "license_id": id_match[selected_license_id],
            }
            if revoke_previous_machine:
                enroll_form["revoke_previous_machine"] = True
            try:
                enrollment_response: LicenseEnrollment = await SupabaseUtils.activate_licenses(self.__user_session.functions, enroll_form)
                # Save license session
                if enrollment_response.get("next_token") is not None:
                    LocalDatastore().set(LocalDatastore.Key.TOKEN, enrollment_response.get("next_token"))
                    LocalDatastore().set(LocalDatastore.Key.SESSION, enrollment_response.get("session"))
                else:
                    raise NotImplementedError
                logger.success("Exegol successfully activated!")
                await self.__user_session.auth.sign_out({"scope": "local"})
                return True
            except CancelOperation:
                selected_license_id = None
                time.sleep(2)
