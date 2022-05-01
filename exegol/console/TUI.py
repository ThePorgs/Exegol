import os
import re
from typing import Union, Optional, List, Dict, Type, Generator, Set, cast, Sequence, Tuple

from rich import box
from rich.progress import TextColumn, BarColumn, TransferSpeedColumn, TimeElapsedColumn, TimeRemainingColumn, TaskID
from rich.prompt import Prompt
from rich.table import Table

from exegol.console.ConsoleFormat import boolFormatter, getColor, richLen
from exegol.console.ExegolProgress import ExegolProgress
from exegol.console.ExegolPrompt import Confirm
from exegol.console.LayerTextColumn import LayerTextColumn
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.model.ExegolContainer import ExegolContainer
from exegol.model.ExegolContainerTemplate import ExegolContainerTemplate
from exegol.model.ExegolImage import ExegolImage
from exegol.model.SelectableInterface import SelectableInterface
from exegol.utils.ExeLog import logger, console, ExeLog


class ExegolTUI:
    """Class gathering different methods of Terminal User Interface (or TUI)"""

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
                    progressDetail = line.get("progressDetail", {})
                    if task_id is None:  # If this is a new layer, create a new task accordingly
                        task_id = progress.add_task(
                            f"[{'blue' if status == 'Downloading' else 'magenta'}]{status} {layer_id}",
                            total=progressDetail.get("total", 100),
                            layer=layer_id)
                        task_pool[layer_id] = task_id
                    # Updating task progress
                    progress.update(task_id, completed=progressDetail.get("current", 100))
                    if status == "Extracting" and progressDetail.get("current", 0) == progressDetail.get("total", 100):
                        progress.update(task_id, description=f"[green]Checksum {layer_id} ...")
                elif "Image is up to date" in status or "Status: Downloaded newer image for" in status:
                    logger.success(status)
                    if quick_exit:
                        break
                else:
                    logger.debug(line)

    @staticmethod
    def buildDockerImage(build_stream: Generator):
        """Rich interface for docker image building from SDK stream"""
        # Prepare log file
        logfile = None
        if ParametersManager().build_log is not None:
            # Opening log file in line buffering mode (1) to support tail -f [file]
            logfile = open(ParametersManager().build_log, 'a', buffering=1)
        # Follow stream
        for line in build_stream:
            stream_text = line.get("stream", '')
            error_text = line.get("error", '')
            if logfile is not None:
                logfile.write(stream_text)
                logfile.write(error_text)
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
        if logfile is not None:
            logfile.close()

    @staticmethod
    def printTable(data: Union[Sequence[SelectableInterface], Sequence[str], Sequence[Dict[str, str]]], title: Optional[str] = None):
        """Printing Rich table for a list of object"""
        logger.empty_line()
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
            elif type(data[0]) is dict:
                ExegolTUI.__buildDictTable(table, cast(Sequence[Dict[str, str]], data))
            else:
                logger.error(f"Print table of {type(data[0])} is not implemented")
                raise NotImplementedError
        console.print(table)
        logger.empty_line()

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
            table.add_column("Size on disk")
            table.add_column("Build date (UTC)")
        else:
            # Depending on whether the image has already been downloaded or not,
            # it will show the download size or the size on disk
            table.add_column("Size")
        table.add_column("Status")
        # Load data into the table
        for image in data:
            # ToBeRemoved images are only shown in verbose mode
            if image.isLocked() and not verbose_mode:
                continue
            if verbose_mode:
                table.add_row(image.getLocalId(), image.getDisplayName(), image.getDownloadSize(),
                              image.getRealSize(), image.getBuildDate(), image.getStatus())
            else:
                table.add_row(image.getDisplayName(), image.getSize(), image.getStatus())

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
                table.add_row(container.getId(), container.name, container.getTextStatus(), container.image.getDisplayName(),
                              container.config.getTextFeatures(verbose_mode),
                              container.config.getTextMounts(debug_mode),
                              container.config.getTextDevices(debug_mode), container.config.getTextEnvs(debug_mode))
            else:
                table.add_row(container.name, container.getTextStatus(), container.image.getDisplayName(),
                              container.config.getTextFeatures(verbose_mode))

    @staticmethod
    def __buildStringTable(table: Table, data: Sequence[str], title: str = "Key"):
        """Building a simple Rich table from a list of string"""
        table.title = title
        table.min_width = richLen(title)
        # Define columns
        table.add_column(title)
        table.show_header = False
        # Load data into the table
        for string in data:
            table.add_row(string)

    @staticmethod
    def __buildDictTable(table: Table, data_array: Sequence[Dict[str, str]]):
        """Building a simple Rich table from a list of string"""
        # Define columns from dict keys
        for column in data_array[0].keys():
            table.add_column(column.capitalize())
        # Load data into the table
        for data in data_array:
            # Array is directly pass as *args to handle dynamic columns number
            table.add_row(*data.values())

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
                f"[bold blue][?][/bold blue] Select {'an' if object_type is ExegolImage else 'a'} {object_name} by its name",
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
                       default: Optional[str] = None) -> Union[str, Tuple[str, str]]:
        """if data is list(str): Return a string selected by the user
        if data is dict: list keys and return a tuple of the selected key corresponding value
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
        choice = Prompt.ask(f"[bold blue][?][/bold blue] Select {subject}", default=default, choices=submit_data,
                            show_choices=False)
        if type(data) is dict:
            return choice, data[choice]
        else:
            return choice

    @classmethod
    def printContainerRecap(cls, container: ExegolContainerTemplate):
        # Fetch data
        devices = container.config.getTextDevices(logger.isEnabledFor(ExeLog.VERBOSE))
        envs = container.config.getTextEnvs(logger.isEnabledFor(ExeLog.VERBOSE))
        sysctls = container.config.getSysctls()
        capabilities = container.config.getCapabilities()
        volumes = container.config.getTextMounts(logger.isEnabledFor(ExeLog.VERBOSE))

        # Color code
        privilege_color = "bright_magenta"
        path_color = "magenta"

        logger.empty_line()
        recap = Table(border_style="grey35", box=box.SQUARE, title_justify="left", show_header=True)
        recap.title = "[not italic]:white_medium_star: [/not italic][gold3][g]Container summary[/g][/gold3]"
        # Header
        recap.add_column(f"[bold blue]Name[/bold blue]{os.linesep}[bold blue]Image[/bold blue]", justify="right")
        container_info_header = f"{container.name}{os.linesep}{container.image.getName()}"
        if "N/A" not in container.image.getImageVersion():
            container_info_header += f" - v.{container.image.getImageVersion()}"
        if "Unknown" not in container.image.getStatus():
            container_info_header += f" ({container.image.getStatus(include_version=False)})"
        recap.add_column(container_info_header)
        # Main features
        recap.add_row("[bold blue]GUI[/bold blue]", boolFormatter(container.config.isGUIEnable()))
        recap.add_row("[bold blue]Network[/bold blue]", container.config.getNetworkMode())
        recap.add_row("[bold blue]Timezone[/bold blue]", boolFormatter(container.config.isTimezoneShared()))
        recap.add_row("[bold blue]Exegol resources[/bold blue]", boolFormatter(container.config.isExegolResourcesEnable()) +
                      f"{'[bright_black](/opt/resources)[/bright_black]' if container.config.isExegolResourcesEnable() else ''}")
        recap.add_row("[bold blue]My resources[/bold blue]", boolFormatter(container.config.isSharedResourcesEnable()) +
                      f"{'[bright_black](/my-resources)[/bright_black]' if container.config.isSharedResourcesEnable() else ''}")
        recap.add_row("[bold blue]VPN[/bold blue]", container.config.getVpnName())
        if container.config.getPrivileged() is True:
            recap.add_row("[bold blue]Privileged[/bold blue]", '[orange3]On :fire:[/orange3]')
        else:
            recap.add_row("[bold blue]Privileged[/bold blue]", "[green]Off :heavy_check_mark:[/green]")
        if len(capabilities) > 0:
            recap.add_row(f"[bold blue]Capabilities[/bold blue]",
                          f"[{privilege_color}]{', '.join(capabilities)}[/{privilege_color}]")
        if container.config.isWorkspaceCustom():
            recap.add_row("[bold blue]Workspace[/bold blue]",
                          f'[{path_color}]{container.config.getHostWorkspacePath()}[/{path_color}] [bright_black](/workspace)[/bright_black]')
        else:
            recap.add_row("[bold blue]Workspace[/bold blue]", '[bright_magenta]Dedicated[/bright_magenta] [bright_black](/workspace)[/bright_black]')
        if len(devices) > 0:
            recap.add_row("[bold blue]Devices[/bold blue]", devices.strip())
        if len(envs) > 0:
            recap.add_row("[bold blue]Envs[/bold blue]", envs.strip())
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
        # if not ParametersManager().interactive_mode:  # TODO improve non-interactive mode
        #    logger.critical(f'A required information is missing. Exiting.')
        pass
