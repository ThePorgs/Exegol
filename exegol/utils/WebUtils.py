import json
import re
import time
from typing import Any, Optional

import requests
from requests import Response

from exegol import ConstantConfig
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.ExeLog import logger


class WebUtils:

    @classmethod
    def getLatestWrapperRelease(cls) -> str:
        url: str = f"https://api.github.com/repos/{ConstantConfig.GITHUB_REPO}/releases/latest"
        github_response = cls.runJsonRequest(url, "Github")
        if github_response is None:
            raise CancelOperation
        latest_tag = github_response.get("tag_name")
        if latest_tag is None:
            logger.warning("Unable to parse the latest Exegol wrapper version from github API.")
            logger.debug(github_response)
        return latest_tag

    @classmethod
    def runJsonRequest(cls, url: str, service_name: str) -> Any:
        """Fetch a web page from url and parse the result as json."""
        data = cls.__runRequest(url, service_name)
        if data is not None:
            data = json.loads(data.text)
        return data

    @classmethod
    def __runRequest(cls, url: str, service_name: str, retry_count: int = 2) -> Optional[Response]:
        """Fetch a web page from url and catch / log different use cases."""
        # In case of API timeout, allow retrying 1 more time
        for i in range(retry_count):
            try:
                try:
                    response = requests.get(url=url, timeout=(5, 10), verify=ParametersManager().verify)
                    return response
                except requests.exceptions.HTTPError as e:
                    logger.error(f"Response error: {e.response.text}")
                except requests.exceptions.ConnectionError as err:
                    logger.debug(f"Error: {err}")
                    error_re = re.search(r"\[Errno [-\d]+]\s?([^']*)('\))+\)*", str(err))
                    error_msg = ""
                    if error_re:
                        error_msg = f" ({error_re.group(1)})"
                    logger.error(f"Connection Error: you probably have no internet.{error_msg}")
                except requests.exceptions.RequestException as err:
                    logger.error(f"Unknown connection error: {err}")
                return None
            except requests.exceptions.ReadTimeout:
                logger.verbose(f"{service_name} time out, retrying ({i+1}/{retry_count}) ...")
                time.sleep(1)
        logger.error(f"[green]{service_name}[/green] request has [red]timed out[/red]. Do you have a slow internet connection, or is the remote service slow/down? Retry later.")
        return None
