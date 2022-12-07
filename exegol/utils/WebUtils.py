import json
import re
import time
from typing import Any, Optional, Dict

import requests
from requests import Response

from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


class WebUtils:
    __registry_token: Optional[str] = None

    @classmethod
    def __getGuestToken(cls, action: str = "pull", service: str = "registry.docker.io"):
        """Generate a guest token for Registry service"""
        url = f"https://auth.docker.io/token?scope=repository:{ConstantConfig.IMAGE_NAME}:{action}&service={service}"
        response = cls.runJsonRequest(url, service_name="Docker Auth")
        if response is not None:
            return response.get("access_token")
        logger.error("Unable to authenticate to docker as anonymous")
        logger.debug(response)
        # If token cannot be retrieved, operation must be cancelled
        raise CancelOperation

    @classmethod
    def __generateLoginToken(cls):
        """Generate an auth token that will be used on future API request"""
        # Currently, only support for guest token
        cls.__registry_token = cls.__getGuestToken()

    @classmethod
    def __getRegistryToken(cls) -> str:
        """Registry auth token getter"""
        if cls.__registry_token is None:
            cls.__generateLoginToken()
        assert cls.__registry_token is not None
        return cls.__registry_token

    @classmethod
    def getLatestWrapperRelease(cls) -> str:
        """Fetch from GitHub release the latest Exegol wrapper version"""
        if ParametersManager().offline_mode:
            raise CancelOperation
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
    def getMetaDigestId(cls, tag: str) -> Optional[str]:
        """Get Virtual digest id of a specific image tag from docker registry"""
        if ParametersManager().offline_mode:
            return None
        try:
            token = cls.__getRegistryToken()
        except CancelOperation:
            return None
        manifest_headers = {"Accept": "application/vnd.docker.distribution.manifest.list.v2+json", "Authorization": f"Bearer {token}"}
        # Query Docker registry API on manifest endpoint using tag name
        url = f"https://{ConstantConfig.DOCKER_REGISTRY}/v2/{ConstantConfig.IMAGE_NAME}/manifests/{tag}"
        response = cls.__runRequest(url, service_name="Docker Registry", headers=manifest_headers, method="HEAD")
        digest_id: Optional[str] = None
        if response is not None:
            digest_id = response.headers.get("docker-content-digest")
            if digest_id is None:
                digest_id = response.headers.get("etag")
        return digest_id

    @classmethod
    def getRemoteVersion(cls, tag: str) -> Optional[str]:
        """Get image version of a specific image tag from docker registry."""
        if ParametersManager().offline_mode:
            return None
        try:
            token = cls.__getRegistryToken()
        except CancelOperation:
            return None
        # In order to access the metadata of the image, the v1 manifest must be use
        manifest_headers = {"Accept": "application/vnd.docker.distribution.manifest.v1+json", "Authorization": f"Bearer {token}"}
        # Query Docker registry API on manifest endpoint using tag name
        url = f"https://{ConstantConfig.DOCKER_REGISTRY}/v2/{ConstantConfig.IMAGE_NAME}/manifests/{tag}"
        response = cls.__runRequest(url, service_name="Docker Registry", headers=manifest_headers, method="GET")
        version: Optional[str] = None
        if response is not None and response.status_code == 200:
            data = json.loads(response.text)
            # Parse metadata of the current image from v1 schema
            metadata = json.loads(data.get("history", [])[0]['v1Compatibility'])
            # Find version label and extract data
            version = metadata.get("config", {}).get("Labels", {}).get("org.exegol.version", "")
        return version

    @classmethod
    def runJsonRequest(cls, url: str, service_name: str, headers: Optional[Dict] = None, method: str = "GET", data: Any = None, retry_count: int = 2) -> Any:
        """Fetch a web page from url and parse the result as json."""
        if ParametersManager().offline_mode:
            return None
        data = cls.__runRequest(url, service_name, headers, method, data, retry_count)
        if data is not None and data.status_code == 200:
            data = json.loads(data.text)
        elif data is not None:
            logger.error(f"Error during web request to {service_name} ({data.status_code}) on {url}")
            if data.status_code == 404 and service_name == "Dockerhub":
                logger.info("The registry is not accessible, if it is a private repository make sure you are authenticated prior with docker login.")
            data = None
        return data

    @classmethod
    def __runRequest(cls, url: str, service_name: str, headers: Optional[Dict] = None, method: str = "GET", data: Any = None, retry_count: int = 2) -> Optional[Response]:
        """Fetch a web page from url and catch / log different use cases.
        Url: web page to quest
        Service_name: service display name for logging purpose
        Retry_count: number of retry allowed."""
        # In case of API timeout, allow retrying 1 more time
        for i in range(retry_count):
            try:
                try:
                    response = requests.request(method=method, url=url, timeout=(5, 10), verify=ParametersManager().verify, headers=headers, data=data)
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
                    # Switch to offline mode
                    ParametersManager().offline_mode = True
                except requests.exceptions.RequestException as err:
                    logger.error(f"Unknown connection error: {err}")
                return None
            except requests.exceptions.ReadTimeout:
                logger.verbose(f"{service_name} time out, retrying ({i + 1}/{retry_count}) ...")
                time.sleep(1)
        logger.error(f"[green]{service_name}[/green] request has [red]timed out[/red]. Do you have a slow internet connection, or is the remote service slow/down? Retry later.")
        return None
