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

> Exegol is a community-driven hacking environment, powerful and yet simple enough to be used by anyone in day to day engagements. Exegol is the best solution to deploy powerful hacking environments securely, easily, professionally.
> Exegol fits pentesters, CTF players, bug bounty hunters, researchers, beginners and advanced users, defenders, from stylish macOS users and corporate Windows pros to UNIX-like power users.

# Getting started

Checkout the [Exegol documentations](https://exegol.readthedocs.io/).

> As of November 2022, the docs are still a work in progress and are not 100% complete yet.

## Project structure

Below are some bullet points to better understand how Exegol works
- This repository ([Exegol](https://github.com/ShutdownRepo/Exegol)) contains the code for the Python wrapper. It's the entrypoint of the Exegol project. The wrapper can be installed from sources, but [a PyPI package](https://pypi.org/project/Exegol/) is available.
- The [Exegol-images](https://github.com/ShutdownRepo/Exegol-images) repo is loaded as a submodule. It includes all necessary assets to build Docker images. Notabene: the image are already built and offered on [the official Dockerhub registry](https://hub.docker.com/repository/docker/nwodtuhs/exegol).
- The [Exegol-resources](https://github.com/ShutdownRepo/Exegol-resources) repo is loaded as a submodule. It includes all resources mentioned previously (LinPEAS, WinPEAS, LinEnum, PrivescCheck, SysinternalsSuite, mimikatz, Rubeus, PowerSploit and many more.).
- The [Exegol-docs](https://github.com/ShutdownRepo/Exegol-docs) repo for the documentation, destined for users as well as developpers and contributors. The GitHub repo holds the sources that are compiled on https://exegol.readthedocs.io/.

# 🚀 Get started

> Keep in mind that the wrapper is one thing, but in order to use Exegol, at least one Exegol docker image must be installed.
> Installing the wrapper and running it will do the next steps (which can be a bit lengthy)

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


# 🔎 Usage

By default, Exegol will create containers with display sharing allowing GUI-based programs to run, with network host sharing, and a few others things.
Below is an example of a GUI app running in an Exegol container.

![display_sharing](https://raw.githubusercontent.com/ShutdownRepo/Exegol-docs/main/.assets/example-display-sharing.gif)

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

# Sponsors

Dramelac and I work at Capgemini and we thank them for allocating some time for us to develop and maintain Exegol!

We also thank HackTheBox for continuously supporting the community and for helping us financially to acquire the necessary hardware for supporting multiple architectures (AMD64, ARM64).  

<div align="center">
  <a href="https://www.capgemini.com/" title="Follow">
    <img width="300" src="https://upload.wikimedia.org/wikipedia/fr/thumb/b/b5/Capgemini_Logo.svg/1280px-Capgemini_Logo.svg.png">
  </a>
  <a href="https://www.hackthebox.com/" title="Follow">
    <img width="300" src="https://www.hackthebox.com/images/logo600.png">
  </a>
</div>

