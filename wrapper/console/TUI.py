import logging
import re

from rich.progress import Progress, TextColumn, BarColumn, TransferSpeedColumn, TimeElapsedColumn, TimeRemainingColumn

from wrapper.console.LayerTextColumn import LayerTextColumn
from wrapper.utils.ExeLog import logger


class ExegolTUI:

    @classmethod
    def downloadDockerLayer(cls, stream, quick_exit=False):
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
            for line in stream:
                status = line.get("status", '')
                layer_id = line.get("id")
                if status == "Pulling fs layer":
                    layers.add(layer_id)
                    progress.update(task_layers, total=len(layers))
                elif "Pulling from " in status:
                    progress.tasks[
                        task_layers].description = f"[bold red]Downloading {status.replace('Pulling from ', '')}:{line.get('id', 'latest')}"
                elif status == "Download complete":
                    layers_complete.add(layer_id)
                    # Remove finished layer progress bar
                    progress.remove_task(downloading.get(layer_id))
                    downloading.pop(layer_id)
                    progress.update(task_layers, completed=len(layers_complete))
                    if quick_exit and len(layers_complete) == len(layers):
                        # Exit stream when download is complete
                        logger.info("End of download")
                        break
                elif "Image is up to date" in status:
                    logger.info(status)
                    break
                elif status == "Downloading":
                    task = downloading.get(layer_id)
                    if task is None:
                        task = progress.add_task(f"[blue]Downloading {layer_id}",
                                                 total=line.get("progressDetail", {}).get("total", 100),
                                                 layer=layer_id)
                        downloading[layer_id] = task
                    progress.update(task, completed=line.get("progressDetail", {}).get("current", 100))

    @classmethod
    def buildDockerImage(cls, build_stream):
        for line in build_stream:
            stream_text = line.get("stream", '')
            if stream_text.strip() != '':
                if "Step" in stream_text:
                    logger.info(stream_text.rstrip())
                elif "--->" in stream_text or \
                        "Removing intermediate container " in stream_text or \
                        re.match(r"Successfully built [a-z0-9]{12}", stream_text) or \
                        re.match(r"^Successfully tagged ", stream_text):
                    logger.verbose(stream_text.rstrip())
                else:
                    logger.raw(stream_text, level=logging.DEBUG)
            if ': FROM ' in stream_text:
                logger.info("Downloading docker image")
                ExegolTUI.downloadDockerLayer(build_stream)
                logger.info("End of download")
