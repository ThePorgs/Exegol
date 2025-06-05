from datetime import datetime
from multiprocessing import Queue
from typing import Optional, Tuple, Type, Union

import jwt

from exegol.config.ConstantConfig import ConstantConfig
from exegol.console.ExegolPrompt import ExegolRich
from exegol.exceptions.ExegolExceptions import CancelOperation, LicenseToleration, LicenseRevocation
from exegol.manager.TaskManager import TaskManager
from exegol.model.LicensesTypes import LicenseType
from exegol.utils.ExeLog import logger
from exegol.utils.KeyHandler import KeyHandler
from exegol.utils.LocalDatastore import LocalDatastore
from exegol.utils.MUID import MUID
from exegol.utils.MetaSingleton import MetaSingleton
from exegol.utils.SupabaseUtils import SupabaseUtils


class SessionHandler(metaclass=MetaSingleton):
    __PUB_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA9rkavi/6ee+aDd+483oi
smKFmWYt2oQqPdxKDRblkKD8UORy2fXoCTQuW7LVyD4RsIAx4fibE+Zsj9Rg9rTY
S2HoSMUoJfSYktkpV3ZDD+Jm4rddG6bAeC2unFbNokmwOLz5hdjUgNwJ5fsyA61D
X1YYMIFH73WZS1zBNh0Q9OgqFkwSXz7PEygHea7RkQVsxAPULUCVpKSXLJWpIAh/
uIPcpd3EwkomPJKnjztydfF/iE4wx+54zdej1BReRd85QOfoRzAE+nS89kgjXiCi
xtgF1VPiq0g7RALUlZgox05XgmM1pvxaP6zEUkS5IPW/qv0cY/cC6DJRr9FDBrWx
owIDAQAB
-----END PUBLIC KEY-----"""
    __ALG = "ES256"

    def __init__(self) -> None:
        self.__key_handler = KeyHandler()
        # Raw JWT session
        self.__session: Optional[str] = None
        self.__token: Optional[str] = None
        # Session data
        self.__machine_id: Optional[str] = None
        self.__license: LicenseType = LicenseType.Community
        self.__license_id: Optional[str] = None
        self.__license_owner: Optional[str] = None
        self.__user_email: Optional[str] = None
        self.__expiration_date: Optional[datetime] = None
        self.__session_expiration_date: Optional[datetime] = None
        self.__session_issue_date: Optional[datetime] = None
        self.__is_enrolled: bool = False
        self.__current_muid = MUID.get_current_muid()
        # Fast loading local session
        self.__fast_load()
        # Local status
        self.__cert_force_refreshed = False
        self.__session_refreshed = False

    """
    Yes. This is where the license check is happening. We didn't mean this to be a difficult thing to bypass. Know one thing though.
    Not supporting Exegol today probably means future features won't ever see the light of day. But yes, you'll save on a few bucks tough.
    Open-source probably was a mistake then...
    """

    def is_enrolled(self) -> bool:
        """Return True if the wrapper is enrolled to an Exegol license expired or not"""
        return self.__is_enrolled

    def pro_feature_access(self) -> bool:
        return self.get_license_type().value >= LicenseType.Professional.value

    def enterprise_feature_access(self) -> bool:
        return self.get_license_type().value >= LicenseType.Enterprise.value

    def __is_session_valid(self) -> bool:
        if self.__license == LicenseType.Community:
            return True
        now = datetime.now()
        return (self.__session_expiration_date is not None and
                self.__expiration_date is not None and
                not (self.__session_expiration_date < now or
                     self.__expiration_date < now or
                     self.__machine_id != self.__current_muid))

    async def __refresh_thread_main(self, token: str, muid: str, return_queue: Queue) -> None:
        # Acquire refresh lock cross-process
        lock_path = ConstantConfig.exegol_config_path / ".session.lock"
        try:
            with open(lock_path, "x") as lock:
                lock.write(str(datetime.now().timestamp()))
            try:
                new_session = await self.__refresh_session(token, muid)
                return_queue.put((new_session, None))
            except Exception as e:
                return_queue.put((None, e))
            lock_path.unlink()
            return None
        except FileExistsError:
            logger.debug(f"Session refresh lock detected.")
            creation_time = None
            with open(lock_path, "r") as lock_file:
                try:
                    creation_time = float(lock_file.read())
                except ValueError:
                    pass
            if creation_time is None:
                # Fallback to file creation time
                try:
                    creation_time = lock_path.stat().st_birthtime  # type: ignore[attr-defined]
                except AttributeError:
                    creation_time = lock_path.lstat().st_ctime
            if creation_time is not None and creation_time > 0 and (datetime.now() - datetime.fromtimestamp(creation_time)).seconds >= 3600:
                logger.debug(f"Session refresh lock is older than 1 hour. Removing it.")
                lock_path.unlink()
                return await self.__refresh_thread_main(token, muid, return_queue)
        except PermissionError:
            logger.error(f"Permission denied in {ConstantConfig.exegol_config_path} directory. Exegol need Read/Write access to this directory.")
        return_queue.put((None, LicenseToleration))
        return None

    async def __refresh_session(self, token: str, muid: str) -> Optional[str]:
        logger.debug(f"Refreshing session")
        data = {"token": token, "machine_id": muid}
        if self.__machine_id is not None and self.__machine_id != muid:
            data["previous_id"] = self.__machine_id
        # Rotate token
        try:
            refresh_token = await SupabaseUtils.rotate_token(data)
        except LicenseRevocation as e:
            LocalDatastore().deactivate_license()
            raise e
        # Save refresh token
        if refresh_token is not None:
            logger.debug(f"Storing refresh token response")
            LocalDatastore().set(LocalDatastore.Key.TOKEN, refresh_token)

        # Get session
        try:
            refresh_session = await SupabaseUtils.refresh_session({"token": refresh_token})
        except LicenseRevocation as e:
            LocalDatastore().deactivate_license()
            raise e
        # Save refresh token
        if refresh_session is not None:
            logger.debug(f"Storing session response")
            LocalDatastore().set(LocalDatastore.Key.SESSION, refresh_session)

        logger.debug(f"Session refreshed and stored")
        return refresh_session

    def __session_parsing(self) -> None:
        """
        Parse JWT session and extract data
        Raise many exceptions if the session is invalid
        :return:
        """
        if self.__session is None:
            raise jwt.InvalidTokenError
        session = jwt.decode(self.__session,
                             self.__key_handler.getKey(),
                             algorithms=[self.__ALG],
                             options={"require": ["iat", "iss", "aud", "exp"], "verify_exp": False, "verify_iat": False},
                             audience="urn:exegol:wrapper",
                             issuer=self.__key_handler.getSubject(), )
        logger.debug(f"Local session: {session}")
        self.__machine_id = session["machine_id"]
        self.__license_id = session["license_id"]
        self.__license_owner = session["license_owner"]
        self.__user_email = session["username"]
        self.__expiration_date = datetime.fromtimestamp(session["expiration_date"])
        self.__session_expiration_date = datetime.fromtimestamp(session["exp"])
        self.__session_issue_date = datetime.fromtimestamp(session["iat"])
        self.__license = LicenseType[session.get("license", "Community")]

    def __fast_load(self) -> bool:
        """
        Sync fast load from init for Completer usage / UserConfig generation etc
        :return:
        """
        logger.debug("Fast loading session from datastore")
        if self.__token is None:
            self.__session, self.__token = LocalDatastore().get_license()
        self.__is_enrolled = self.__token is not None
        if self.__token is None:
            return False
        now = datetime.now()
        # Verify JWT
        try:
            if not self.__session:
                # If fast_load is True, but we only have a refresh token and no session
                return False
            self.__session_parsing()

            if self.__session_expiration_date is None or self.__expiration_date is None:
                raise LicenseToleration

            # Manually handle JWT expiration after payload parsing
            if self.__session_expiration_date < now:
                raise LicenseToleration

            # - Check local machine ID
            # - Expiration date still valid
            if self.__machine_id != self.__current_muid or self.__expiration_date < now:
                raise LicenseToleration
            logger.debug("Session is valid and fully processed")
            return True
        except KeyError:
            logger.error("Your version of Exegol wrapper doesn't support this license type. Please update your exegol wrapper.")
            self.__license = LicenseType.Community
        except jwt.ExpiredSignatureError:
            pass
        except jwt.InvalidTokenError:
            pass
        except CancelOperation:
            pass
        except LicenseToleration:
            # - Signed by JWT Cert keymax 7j (en tant qu'offline)
            # - Warning after 24h (post-expiration) offline
            # - Interactive warning message after 3j+
            logger.debug("License toleration detected")
            if self.__license != LicenseType.Community:
                if (self.__expiration_date is not None and
                        self.__session_expiration_date is not None and
                        self.__expiration_date > now):
                    expiration_delta = now - self.__session_expiration_date
                    # After 7 days the grace period expired
                    if expiration_delta.days >= 7:
                        self.__license = LicenseType.Community
                else:
                    self.__license = LicenseType.Community
        return False

    async def reload_session(self, force_refresh: bool = False) -> bool:
        """

        :return: True is the session was reloaded
        """
        logger.debug("Fetch session from datastore")
        if self.__token is None:
            self.__session, self.__token = LocalDatastore().get_license()
        self.__is_enrolled = self.__token is not None
        if self.__token is None:
            return False
        now = datetime.now()
        # Verify JWT
        try:
            await self.__key_handler.refresh_certificate()  # Refresh cert if not yet ready
            # Check when session need to be reloaded from server (because session is missing but token is here, or because it's time to refresh)
            if not self.__session or force_refresh:
                if self.__session_issue_date and (now - self.__session_issue_date).seconds <= 300:
                    # Too early to use the token
                    raise LicenseToleration
                refresh_queue: Queue[Tuple[Optional[str], Optional[Union[Exception, Type[Exception]]]]] = Queue()
                # Critical task in thread to prevent abort and loose session binding
                TaskManager.add_task(self.__refresh_thread_main(self.__token, self.__current_muid, refresh_queue),
                                     TaskManager.TaskId.RefreshSession)
                await TaskManager.wait_for(TaskManager.TaskId.RefreshSession)
                refresh_error: Optional[Union[Exception, Type[Exception]]]
                # Fetch Result of refresh thread
                self.__session, refresh_error = refresh_queue.get()
                self.__token = None
                refresh_queue.close()
                self.__session_refreshed = True
                if refresh_error is not None:
                    raise refresh_error
                elif self.__session is None:
                    raise CancelOperation

            elif not self.__session:
                # If fast_load is True, but we only have a refresh token and no session
                return False
            self.__session_parsing()

            if self.__session_expiration_date is None or self.__expiration_date is None:
                raise jwt.InvalidTokenError

            # Manually handle JWT expiration after payload parsing
            if self.__session_expiration_date < now:
                raise jwt.ExpiredSignatureError

            # - Check local machine ID
            # - Expiration date still valid
            if self.__machine_id != self.__current_muid or self.__expiration_date < now:
                if (now - self.__session_expiration_date).seconds <= 300:
                    raise LicenseToleration
                if not force_refresh and not self.__session_refreshed:
                    return await self.reload_session(force_refresh=True)
                else:
                    raise CancelOperation
            logger.debug("Session is valid and fully processed")
            return True
        except KeyError:
            logger.error("Your version of Exegol wrapper doesn't support this license type. Please update your exegol wrapper.")
            self.__license = LicenseType.Community
        except jwt.ExpiredSignatureError:
            if force_refresh or self.__session_refreshed:
                logger.critical("Your system doesn't seem to be on time. Please check your system settings.")
            logger.debug("Session expired, reloading it")
            return await self.reload_session(force_refresh=True)
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid token error: {e}")
            if force_refresh or self.__session_refreshed:
                if not self.__cert_force_refreshed:
                    cert_changed = await self.__key_handler.refresh_certificate(force_refresh=True)
                    self.__cert_force_refreshed = True
                    if cert_changed:
                        return await self.reload_session()
                self.__license = LicenseType.Community
                logger.error("An error occurred, your license cannot be processed. Please update your wrapper to the latest version or contact support.")
            return await self.reload_session(force_refresh=True)
        except CancelOperation:
            self.__license = LicenseType.Community
            await self.__license_expired(True)
        except LicenseRevocation:
            self.__license = LicenseType.Community
            await ExegolRich.Acknowledge("Your license has been revoked. Re-activation is required.")
        except LicenseToleration:
            # - Signed by JWT Cert keymax 7j (en tant qu'offline)
            # - Warning after 24h (post-expiration) offline
            # - Interactive warning message after 3j+
            logger.debug("License toleration detected")
            if self.__license != LicenseType.Community:
                if (self.__expiration_date is not None and
                        self.__session_expiration_date is not None and
                        self.__expiration_date > now):
                    expiration_delta = now - self.__session_expiration_date
                    # After 7 days the grace period expired
                    if expiration_delta.days < 7:
                        days_remaining = 7 - expiration_delta.days
                        # Warning after 2d offline
                        if expiration_delta.days >= 2:
                            logger.warning(f"Offline use of your {self.get_license_type_display()} features is allowed for up to 7 days ({expiration_delta.days}/7).")
                            # More warning message after 5j
                            if expiration_delta.days == 5:
                                logger.warning(f"{self.get_license_type_display()} features will be deactivated in {days_remaining} days if Exegol can't connect to the Internet before then.")
                            else:
                                await ExegolRich.Acknowledge(f"{self.get_license_type_display()} features will be deactivated in {days_remaining} days if Exegol can't connect to the Internet before then.")
                    else:
                        self.__license = LicenseType.Community
                        await ExegolRich.Acknowledge("Offline usage period exceeded. Connect Exegol back to the internet to re-enable Pro features.")
                else:
                    self.__license = LicenseType.Community
                    await self.__license_expired(False)
        return False

    @staticmethod
    async def __license_expired(have_internet: bool) -> None:
        await ExegolRich.Acknowledge(f"License has expired. Pro features not available anymore. Renew subscription{'' if have_internet else ' and connect to the Internet.'} to re-enable.")
        if await ExegolRich.Confirm("Do you want to deactivate your wrapper and cancel license auto-refresh?", default=False):
            LocalDatastore().deactivate_license()
        else:
            logger.info("Keeping local license binding. Exegol needs Internet access to enable Pro features.")

    def display_license(self, as_info: bool = False) -> None:
        display = f"Exegol "
        if self.__license is LicenseType.Community:
            display += f"[green]{self.__license.name}[/green] (personal use only)"
        elif self.__license is LicenseType.Professional:
            display += f"[gold3]{self.__license.name}[/gold3] licensed to [green]{self.__user_email}[/green]"
        elif self.__license is LicenseType.Enterprise:
            display += f"[gold3]{self.__license.name}[/gold3] licensed to [green]{self.__license_owner}[/green] / [green]{self.__user_email}[/green]"
        else:
            raise NotImplementedError

        if self.__license is not LicenseType.Community:
            logger.debug(f"Using license {self.__license_id} from machine {self.__machine_id}")
        if as_info:
            logger.info(display)
        else:
            logger.verbose(display)
        if self.__expiration_date is not None:
            logger.verbose(f"License valid until {self.__expiration_date}")

    def get_license_type_display(self) -> str:
        if self.__license is not None:
            if self.__license != LicenseType.Community:
                return f"[gold3]{self.__license.name}[/gold3]"
        return f"[green]{LicenseType.Community.name}[/green]"

    def get_license_type(self) -> LicenseType:
        if self.__license is not None:
            return self.__license
        return LicenseType.Community

    async def get_registry_auth(self, registry: str, tag: str) -> dict:
        await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
        # Check if session still valid
        if not self.__is_session_valid():
            logger.critical("You cannot access the official registry without access to Exegol license servers.")
        if self.__license == LicenseType.Community or self.__session is None:
            logger.critical("Pro/Enterprise license required to download non-Free images.")
            raise SystemExit(1)
        # Get registry token for specific registry
        return {"username": "__token__", "password": await SupabaseUtils.registry_access({"image_name": registry, "tag": tag}, self.__session)}
