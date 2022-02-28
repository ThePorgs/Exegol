import os
import re
from typing import Union, Optional, List, Dict, Type, Generator, Set, cast, Sequence

from rich import box
from rich.align import Align
from rich.progress import TextColumn, BarColumn, TransferSpeedColumn, TimeElapsedColumn, TimeRemainingColumn, TaskID
from rich.prompt import Prompt
from rich.table import Table

from wrapper.console.ConsoleFormat import boolFormatter, getColor
from wrapper.console.ExegolProgress import ExegolProgress
from wrapper.console.ExegolPrompt import Confirm
from wrapper.console.LayerTextColumn import LayerTextColumn
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.model.ExegolContainer import ExegolContainer
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.model.SelectableInterface import SelectableInterface
from wrapper.utils.ExeLog import logger, console, ExeLog


# Class gathering different methods of Terminal User Interface (or TUI)
class ExegolTUI:

    @staticmethod
    def downloadDockerLayer(stream: Generator, quick_exit: bool = False):
        """Rich interface for docker image layer download from SDK stream"""
        layers: Set[str] = set()
        layers_downloaded: Set[str] = set()
        layers_extracted: Set[str] = set()
        downloading: Dict[str, TaskID] = {}
        extracting: Dict[str, TaskID] = {}
        # Create progress bar with columns
        with ExegolProgress(TextColumn("{task.description}", justify="left"),
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
            task_layers_download = progress.add_task("[bold red]Downloading layers...", total=0)
            task_layers_extract = progress.add_task("[bold gold1]Extracting layers...", total=0, start=False)
            for line in stream:  # Receiving stream from docker API
                status = line.get("status", '')
                error = line.get("error", '')
                layer_id = line.get("id")
                if error != "":
                    logger.error(f"Docker download error: {error}")
                    logger.critical(f"An error occurred during the image download. Exiting.")
                if status == "Pulling fs layer":  # Identify new layer to download
                    layers.add(layer_id)
                    progress.update(task_layers_download, total=len(layers))
                    progress.update(task_layers_extract, total=len(layers))
                elif "Pulling from " in status:  # Rename task with image name
                    progress.getTask(task_layers_download).description = \
                        f"[bold red]Downloading {status.replace('Pulling from ', '')}:{line.get('id', 'latest')}"
                    progress.getTask(task_layers_extract).description = \
                        f"[bold gold1]Extracting {status.replace('Pulling from ', '')}:{line.get('id', 'latest')}"
                elif status == "Download complete" or status == "Pull complete":  # Mark task as complete and remove it from the pool
                    # Select task / layer pool depending on the status
                    task_pool = downloading
                    layer_pool = layers_downloaded
                    if status == "Pull complete":
                        task_pool = extracting
                        layer_pool = layers_extracted
                    # Tagging current layer as ended
                    layer_pool.add(layer_id)
                    # Remove finished layer progress bar
                    layer_task = task_pool.get(layer_id)
                    if layer_task is not None:
                        progress.remove_task(layer_task)  # Remove progress bar
                        task_pool.pop(layer_id)  # Remove task from pool
                    # Update global task completion status
                    progress.update(task_layers_download, completed=len(layers_downloaded))
                    progress.update(task_layers_extract, completed=len(layers_extracted))
                elif status == "Downloading" or status == "Extracting":  # Handle download or extract progress
                    task_pool = downloading
                    if status == "Extracting":
                        task_pool = extracting
                        if not progress.getTask(task_layers_extract).started:
                            progress.start_task(task_layers_extract)
                    task_id = task_pool.get(layer_id)
                    if task_id is None:  # If this is a new layer, create a new task accordingly
                        task_id = progress.add_task(
                            f"[{'blue' if status == 'Downloading' else 'green'}]{status} {layer_id}",
                            total=line.get("progressDetail", {}).get("total", 100),
                            layer=layer_id)
                        task_pool[layer_id] = task_id
                    # Updating task progress
                    progress.update(task_id, completed=line.get("progressDetail", {}).get("current", 100))
                    # TODO add checksum step
                elif "Image is up to date" in status or "Status: Downloaded newer image for" in status:
                    logger.success(status)
                    if quick_exit:
                        break
                else:
                    logger.debug(line)

    @staticmethod
    def buildDockerImage(build_stream: Generator):
        """Rich interface for docker image building from SDK stream"""
        for line in build_stream:
            stream_text = line.get("stream", '')
            error_text = line.get("error", '')
            if error_text != "":
                logger.error(f"Docker build error: {error_text}")
                logger.critical(
                    f"An error occurred during the image build (code: {line.get('errorDetail', {}).get('code', '?')}). Exiting.")
            if stream_text.strip() != '':
                if "Step" in stream_text:
                    logger.info(stream_text.rstrip())
                elif "--->" in stream_text or \
                        "Removing intermediate container " in stream_text or \
                        re.match(r"Successfully built [a-z0-9]{12}", stream_text) or \
                        re.match(r"^Successfully tagged ", stream_text):
                    logger.verbose(stream_text.rstrip())
                else:
                    logger.raw(stream_text, level=ExeLog.ADVANCED)
            if ': FROM ' in stream_text:
                logger.info("Downloading docker image")
                ExegolTUI.downloadDockerLayer(build_stream, quick_exit=True)

    @staticmethod
    def printTable(data: Union[Sequence[SelectableInterface], Sequence[str]], title: Optional[str] = None):
        """Printing Rich table for a list of object"""
        table = Table(title=title, show_header=True, header_style="bold blue", border_style="grey35",
                      box=box.SQUARE, title_justify="left")
        if len(data) == 0:
            logger.debug("No data supplied")
            return
        else:
            if type(data[0]) is ExegolImage:
                ExegolTUI.__buildImageTable(table, cast(Sequence[ExegolImage], data))
            elif type(data[0]) is ExegolContainer:
                ExegolTUI.__buildContainerTable(table, cast(Sequence[ExegolContainer], data))
            elif type(data[0]) is str:
                if title is not None:
                    ExegolTUI.__buildStringTable(table, cast(Sequence[str], data), cast(str, title))
                else:
                    ExegolTUI.__buildStringTable(table, cast(Sequence[str], data))
            else:
                logger.error(f"Print table of {type(data[0])} is not implemented")
                raise NotImplementedError
        console.print(table)

    @staticmethod
    def __buildImageTable(table: Table, data: Sequence[ExegolImage]):
        """Building Rich table from a list of ExegolImage"""
        table.title = "[not italic]:flying_saucer: [/not italic][gold3][g]Available images[/g][/gold3]"
        # Define columns
        verbose_mode = logger.isEnabledFor(ExeLog.VERBOSE)
        debug_mode = logger.isEnabledFor(ExeLog.ADVANCED)
        if verbose_mode:
            table.add_column("Id")
        table.add_column("Image tag")
        if verbose_mode:
            table.add_column("Download size")
            table.add_column("Disk size")
        else:
            # Depending on whether the image has already been downloaded or not,
            # it will show the download size or the size on disk
            table.add_column("Size")
        table.add_column("Status")
        # Load data into the table
        for image in data:
            if image.isLocked() and not debug_mode:
                continue
            if verbose_mode:
                table.add_row(image.getLocalId(), image.getName(), image.getDownloadSize(), image.getRealSize(),
                              image.getStatus())
            else:
                table.add_row(image.getName(), image.getSize(), image.getStatus())

    @staticmethod
    def __buildContainerTable(table: Table, data: Sequence[ExegolContainer]):
        """Building Rich table from a list of ExegolContainer"""
        table.title = "[not italic]:alien: [/not italic][gold3][g]Available containers[/g][/gold3]"
        # Define columns
        verbose_mode = logger.isEnabledFor(ExeLog.VERBOSE)
        debug_mode = logger.isEnabledFor(ExeLog.ADVANCED)
        if verbose_mode:
            table.add_column("Id")
        table.add_column("Container tag")
        table.add_column("State")
        table.add_column("Image tag")
        table.add_column("Configurations")
        if verbose_mode:
            table.add_column("Mounts")
            table.add_column("Devices")
            table.add_column("Envs")
        # Load data into the table
        for container in data:
            if verbose_mode:
                table.add_row(container.getId(), container.name, container.getTextStatus(), container.image.getName(),
                              container.config.getTextFeatures(verbose_mode),
                              container.config.getTextMounts(debug_mode),
                              container.config.getTextDevices(debug_mode), container.config.getTextEnvs(debug_mode))
            else:
                table.add_row(container.name, container.getTextStatus(), container.image.getName(),
                              container.config.getTextFeatures(verbose_mode))

    @staticmethod
    def __buildStringTable(table: Table, data: Sequence[str], title: str = "Key"):
        """Building a simple Rich table from a list of string"""
        table.title = None
        # Define columns
        table.add_column(title)
        # Load data into the table
        for string in data:
            table.add_row(string)

    @classmethod
    def selectFromTable(cls,
                        data: Sequence[SelectableInterface],
                        object_type: Optional[Type] = None,
                        default: Optional[str] = None,
                        allow_None: bool = False) -> Union[SelectableInterface, str]:
        """Return an object (implementing SelectableInterface) selected by the user
        Return a str when allow_none is true and no object have been selected
        Raise IndexError of the data list is empty."""
        cls.__isInteractionAllowed()
        # Check if there is at least one object in the list
        if len(data) == 0:
            if object_type is ExegolImage:
                logger.warning("No images are installed")
            elif object_type is ExegolContainer:
                logger.warning("No containers have been created yet")
            else:
                # Using container syntax by default
                logger.warning("No containers have been created yet")
            raise IndexError
        object_type = type(data[0])
        object_name = "container" if object_type is ExegolContainer else "image"
        action = "create" if object_type is ExegolContainer else "build"
        # Print data list
        cls.printTable(data)
        # Get a list of every choice available
        choices: Optional[List[str]] = [obj.getKey() for obj in data]
        # If no default have been supplied, using the first one
        if default is None:
            default = cast(List[str], choices)[0]
        # When allow_none is enable, disabling choices restriction
        if allow_None:
            choices = None
            logger.info(
                f"You can use a name that does not already exist to {action} a new {object_name}"
                f"{' from local sources' if object_type is ExegolImage else ''}")
        while True:
            choice = Prompt.ask(
                f"[blue][?][/blue] Select {'an' if object_type is ExegolImage else 'a'} {object_name} by his name",
                default=default, choices=choices,
                show_choices=False)
            for o in data:
                if choice == o:
                    return o
            if allow_None:
                if Confirm(
                        f"No {object_name} is available under this name, do you want to {action} it?",
                        default=True):
                    return choice
                logger.info(f"[red]Please select one of the available {object_name}s[/red]")
            else:
                logger.critical(f"Unknown error, cannot fetch selected object.")

    @classmethod
    def multipleSelectFromTable(cls,
                                data: Sequence[SelectableInterface],
                                object_type: Type = None,
                                default: Optional[str] = None) -> Sequence[SelectableInterface]:
        """Return a list of object (implementing SelectableInterface) selected by the user
        Raise IndexError of the data list is empty."""
        cls.__isInteractionAllowed()
        result = []
        pool = cast(List[SelectableInterface], data).copy()
        if object_type is None and len(pool) > 0:
            object_type = type(pool[0])
        if object_type is ExegolContainer:
            object_subject = "container"
        elif object_type is ExegolImage:
            object_subject = "image"
        else:
            object_subject = "object"
        while True:
            selected = cast(SelectableInterface, cls.selectFromTable(pool, object_type, default))
            result.append(selected)
            pool.remove(selected)
            if len(pool) == 0:
                return result
            elif not Confirm(f"Do you want to select another {object_subject}?", default=False):
                return result

    @classmethod
    def selectFromList(cls,
                       data: Union[Dict[str, str], List[str]],
                       subject: str = "an option",
                       title: str = "Options",
                       default: Optional[str] = None) -> str:
        """if data is list(str): Return a string selected by the user
        if data is dict: list keys and return corresponding value
        Raise IndexError of the data list is empty."""
        cls.__isInteractionAllowed()
        if len(data) == 0:
            logger.warning("No options were found")
            raise IndexError
        if type(data) is dict:
            submit_data = list(data.keys())
        else:
            submit_data = cast(List[str], data)
        cls.printTable(submit_data, title=title)
        if default is None:
            default = submit_data[0]
        choice = Prompt.ask(f"[blue][?][/blue] Select {subject}", default=default, choices=submit_data,
                            show_choices=False)
        if type(data) is dict:
            return data[choice]
        else:
            return choice

    @classmethod
    def printContainerRecap(cls, container: ExegolContainerTemplate):
        # Fetch data
        devices = container.config.getDevices()
        envs = container.config.getEnvs()
        sysctls = container.config.getSysctls()
        capabilities = container.config.getCapabilities()
        volumes = container.config.getTextMounts(logger.isEnabledFor(ExeLog.ADVANCED))

        # Color code
        privilege_color = "salmon1"
        path_color = "chartreuse1"

        logger.empty_line()
        recap = Table(border_style="grey35", box=box.SQUARE, title_justify="left", show_header=True)
        recap.title = "[not italic]:white_medium_star: [/not italic][gold3][g]Container summary[/g][/gold3]"
        # Header
        recap.add_column(f"[bold blue]Name[/bold blue]{os.linesep}[bold blue]Image[/bold blue]", justify="right")
        recap.add_column(f"{container.name}{os.linesep}{container.image.getName()} ({container.image.getStatus()})")
        # Main features
        recap.add_row("[bold blue]GUI[/bold blue]", boolFormatter(container.config.isGUIEnable()))
        recap.add_row("[bold blue]Network[/bold blue]", container.config.getNetworkMode())
        recap.add_row("[bold blue]Timezone[/bold blue]", boolFormatter(container.config.isTimezoneShared()))
        recap.add_row("[bold blue]Common resources[/bold blue]",
                      boolFormatter(container.config.isCommonResourcesEnable()))
        recap.add_row("[bold blue]VPN[/bold blue]", container.config.getVpnName())
        recap.add_row("[bold blue]Privileged[/bold blue]", boolFormatter(container.config.getPrivileged()))
        if len(capabilities) > 0:
            recap.add_row(f"[bold blue]Capabilities[/bold blue]",
                          f"[{privilege_color}]{', '.join(capabilities)}[/{privilege_color}]")
        if container.config.isWorkspaceCustom():
            recap.add_row("[bold blue]Workspace[/bold blue]",
                          f'[{path_color}]{container.config.getHostWorkspacePath()}[/{path_color}]')
        else:
            recap.add_row("[bold blue]Workspace[/bold blue]", '[orange3]Dedicated[/orange3]')
        if len(devices) > 0:
            recap.add_row("[bold blue]Devices[/bold blue]",
                          os.linesep.join([f"{device.split(':')[0]}:{device.split(':')[-1]}" for device in devices]))
        if len(envs) > 0:
            recap.add_row("[bold blue]Envs[/bold blue]",
                          os.linesep.join([f"{key} = {value}" for key, value in envs.items()]))
        if len(volumes) > 0:
            recap.add_row("[bold blue]Volumes[/bold blue]", volumes.strip())
        if len(sysctls) > 0:
            recap.add_row("[bold blue]Systctls[/bold blue]", os.linesep.join(
                [f"[{privilege_color}]{key}[/{privilege_color}] = {getColor(value)[0]}{value}{getColor(value)[1]}" for
                 key, value in sysctls.items()]))
        console.print(recap)
        logger.empty_line()

    @classmethod
    def __isInteractionAllowed(cls):
        if not ParametersManager().interactive_mode:  # TODO improve non-interactive mode
            logger.critical(f'A required information is missing. Exiting.')