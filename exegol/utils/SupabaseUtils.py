import logging
from enum import Enum
from typing import Optional, Union, List, Tuple, Dict, cast

from gotrue.errors import AuthApiError, AuthRetryableError, AuthInvalidCredentialsError, AuthUnknownError
from httpx import ConnectError, TransportError
from postgrest import APIError, AsyncFilterRequestBuilder, \
    AsyncMaybeSingleRequestBuilder, AsyncSingleRequestBuilder, AsyncSelectRequestBuilder, APIResponse
from supabase import create_async_client, AsyncClient
from supabase.lib.client_options import AsyncClientOptions
from supafunc import AsyncFunctionsClient
from supafunc.errors import FunctionsHttpError, FunctionsRelayError

from exegol.config.ConstantConfig import ConstantConfig
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import CancelOperation, LicenseToleration, LicenseRevocation
from exegol.model.LicensesTypes import LicenseSession, TokenRotate, LicenseEnrollment, EnrollmentForm
from exegol.model.SupabaseModels import SupabaseImage
from exegol.utils.ExeLog import logger


class SupabaseUtils:
    class LicenseAction(Enum):
        LicenseEnum = "license_enumeration"
        LicenseActivation = "license_activation"
        TokenRotate = "token_rotate"
        TokenSession = "token_session"

        RegistryAccess = "registry_access"

        GetCertificate = "machine_certificate"

    @classmethod
    async def __create_client(cls) -> AsyncClient:
        return await create_async_client(ConstantConfig.SUPABASE_URL, ConstantConfig.SUPABASE_KEY, options=AsyncClientOptions(
            persist_session=False,
            postgrest_client_timeout=10,
            schema="public",
        ))

    @classmethod
    async def login_user(cls) -> AsyncClient:
        if ParametersManager().offline_mode:
            logger.critical("You can't activate Exegol in offline mode.")
        # Login
        supabase_client = await cls.__create_client()
        logger.info("Authenticating to Exegol")
        auth_response = None
        email = None
        for i in range(3):
            if email is None:
                email = await ExegolRich.Ask("[bold blue][?][/bold blue] Enter your exegol email account")
            if email.strip() == "":
                email = None
                logger.error("You must supply a valid email account, please retry")
                continue
            try:
                logger.success("To link your account to the wrapper, you need to generate a login code "
                               "from your dashboard: https://dashboard.exegol.com/otp")
                token = await ExegolRich.Ask("[bold blue][?][/bold blue] Enter your login token")
                auth_response = await supabase_client.auth.verify_otp({
                    "type": "magiclink",
                    "email": email,
                    "token": token,
                })
                break
            except AuthInvalidCredentialsError:
                logger.error("You must supply a valid email account, please retry")
            except AuthApiError as e:
                if "Invalid email" in e.message:
                    email = None
                logger.error(f"{e}, please retry")
            except AuthRetryableError as e:
                if e.status == 503:
                    logger.critical("The Exegol servers are currently unavailable, please try again later.")
                elif e.status == 0 and e.code is None:
                    logger.critical("You can't activate Exegol without internet access.")
                else:
                    logger.debug(f"Received error [{e.status}] {e.code} {e.message}")
                    logger.error(f"Unable to authenticate you to Exegol, retry later. {e.message}")
            except AuthUnknownError as e:
                logger.error(f"An unknown error occurred during authentication, retry later. {e.message}")
        if auth_response is None or auth_response.user is None:
            logger.critical("Unable to authenticate, aborting.")
        logger.success("Successfully authenticated")
        return supabase_client

    @classmethod
    async def __call_licenses_endpoint(cls, supabase_client: AsyncFunctionsClient, function_name: LicenseAction,
                                       body: Optional[Dict] = None, auth_token: Optional[str] = None) -> Dict:
        """
        This function raises the following exception that should be caught accordingly:
            - FunctionsRelayError (supabase error)
            - ConnectError (no internet)
            - TransportError (function unavailable)
            - FunctionsHttpError (app error)
        :param supabase_client: Supabase client instance (auth or anonymous)
        :param function_name: Function name to call (enum, activate, renew, registry_access, ...)
        :param body: Form (if any)
        :param auth_token: Session token (if any)
        :return:
        """
        if ParametersManager().offline_mode:
            # This check must be made before
            raise NotImplementedError
        headers: Dict[str, str] = {"app-action": function_name.value}
        options: Dict[str, Union[str, Dict]] = {"headers": headers}
        if function_name != cls.LicenseAction.GetCertificate:
            options["responseType"] = "json"
        if body:
            options["body"] = body
        if auth_token:
            headers["app-session"] = auth_token
        result = await supabase_client.invoke("licenses-endpoint", invoke_options=options)
        if type(result) is bytes:
            return {"result": result}
        return result

    @classmethod
    async def __execute(cls, supabase_query: Union[AsyncFilterRequestBuilder, AsyncMaybeSingleRequestBuilder, AsyncSingleRequestBuilder, AsyncSelectRequestBuilder]) -> Optional[APIResponse]:
        if ParametersManager().offline_mode:
            # This check must be made before
            raise NotImplementedError
        try:
            return await supabase_query.execute()
        except ConnectError as e:
            logger.debug(f"Supabase connect error: {e}")
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                logger.warning("TLS certificate verification failed while contacting Exegol servers. Do you have a proxy server ? If so, python probably doesn't trust your private CA.")
                logger.warning("Check the Exegol documentation to fix the issue: https://docs.exegol.com/troubleshooting#tls-certificate-verification-issues")
            else:
                logger.warning("No internet connection available. Skipping online queries.")
        except TransportError:
            logger.warning("An error occurred while contacting the server.")
        except APIError as e:
            if e.code == 503:
                logger.warning("The Exegol servers are currently unavailable, image status cannot be retrieved.")
            else:
                logger.debug(e.details)
                logger.error(f"[{e.code}] An error occurred while contacting Exegol servers: {e.message}")
                logger.warning("Some information might be missing.")
        return None

    ### License calls ###

    @classmethod
    async def get_cert(cls) -> bytes:
        """
        Get new public certificate from license server.
        :return: Public certificate as string.
        """
        if ParametersManager().offline_mode:
            logger.critical("You need internet access to validate Exegol license.")
        try:
            data: Dict[str, bytes] = await cls.__call_licenses_endpoint((await cls.__create_client()).functions, cls.LicenseAction.GetCertificate)
            cert = data.get("result")
            if cert is None:
                raise FunctionsRelayError
            return cert
        except ConnectError as e:
            logger.critical("Exegol license server is unreachable. Do you have internet access?")
            raise e
        except (FunctionsRelayError, TransportError) as e:
            logger.critical("Exegol license server seems to be unavailable for now. Please retry later.")
            raise e
        except FunctionsHttpError as e:
            if e.status in [500, 503, 504, 546]:
                logger.critical("The Exegol servers are currently unavailable, please try again later.")
            else:
                logger.critical(f"Unable to enumerate licenses from exegol servers: [{e.status}] {e.message}")
            raise e

    @classmethod
    async def enum_licenses(cls, supabase_client: AsyncFunctionsClient) -> Dict:
        """
        Enumerate all licenses available for the current user.
        :param supabase_client:
        :return:
        """
        if ParametersManager().offline_mode:
            logger.critical("You can't activate Exegol in offline mode.")
        try:
            return await cls.__call_licenses_endpoint(supabase_client, cls.LicenseAction.LicenseEnum)
        except ConnectError as e:
            logger.critical("Exegol license server is unreachable. Do you have internet access?")
            raise e
        except (FunctionsRelayError, TransportError) as e:
            logger.critical("Exegol license server seems to be unavailable for now. Please retry later.")
            raise e
        except FunctionsHttpError as e:
            if e.status in [403, 503, 504, 546]:
                logger.critical("The Exegol servers are currently unavailable, please try again later.")
            else:
                logger.critical(f"Unable to enumerate licenses from exegol servers: [{e.status}] {e.message}")
            raise e

    @classmethod
    async def activate_licenses(cls, supabase_client: AsyncFunctionsClient, form: EnrollmentForm) -> LicenseEnrollment:
        if ParametersManager().offline_mode:
            logger.critical("You can't activate Exegol in offline mode.")
        try:
            return cast(LicenseEnrollment, await cls.__call_licenses_endpoint(supabase_client, cls.LicenseAction.LicenseActivation, cast(dict, form)))
        except ConnectError:
            logger.error("Exegol license server is unreachable. Do you have internet access?")
            raise CancelOperation
        except (FunctionsRelayError, TransportError):
            logger.error("Exegol license server seems to be unavailable for now. Please retry later.")
            raise CancelOperation
        except FunctionsHttpError as e:
            if e.status in [401, 404, 406]:
                logger.raw(msg=f"[bold red][-][/bold red] {e.message}", markup=True, emoji=True, level=logging.ERROR)
                logger.empty_line(log_level=logging.ERROR)
            elif e.status == 400:
                if e.message == "Bad Request":
                    logger.error("Exegol license server seems to be unavailable for now. Check if your exegol is up-to-date and retry.")
                else:
                    logger.error(f"An error occurred when activating Exegol: {e.message}")
            elif e.status in [403, 503, 504, 546]:
                logger.error(f"The license server is currently unavailable. Please try again later.")
                logger.debug(f"Error code [{e.status}] {e}")
            elif e.status >= 500:
                logger.error(f"An error has occurred in the license server. You can contact support to help you. Error: [{e.status}] {e.message}")
            else:
                logger.error(f"An unknown error occurred when activating Exegol: {e.message} {e}")
            raise CancelOperation

    @staticmethod
    def __handle_session_error(e: FunctionsHttpError):
        if e.status == 403:
            # 403 invalid token (revoked)
            logger.error("Your license has been revoked on this machine.")
            raise LicenseRevocation
        elif e.status == 410:
            # 410 invalid licenses (expired)
            logger.error("Your license has expired. Please re-activate your exegol with another license.")
            raise LicenseRevocation
        elif e.status == 425:
            # 425 sessions cannot be renewed yet
            logger.debug("Session refresh rate limited.")
        elif e.status == 400:
            logger.warning("Received an unexpected error from license server. Check if your wrapper is up-to-date.")
        elif e.status == 500:
            logger.verbose(f"The Exegol servers are currently unavailable, please try again later.")
        elif e.status in [503, 504, 546]:
            logger.debug(f"License server seems to be unavailable for now: code {e.status} {e.message}. Retry later.")
        else:
            logger.error(f"An unknown error occurred when renewing session: [{e.status}] {e.message}")

    @classmethod
    async def rotate_token(cls, form: dict) -> str:
        if ParametersManager().offline_mode:
            raise LicenseToleration
        try:
            result = cast(TokenRotate, await cls.__call_licenses_endpoint((await cls.__create_client()).functions,
                                                                          cls.LicenseAction.TokenRotate,
                                                                          form))
            token = result.get("next_token")
            if token is None:
                raise FunctionsRelayError("Received an empty response from license server.")
            return token
        except ConnectError:
            logger.error("Exegol license server is unreachable. Do you have internet access?")
            raise LicenseToleration
        except (FunctionsRelayError, TransportError) as e:
            # Error during http request
            logger.debug(f"Error during session refresh. Network error, retry later: {e}")
            raise LicenseToleration
        except FunctionsHttpError as e:
            cls.__handle_session_error(e)
            raise LicenseToleration

    @classmethod
    async def refresh_session(cls, form: dict) -> Optional[str]:
        if ParametersManager().offline_mode:
            raise LicenseToleration
        try:
            result = cast(LicenseSession, await cls.__call_licenses_endpoint((await cls.__create_client()).functions,
                                                                             cls.LicenseAction.TokenSession,
                                                                             form))
            return result.get("session")
        except ConnectError:
            logger.error("Exegol license server is unreachable. Do you have internet access?")
            raise LicenseToleration
        except (FunctionsRelayError, TransportError) as e:
            # Error during http request
            logger.debug(f"Error during session refresh. Network error, retry later: {e}")
            raise LicenseToleration
        except FunctionsHttpError as e:
            cls.__handle_session_error(e)
            raise LicenseToleration

    @classmethod
    async def registry_access(cls, form: dict, session: str) -> str:
        if ParametersManager().offline_mode:
            logger.critical("You can't access the registry in offline mode.")
        try:
            data = await cls.__call_licenses_endpoint((await cls.__create_client()).functions,
                                                      cls.LicenseAction.RegistryAccess,
                                                      body=form,
                                                      auth_token=session)
            token = data.get("token")
            if token is None:
                logger.error("Exegol server returned an unexpected response. Please retry later.")
                raise CancelOperation
            return token
        except ConnectError as e:
            logger.critical("Exegol server is unreachable. Do you have internet access?")
            raise e
        except (FunctionsRelayError, TransportError) as e:
            logger.critical("Exegol server seems to be unavailable for now. Please retry later.")
            raise e
        except FunctionsHttpError as e:
            if e.status == 403:
                logger.critical("Your license does not allow you to download this image.")
            elif e.status == 500:
                logger.critical("The Exegol servers are currently unavailable, please try again later.")
            else:
                logger.debug(f"Error code {e.status}")
                logger.critical(f"An error occurred for registry access: {e.message}")
            raise e

    ## Public DB ##
    ### images table ###

    @classmethod
    async def list_all_images(cls, arch: str) -> List[SupabaseImage]:
        if ParametersManager().offline_mode:
            logger.warning("Offline mode enabled. Skipping image listing.")
            return []
        logger.debug(f"Listing images from metadata table")
        image_list = await cls.__execute((await cls.__create_client())
                                         .table("images")
                                         .select("*")
                                         .eq("arch", arch)
                                         .not_.is_("version", None))
        supa_images: List[SupabaseImage] = []
        if image_list is not None:
            # Pydantic validation
            for x in image_list.data:
                supa_images.append(SupabaseImage.model_validate(x))

        return supa_images

    @classmethod
    async def get_tag_version(cls, tag: str, arch: str) -> Tuple[Optional[str], Optional[str]]:
        """Get the latest version information of a specific image"""
        if ParametersManager().offline_mode:
            return None, None
        logger.debug(f"Fetching latest version of a specific image {tag} from metadata table")
        image: Optional[APIResponse] = await cls.__execute((await cls.__create_client())
                                                           .table("images")
                                                           .select("repo_digest, version")
                                                           .eq("arch", arch)
                                                           .eq("tag", tag)
                                                           .not_.is_("version", None)
                                                           .limit(1)
                                                           .maybe_single())
        if image is None:
            return None, None
        result: Optional[Dict[str, str]] = cast(Optional[Dict[str, str]], image.data)  # single mode cast
        if result is None:
            return None, None
        return result["repo_digest"], result["version"]
