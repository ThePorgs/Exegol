> **Want to quick start without reading anything else? [Click here](#-get-started)**

<div align="center">

  <img alt="latest commit on master" width="600" src="https://raw.githubusercontent.com/ShutdownRepo/Exegol-docs/main/.assets/rounded_social_preview.png">
  <br><br>

  [![DockerHub type](https://img.shields.io/docker/cloud/automated/nwodtuhs/exegol)](https://hub.docker.com/r/nwodtuhs/exegol)
  [![DockerHub state](https://img.shields.io/docker/cloud/build/nwodtuhs/exegol)](https://hub.docker.com/r/nwodtuhs/exegol)
  [![image (compressed) max size](https://img.shields.io/docker/image-size/nwodtuhs/exegol/nightly?label=image%20(compressed)%20max%20size)](https://hub.docker.com/r/nwodtuhs/exegol)
  <br>
  [![PyPI](https://img.shields.io/pypi/v/Exegol?color=informational)](https://pypi.org/project/Exegol/)
  [![Downloads](https://static.pepy.tech/personalized-badge/exegol?period=total&units=international_system&left_color=grey&right_color=brightgreen&left_text=Downloads)](https://pepy.tech/project/exegol)
  [![Python](https://img.shields.io/badge/Python-3.7+-informational)](https://pypi.org/project/Exegol/)
  <br>

  <img alt="latest commit on master" src="https://img.shields.io/github/last-commit/ShutdownRepo/Exegol/master?label=latest%20release">
  <img alt="latest commit on dev" src="https://img.shields.io/github/last-commit/ShutdownRepo/Exegol/dev?label=latest%20dev">
  <br>
  <img alt="current version" src="https://img.shields.io/badge/linux-supported-success">
  <img alt="current version" src="https://img.shields.io/badge/windows-supported-success">
  <img alt="current version" src="https://img.shields.io/badge/mac-supported-success">
  <br>
  <a href="https://twitter.com/intent/follow?screen_name=_nwodtuhs" title="Follow"><img src="https://img.shields.io/twitter/follow/_nwodtuhs?label=Shutdown&style=social"></a>
  <a href="https://twitter.com/intent/follow?screen_name=Dramelac_" title="Follow"><img src="https://img.shields.io/twitter/follow/Dramelac_?label=Dramelac&style=social">
  <br><br>
  <a href="https://discord.gg/BcgXnRpqxd" title="Join us on Discord"><img src="https://raw.githubusercontent.com/ShutdownRepo/Exegol-docs/main/.assets/discord_join_us.png" width="150">
  </a><br><br>
</div>

> Exegol is a community-driven hacking environment, powerful and yet simple enough to be used by anyone in day to day engagements.
> Script kiddies use Kali Linux, real pentesters use Exegol 👀

![info](https://raw.githubusercontent.com/ShutdownRepo/Exegol-docs/main/.assets/exegol-info.png)

> Exegol was built with pentest engagements in mind, but it can also be used in CTFs, Bug Bounties, HackTheBox, OSCP, and so on.

- 🔧 **Tools**: many tools that are either installed manually or with apt, pip, go etc. Some of those tools are in kali, some are not. Exegol doesn't come with only ultra-famous tools, you will find ones that the community loves to use, even if it's in dev/new/not famous. Some tools are pre-configured and/or customized (colored output, custom NtChallengeResponse in Responder, custom queries in BloodHound, ...)
- 💡 **Resources**: many resources can be useful during engagements. Those resources are not referred to as "tools" since they need to be run on a pwned target, and not on the attacker machine (e.g. mimikatz, rubeus, ...).
- 📜 **History**: a populated history file that allows exegol users to save time and brain space by not having to remember every tool option and argument or checking the "help" every time.
- 🚀 **Aliases**: a file containing aliases that can be handful when using manually installed tools, or doing common operations.
- 🔎 **Usage**: a powerful Python3 wrapper used to manage Exegol container and image very easily (handles every docker operations).

## Project structure

Below are some bullet points to better understand how Exegol works
- This repository ([Exegol](https://github.com/ShutdownRepo/Exegol)) contains the code for the Python wrapper. It's the entrypoint of the Exegol project.
- The [Exegol-images](https://github.com/ShutdownRepo/Exegol-images) repo is loaded as a submodule. It includes all necessary assets to build Docker images.
- The [Exegol-resources](https://github.com/ShutdownRepo/Exegol-resources) repo is loaded as a submodule. It includes all resources mentioned previously (LinPEAS, WinPEAS, LinEnum, PrivescCheck, SysinternalsSuite, mimikatz, Rubeus, PowerSploit and many more.).
- The [Exegol-docs](https://github.com/ShutdownRepo/Exegol-docs) repo for the documentation, destined for users as well as developpers and contributors.
- Getting started with the Exegol project comes down to using the wrapper, which can be installed through pip or with the sources directly (see. [get started](#fast_forward-get-started)).

# 🚀 Get started

> Keep in mind that the wrapper is one thing, but in order to use Exegol, at least one Exegol docker image must be installed.
> Installing the wrapper and running it will do the next steps (which can be a bit lengthy)

## Pre-requisites
You need :
- git
- python3
- docker
- and at least 20GB of free storage

> To run exegol from the user environment without `sudo`, the user must have privileged rights equivalent to root.
> To grant yourself these rights, you can use the following command: `sudo usermod -aG docker $(id -u -n)`
>
> For more information: https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user

You also need python libraries listed in [requirements.txt](./requirements.txt) (installed automatically or manually depending on the installation method you choose).

## Installation using pip

Exegol's wrapper can be installed from pip repository. That's the entrypoint of the project, you'll be able to do all the rest from there.
```
python3 -m pip install exegol
```

> Remember that pip install binaries in `~/.local/bin`, which then must be in the `PATH` environment variable.

## Installation from sources

Exegol's wrapper can also be installed from sources. The wrapper then knows how to self-update.

```
git clone https://github.com/ShutdownRepo/Exegol
cd Exegol
python3 -m pip install --user --requirement requirements.txt
```

## Add exegol command

<details>
  <summary><h4>On Linux / macOS</h4></summary>

The exegol wrapper can then be added to the `PATH` throw symlink for direct access.

```bash
sudo ln -s $(pwd)/exegol.py /usr/local/bin/exegol
```

</details>

<details>
  <summary><h4>On Windows (with Powershell)</h4></summary>

The exegol wrapper can be added as a powershell command aliases and saved for persistence
in `$HOME\PowershellAliasesExport.txt`
then load from `$PROFILE` script at powershell startup.

```powershell
$AliasFile = "$HOME\PowershellAliasesExport.txt"
Set-Alias -Name exegol -Value "$(pwd)\exegol.py"
Get-Alias -Name "exegol" | Export-Alias -Path $AliasFile
echo "Import-Alias '$AliasFile'" >> $PROFILE
```

> Warning! To automatically load aliases from the .ps1 file, the `Get-ExecutionPolicy` powershell must be set
> to `RemoteSigned`

If the configuration is not correct it can be configured as **administrator** with the following command:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned
```

</details>

## User configuration

Exegol installs and uses a yaml configuration file, located in the user's home directory: `~/.exegol` (
or `/home/<user>/.exegol`).
The configuration file indicates paths to three host directories shared with the containers:

- "my resources": dedicated to the user to customize his environment and tools. Defaults
  to `/home/<user>/.exegol/my-resources`.
- "exegol resources": official exegol resources from
  the [Exegol-resources](https://github.com/ShutdownRepo/Exegol-resources) repo. Defaults
  to `/path/to/Exegol/exegol-resources`.
- "private workspace": a dedicated workspace for each container, shared with the host. Defaults
  to `/home/<user>/.exegol/workspaces`.

## Exegol images

It is possible to install an exegol image using the wrapper with the following command: `exegol install <image_name>`

| Image name | Description                                                                                        |
|------------|----------------------------------------------------------------------------------------------------|
| full       | Includes all the tools supported by Exegol (warning: this is the heaviest image)                   |
| nightly    | (for developers and advanced users) contains the latest updates. This image can be unstable!       |
| ad         | Includes tools for Active Directory / internal pentesting only.                                    |
| web        | Includes tools for Web pentesting only.                                                            |
| light      | Includes the lightest and most used tools for various purposes.                                    |
| osint      | Includes tools for OSINT.                                                                          |

# 🔎 Usage
Below are some examples of usage. For more examples, run the following command: `exegol <action> -h` (action: install/start/stop/etc.).

- Install an Exegol image : `exegol install`
- Create/start/enter a container : `exegol start`
- Show info on containers and images : `exegol info`
- Stop a container : `exegol stop`
- Remove a container : `exegol remove`
- Uninstall an image : `exegol uninstall`
- Get help and advanced usage : `exegol --help`

> ⚠️ remember that Exegol uses Docker images and containers. Understanding the difference is essential to understand Exegol.
> - **image**: think of it as an immutable template. They cannot be executed as-is and serve as input for containers. It's not possible to open a shell in an image.
> - **container**: a container rests upon an image. A container is created for a certain image at a certain time. It's possible to open a shell in a container. Careful though, once a container is created, updating the image it was created upon won't have any impact on the container. In order to enjoy the new things, a new container must be created upon that updated image.

![help](https://raw.githubusercontent.com/ShutdownRepo/Exegol-docs/main/.assets/exegol-help.png)

By default, Exegol will create containers with display sharing allowing GUI-based programs to run, with network host sharing, and a few others things.
Below is an example of a GUI app running in an Exegol container.

![display_sharing](https://raw.githubusercontent.com/ShutdownRepo/Exegol-docs/main/.assets/example-display-sharing.gif)

<details>
  <summary><h2>Default container configuration</h2></summary>
  When creating a new container with `exegol start`, it gets the following configuration by default (which can be tweaked, see `exegol start -h`)

  - GUI (X11 sharing) enabled
  - Host network sharing enabled (host's network interfaces are shared with the container)
  - Timezone sharing enabled
  - Exegol-resources sharing enabled (`/path/to/Exegol/exegol-resources` maps to `/opt/resources` in the container)
  - Personal resources ("My resources") sharing enabled (`~/.exegol/my-resources` maps to `/opt/my-resources` in the container)
  - Workspace sharing enabled (`~/.exegol/workspaces/CONTAINER_NAME` maps to `/workspace` in the container)
  
  > Users should keep in mind that when a container is created, it's configuration cannot be modified. If you want another configuration, create another one.
  
  ![start_verbose](https://raw.githubusercontent.com/ShutdownRepo/Exegol-docs/main/.assets/exegol-start.png)
</details>

<details>
  <summary><h2>Credentials</h2></summary>
  Some tools are pre-configured with the following credentials
  
  | Element | User | Password |
  | ------- | ---- | -------- |
  | neo4j database | neo4j | exegol4thewin |
  | bettercap ui | bettercap | exegol4thewin |
  | trilium | trilium | exegol4thewin |
  | empire | empireadmin | exegol4thewin |
  | wso-webshell (PHP) | | exegol4thewin |
</details>

# 👏 Credits
Credits and thanks go to every infosec addicts that contribute and share but most specifically to 
- [@th1b4ud](https://twitter.com/th1b4ud) for the base ["Kali Linux in 3 seconds with Docker"](https://thibaud-robin.fr/articles/docker-kali/).
- [dramelac_](https://twitter.com/dramelac_) for working on [Exegol](https://github.com/ShutdownRepo/Exegol) (the wrapper)
- [LamaBzh](https://twitter.com/rode_tony) for working on [Exegol-images](https://github.com/ShutdownRepo/Exegol-images)**
