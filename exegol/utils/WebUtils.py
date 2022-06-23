import json
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
        github_response = cls.runJsonRequest(url)
        if github_response is None:
            raise CancelOperation
        latest_tag = github_response.get("tag_name")
        if latest_tag is None:
            logger.warning("Unable to parse the latest Exegol wrapper version from github API.")
            logger.debug(github_response)
        return latest_tag

    @classmethod
    def runJsonRequest(cls, url) -> Any:
        """Fetch a web page from url and parse the result as json."""
        data = cls.__runRequest(url)
        if data is not None:
            data = json.loads(data.text)
        return data

    @classmethod
    def __runRequest(cls, url) -> Optional[Response]:
        """Fetch a web page from url and catch / log different use cases."""
        try:
            response = requests.get(url=url, timeout=(5, 10), verify=ParametersManager().verify)
            return response
        except requests.exceptions.HTTPError as e:
            logger.error(f"Response error: {e.response.text}")
        except requests.exceptions.ConnectionError as err:
            logger.error(f"Error: {err}")
            logger.error("Connection Error: you probably have no internet.")
        except requests.exceptions.ReadTimeout:
            logger.error(
                "[green]Dockerhub[/green] request has [red]timed out[/red]. Do you have a slow internet connection, or is the remote service slow/down? Retry later.")
        except requests.exceptions.RequestException as err:
            logger.error(f"Unknown connection error: {err}")
        return None
