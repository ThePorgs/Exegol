import json

import docker
import requests
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn, TransferSpeedColumn, TimeRemainingColumn

from console.LayerTextColumn import LayerTextColumn
from wrapper.model.ExegolImage import ExegolImage
from wrapper.utils.ExeLog import logger


class DockerUtils:
    __client = docker.from_env()
    __image_name = "nwodtuhs/exegol"
    __images = None
    __containers = None

    @classmethod
    def listImages(cls):
        logger.info("Available images")
        if cls.__images is None:
            remote_images = cls.__listRemoteImages()
            local_images = cls.__listLocalImages()
            cls.__images = ExegolImage.mergeImages(remote_images, local_images)
        return cls.__images

    @classmethod
    def __listLocalImages(cls, tag=None):
        logger.debug("Fetching local image tags, digests (and other attributes)")
        return cls.__client.images.list(cls.__image_name + "" if tag is None else ":" + tag,
                                        filters={"dangling": False})

    @classmethod
    def __listRemoteImages(cls):
        logger.debug("Fetching remote image tags, digests and sizes")
        try:
            remote_images_request = requests.get(
                url="https://hub.docker.com/v2/repositories/{}/tags".format(cls.__image_name),
                timeout=(5, 10), verify=True)  # TODO add verify as optional
        except requests.exceptions.ConnectionError as err:
            logger.warning("Connection Error: you probably have no internet, skipping online queries")
            logger.warning(f"Error: {err}")
            return []
        remote_results = []
        remote_images_list = json.loads(remote_images_request.text)
        for docker_image in remote_images_list["results"]:
            exegol_image = ExegolImage(name=docker_image.get('name', 'NONAME'),
                                       digest=docker_image["images"][0]["digest"],
                                       size=docker_image.get("full_size"))
            remote_results.append(exegol_image)
            cls.__client.images.list(cls.__image_name, filters={"dangling": False})
        return remote_results

    @classmethod
    def listContainers(cls):
        # TODO parse containers objects
        return cls.__client.containers.list(all=True, filters={"name": "exegol-"})

    @classmethod
    def updateImage(cls, image: ExegolImage):
        logger.info(f"Updating exegol image : {image.getName()}")
        name = image.update()
        if name is not None:
            logger.info(f"Starting download. Please wait, this might be (very) long.")
            layers = set()
            layers_complete = set()
            downloading = {}
            with Progress(TextColumn("{task.description}", justify="left"),
                          BarColumn(bar_width=None),
                          "[progress.percentage]{task.percentage:>3.1f}%",
                          "•",
                          LayerTextColumn("[bold]{task.completed}/{task.total}", "layer"),
                          "•",
                          TransferSpeedColumn(),
                          "•",
                          TimeElapsedColumn(),
                          "•",
                          TimeRemainingColumn(),
                          transient=True) as progress:
                task_layers = progress.add_task("[bold red]Downloading layers...", total=0)
                for line in cls.__client.api.pull(repository=cls.__image_name, tag=name, stream=True, decode=True):
                    status = line.get("status", '')
                    layer_id = line.get("id")
                    if status == "Pulling fs layer":
                        layers.add(layer_id)
                        progress.update(task_layers, total=len(layers), completed=len(layers_complete))
                    elif status == "Download complete":
                        layers_complete.add(layer_id)
                        # Remove finished layer progress bar
                        progress.remove_task(downloading.get(layer_id))
                        downloading.pop(layer_id)
                        progress.update(task_layers, total=len(layers), completed=len(layers_complete))
                    elif status == "Downloading":
                        task = downloading.get(layer_id)
                        if task is None:
                            task = progress.add_task(f"[blue]Downloading {layer_id}",
                                                     total=line.get("progressDetail", {}).get("total", 100),
                                                     layer=layer_id)
                            downloading[layer_id] = task
                        progress.update(task, completed=line.get("progressDetail", {}).get("current", 100))

                # image.setDockerObject(docker_image)
                logger.success(f"Image successfully updated")

