from datetime import datetime, timedelta
from multiprocessing import Queue
from pathlib import Path
from typing import Optional, Tuple, Type, Union, Set, cast

import jwt

from exegol.config.ConstantConfig import ConstantConfig
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import CancelOperation, LicenseToleration, LicenseRevocation, UnavailableService
from exegol.manager.TaskManager import TaskManager
from exegol.model.LicensesTypes import LicenseType, LicenseFeature, SessionData, SessionOfflineData
from exegol.utils.ExeLog import logger
from exegol.utils.KeyHandler import KeyHandler
from exegol.utils.LocalDatastore import LocalDatastore
from exegol.utils.MUID import MUID
from exegol.utils.MetaSingleton import MetaSingleton
from exegol.utils.SupabaseUtils import SupabaseUtils


class SessionHandler(metaclass=MetaSingleton):
    __ALG = "ES256"
    __OFFLINE_KEY_PATH = ConstantConfig.exegol_config_path / "license.key"
    __SESSION_LOCK = ConstantConfig.exegol_config_path / ".session.lock"

    def __init__(self) -> None:
        self.__key_handler: KeyHandler = KeyHandler()
        self.__parsed_key: Optional[Path] = None
        # Raw JWT session
        self.__session: Optional[str] = None
        self.__token: Optional[str] = None
        # Raw JWT offline session object
        self.__offline_session: Optional[SessionOfflineData] = None
        self.__offline_mode: bool = False
        self.__offline_err_msg: Optional[str] = None
        # Session data
        self.__machine_id: Optional[str] = None
        self.__activation_id: Optional[str] = None
        self.__license: LicenseType = LicenseType.Community
        self.__license_id: Optional[str] = None
        self.__features: Set[LicenseFeature] = set()
        self.__license_owner: Optional[str] = None
        self.__username: Optional[str] = None
        self.__user_id: Optional[str] = None
        self.__expiration_date: Optional[datetime] = None
        self.__session_expiration_date: Optional[datetime] = None
        self.__session_issue_date: Optional[datetime] = None
        self.__is_enrolled: bool = False
        self.__current_muid: Optional[str] = None
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

    def __get_current_muid(self) -> str:
        if self.__current_muid is None:
            self.__current_muid = MUID.get_current_muid()
        return self.__current_muid

    def is_enrolled(self) -> bool:
        """Return True if the wrapper is enrolled to an Exegol license expired or not"""
        return self.__is_enrolled

    def pro_feature_access(self) -> bool:
        return self.get_license_type().value >= LicenseType.Professional.value

    def enterprise_feature_access(self) -> bool:
        return self.get_license_type().value >= LicenseType.Enterprise.value

    def has_feature(self, feature: LicenseFeature) -> bool:
        return feature in self.__features

    def __is_online_session_valid(self) -> bool:
        if self.__license == LicenseType.Community:
            return True
        now = datetime.now()
        return (self.__session_expiration_date is not None and
                self.__expiration_date is not None and
                not (self.__session_expiration_date < now or
                     self.__expiration_date < now or
                     self.__machine_id != self.__get_current_muid()))

    async def __refresh_thread_main(self, token: str, muid: str, return_queue: Queue) -> None:
        # Acquire refresh lock cross-process
        try:
            with open(self.__SESSION_LOCK, "x") as lock:
                lock.write(str(datetime.now().timestamp()))
            try:
                new_session = await self.__refresh_session(token, muid)
                return_queue.put((new_session, None))
            except UnavailableService:
                return_queue.put((None, LicenseToleration))
            except Exception as e:
                return_queue.put((None, e))
            except BaseException as e:
                # The thread is being aborted (e.g. SystemExit): fallback to the toleration mode so that the
                # caller never waits for a result that will not come, then let the thread die.
                logger.debug(f"Session refresh thread aborted: {type(e).__name__} {e}")
                return_queue.put((None, LicenseToleration))
                raise
            finally:
                # Always release the cross-process lock, even if the refresh was aborted
                self.__SESSION_LOCK.unlink(missing_ok=True)
            return None
        except FileExistsError:
            logger.debug(f"Session refresh lock detected.")
            creation_time = None
            with open(self.__SESSION_LOCK, "r") as lock_file:
                try:
                    creation_time = float(lock_file.read())
                except ValueError:
                    pass
            if creation_time is None:
                # Fallback to file creation time
                try:
                    creation_time = self.__SESSION_LOCK.stat().st_birthtime  # type: ignore[attr-defined]
                except AttributeError:
                    creation_time = self.__SESSION_LOCK.lstat().st_ctime
            if creation_time is not None and creation_time > 0 and (datetime.now() - datetime.fromtimestamp(creation_time)).seconds >= 3600:
                logger.debug(f"Session refresh lock is older than 1 hour. Removing it.")
                self.__SESSION_LOCK.unlink()
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
        # Token comparison check in case lock have been overwritten
        _, db_token = LocalDatastore().get_license()
        if token != db_token:
            logger.debug(f"Licence token mismatch detected. Refresh session cancelled.")
            raise LicenseToleration
        # Rotate token
        try:
            refresh_token = await SupabaseUtils.rotate_token(data, show_connection_error=not self.__is_offline_capable())
        except LicenseRevocation as e:
            self.remove_license()
            raise e
        # Save refresh token
        if refresh_token is not None:
            logger.debug(f"Storing refresh token response")
            LocalDatastore().set(LocalDatastore.Key.TOKEN, refresh_token)

        # Get session
        try:
            refresh_session = await SupabaseUtils.refresh_session({"token": refresh_token})
        except LicenseRevocation as e:
            self.remove_license()
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
        session = cast(SessionData, jwt.decode(self.__session,
                                               self.__key_handler.getKey(),
                                               algorithms=[self.__ALG],
                                               options={"require": ["iat", "iss", "aud", "exp"],
                                                        "verify_exp": False,
                                                        "verify_iat": False},
                                               audience="urn:exegol:wrapper",
                                               issuer=self.__key_handler.getSubject(), ))
        self.__machine_id = session["machine_id"]
        self.__extract_from_session(session)
        self.__offline_mode = False

    def __get_offline_key_path(self) -> Path:
        """
        Find license key file
        """
        if self.__parsed_key is not None:
            return self.__parsed_key
        if not self.__OFFLINE_KEY_PATH.is_file():
            key_search = list(ConstantConfig.exegol_config_path.glob("*.key"))
            if len(key_search) > 0:
                if len(key_search) > 1:
                    key_search.sort()
                    logger.warning(f"Multiple license key found! Using [magenta]{key_search[0]}[/magenta]")
                self.__parsed_key = key_search[0]
                return key_search[0]
        self.__parsed_key = self.__OFFLINE_KEY_PATH
        return self.__OFFLINE_KEY_PATH

    def save_offline_session(self, session: str) -> None:
        """
        Save offline session
        """
        with self.__OFFLINE_KEY_PATH.open(mode="w", encoding="utf-8") as f:
            f.write(session)

    def __session_can_refresh(self) -> bool:
        """
        Check last session refresh date
        :return: True if the session can be refreshed, False otherwise
        """
        return self.__session_issue_date is None or datetime.now() > (self.__session_issue_date + timedelta(minutes=10))

    def __is_offline_capable(self) -> bool:
        """
        Check if the wrapper is capable of loading offline license
        :return: True if the offline session is available and ready, False otherwise
        """
        if self.__offline_session is not None:
            return True
        elif self.__offline_err_msg is not None:
            return False
        else:
            return self.__load_offline_session()

    def __load_offline_session(self) -> bool:
        """
        Load offline JWT session
        :return: True if the offline session is available and ready, False otherwise
        """
        if self.__get_offline_key_path().is_file() and self.__offline_session is None:
            logger.debug("Loading offline JWT session")
            offline_token = self.__get_offline_key_path().read_text()
            try:
                offline_session = cast(SessionOfflineData,
                                       jwt.decode(offline_token,
                                                  self.__key_handler.getKey(),
                                                  algorithms=[self.__ALG],
                                                  options={"require": ["iat", "iss", "aud", "exp", "nbf"],
                                                           "verify_exp": True,
                                                           "verify_iat": True},
                                                  audience="urn:exegol:offline-wrapper",
                                                  issuer=self.__key_handler.getSubject(), ))
                if offline_session.get("activation_id") != LocalDatastore().get_activation_id() and offline_session.get("activation_id") != "*":
                    logger.debug(f"Mismatch activation id ({LocalDatastore().get_activation_id()}) in offline JWT session ({offline_session.get('activation_id')}).")
                    self.__offline_err_msg = "This offline license is not compatible with this machine. You can contact support if you need assistance."
                else:
                    self.__activation_id = offline_session["activation_id"]
                    self.__offline_session = offline_session
            except jwt.ExpiredSignatureError:
                self.__offline_err_msg = f"Offline license has expired. Please renew it from your exegol dashboard and replace the license key file: [magenta]{self.__get_offline_key_path()}[/magenta]"
            except jwt.ImmatureSignatureError:
                self.__offline_err_msg = f"The machine local date/time might be incorrect. Please check and synchronize the time difference and contact support if the problem persists."
            except (jwt.InvalidIssuerError, jwt.MissingRequiredClaimError, jwt.InvalidSignatureError):
                self.__offline_err_msg = f"This version of the wrapper is too old and does not support this new license. Please update your wrapper before using your license. You can contact support if you need assistance."
            except (jwt.InvalidAlgorithmError, jwt.InvalidAudienceError):
                logger.critical(":(")
            except jwt.InvalidTokenError as e:
                self.__offline_err_msg = f"An unknown error occurred while verifying the Exegol Offline license ({e.__class__.__name__}: {e}). Please contact support for assistance."
            except Exception as e:
                self.__offline_err_msg = f"An unknown error occurred while loading offline license: [{e.__class__.__name__}] {e}"
            if self.__offline_err_msg is not None:
                logger.warning(self.__offline_err_msg)
        return self.__offline_session is not None

    def __offline_parsing(self) -> None:
        if self.__offline_session is not None:
            logger.debug("Offline JWT session found. Extracting data")
            self.__extract_from_session(self.__offline_session)
            self.__offline_mode = True
            self.__machine_id = None

    def __extract_from_session(self, session: Union[SessionData, SessionOfflineData]) -> None:
        self.__license_id = session["license_id"]
        self.__license_owner = session["license_owner"]
        self.__username = session["username"]
        self.__user_id = session.get("user_id", "unknown")
        self.__expiration_date = datetime.fromtimestamp(session["expiration_date"])
        self.__session_expiration_date = datetime.fromtimestamp(session["exp"])
        self.__session_issue_date = datetime.fromtimestamp(session["iat"])
        self.__license = LicenseType[session.get("license", "Community")]
        self.__features.clear()
        features = session.get("features")
        if features is not None:
            for feat in features:
                try:
                    self.__features.add(LicenseFeature[feat])
                except KeyError:
                    logger.warning(f"The current version of your wrapper does not support feature '{feat}' of your license. Please update it to take advantage of this feature.")

    def __fast_load(self) -> bool:
        """
        Sync fast load from init for Completer usage / UserConfig generation etc
        :return:
        """
        logger.debug("Fast loading session from datastore")
        if self.__token is None:
            self.__session, self.__token = LocalDatastore().get_license()
        self.__is_enrolled = self.__token is not None or self.__is_offline_capable()
        if not self.__is_enrolled:
            return False
        now = datetime.now()
        # Verify JWT
        try:
            if not self.__session and not self.__is_offline_capable():
                # If fast_load is True, but we only have a refresh token and no session
                return False
            if not self.__session:
                self.__offline_parsing()
            elif not self.__offline_mode:
                self.__session_parsing()

            if self.__session_expiration_date is None or self.__expiration_date is None:
                raise LicenseToleration

            # Manually handle JWT expiration after payload parsing
            if self.__session_expiration_date < now:
                raise LicenseToleration

            # - Check local machine ID
            # - Expiration date still valid
            if self.__machine_id is not None and (self.__machine_id != self.__get_current_muid() or self.__expiration_date < now):
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
            if not self.__offline_mode and self.__is_offline_capable():
                logger.debug("Offline JWT session found. Using it instead of datastore session.")
                self.__offline_parsing()
                return self.__fast_load()
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

    async def reload_session(self, force_refresh: bool = False, force_offline: bool = False) -> bool:
        """

        :return: True is the session was reloaded
        """
        logger.debug("Fetch session from datastore")
        if self.__token is None:
            self.__session, self.__token = LocalDatastore().get_license()
        self.__is_enrolled = self.__token is not None or self.__is_offline_capable()
        if not self.__is_enrolled:
            return False
        now = datetime.now()
        # Verify JWT
        try:
            await self.__key_handler.refresh_certificate()  # Refresh cert if not yet ready
            # Check when session need to be reloaded from server (because session is missing but token is here, or because it's time to refresh)
            if not force_offline and self.__token is not None and (not self.__session or force_refresh):
                if ParametersManager().offline_mode or not self.__session_can_refresh():
                    # Too early to use the token
                    raise LicenseToleration
                refresh_queue: Queue[Tuple[Optional[str], Optional[Union[Exception, Type[Exception]]]]] = Queue()
                # Critical task in thread to prevent abort and loose session binding
                TaskManager.add_task(self.__refresh_thread_main(self.__token, self.__get_current_muid(), refresh_queue),
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

            if not force_offline and self.__session:
                self.__session_parsing()
            elif self.__is_offline_capable():
                if not self.__offline_mode:
                    self.__offline_parsing()

            if self.__session_expiration_date is None or self.__expiration_date is None:
                raise jwt.InvalidTokenError

            # Manually handle JWT expiration after payload parsing
            if self.__session_expiration_date < now:
                raise jwt.ExpiredSignatureError

            # - Check local machine ID
            # - Expiration date still valid
            if self.__machine_id is not None and (self.__machine_id != self.__get_current_muid() or self.__expiration_date < now):
                if not self.__session_can_refresh():
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
            if not self.__offline_mode and self.__is_offline_capable():
                logger.debug("Offline JWT session found. Using it instead of datastore session.")
                return await self.reload_session(force_offline=True)
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
                            logger.warning(f"Your {self.get_license_type_display()} license can be used offline for up to 7 days ({days_remaining} remaining). Full-offline usage is available as an optional add-on.")
                            # More warning message after 5j
                            if expiration_delta.days == 5:
                                logger.warning(f"Your {self.get_license_type_display()} features will be deactivated in {days_remaining} days if Exegol can't connect to the Internet before then.")
                            elif expiration_delta.days > 5:
                                await ExegolRich.Acknowledge(f"Your {self.get_license_type_display()} features will be deactivated in {days_remaining} days if Exegol can't connect to the Internet before then.")
                    else:
                        self.__license = LicenseType.Community
                        await ExegolRich.Acknowledge("Offline usage period exceeded. Connect Exegol back to the internet to re-enable Pro features.")
                else:
                    self.__license = LicenseType.Community
                    await self.__license_expired(False)
        return False

    async def __license_expired(self, have_internet: bool) -> None:
        await ExegolRich.Acknowledge(f"License has expired. Pro features not available anymore. Renew subscription{'' if have_internet else ' and connect to the Internet.'} to re-enable.")
        if await ExegolRich.Confirm("Do you want to deactivate your wrapper and cancel license auto-refresh?", default=False):
            self.remove_license()
        else:
            logger.info("Keeping local license binding. Exegol needs Internet access to enable Pro features.")

    def display_license(self, as_info: bool = False) -> None:
        display = f"Exegol "
        if self.__license is LicenseType.Community:
            display += f"[green]{self.__license.name}[/green] (personal use only)"
        elif self.__license is LicenseType.Professional:
            display += f"[gold3]{self.__license.name}[/gold3] licensed to [green]{self.__username}[/green]"
        elif self.__license is LicenseType.Enterprise:
            display += f"[gold3]{self.__license.name}[/gold3] licensed to [green]{self.__license_owner}[/green] / [green]{self.__username}[/green]"
        else:
            raise NotImplementedError

        if self.__license is not LicenseType.Community:
            logger.debug(f"Using license {self.__license_id} from machine {self.__activation_id if self.__offline_mode else self.__machine_id}")
        if as_info:
            logger.info(display)
        else:
            logger.verbose(display)
        if self.__expiration_date is not None:
            display = f"License valid until {self.__expiration_date}"
            if as_info:
                logger.info(display)
            else:
                logger.verbose(display)

    def display_support_info(self):
        logger.verbose("Support information:")
        logger.verbose(f"- User ID: {self.__user_id}")
        logger.verbose(f"- Licence ID: {self.__license_id}")
        if self.__features is not None and len(self.__features) > 0:
            logger.verbose(f"- Features: {','.join([x.name for x in self.__features])}")
        logger.verbose(f"- Machine ID: {self.__machine_id}")
        if self.__is_offline_capable() and self.__activation_id is not None:
            if len(self.__activation_id) == 8:
                logger.verbose(f"- Activation ID: [green]{self.__activation_id[:4]}-{self.__activation_id[4:]}[/green]")
            else:
                logger.verbose(f"- Activation ID: [green]{self.__activation_id}[/green]")
            logger.verbose(f"- Is offline: {self.__offline_mode}")
            logger.verbose(f"- Offline key: {self.__get_offline_key_path()}")
            logger.verbose(f"- Online session: {self.__token is not None}")
        else:
            act_id = MUID.get_activation_id()
            logger.verbose(f"- Activation ID: [green]{act_id[:4]}-{act_id[4:]}[/green]")
        logger.verbose(f"- License expiration: {self.__expiration_date}")
        logger.verbose(f"- Session expiration: {self.__session_expiration_date}")

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
        if self.__offline_mode:
            logger.critical("Exegol offline has been activated without an internet connection, so it is not possible to download images directly from the official internet registry.")
        await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
        # Check if session still valid
        if not self.__is_online_session_valid():
            # Reload session if needed
            if not await self.reload_session(force_refresh=True) or not self.__is_online_session_valid():
                if self.__SESSION_LOCK.exists():
                    logger.critical("Another exegol instance is refreshing the session. Please close other exegol instances before downloading a new image. Contact support if the problem persists.")
                logger.critical("You cannot access the official registry without access to Exegol license servers.")
        if self.__license == LicenseType.Community or self.__session is None:
            logger.critical("Pro/Enterprise license required to download non-Free images.")
            raise SystemExit(1)
        # Get a registry token for a specific registry
        return {
            "username": "__token__",
            "password": await SupabaseUtils.registry_access({"image_name": registry, "tag": tag}, self.__session)
        }

    def remove_license(self) -> None:
        LocalDatastore().deactivate_license()
        self.__get_offline_key_path().unlink(missing_ok=True)
        self.__is_enrolled = False
