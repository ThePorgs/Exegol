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

You can refer to the [Exegol documentations](https://exegol.readthedocs.io/).

## Project structure

Below are some bullet points to better understand how Exegol works
- This repository ([Exegol](https://github.com/ShutdownRepo/Exegol)) contains the code for the Python wrapper. It's the entrypoint of the Exegol project. The wrapper can be installed from sources, but [a PyPI package](https://pypi.org/project/Exegol/) is available.
- The [Exegol-images](https://github.com/ShutdownRepo/Exegol-images) repo is loaded as a submodule. It includes all necessary assets to build Docker images. Notabene: the image are already built and offered on [the official Dockerhub registry](https://hub.docker.com/repository/docker/nwodtuhs/exegol).
- The [Exegol-resources](https://github.com/ShutdownRepo/Exegol-resources) repo is loaded as a submodule. It includes all resources mentioned previously (LinPEAS, WinPEAS, LinEnum, PrivescCheck, SysinternalsSuite, mimikatz, Rubeus, PowerSploit and many more.).
- The [Exegol-docs](https://github.com/ShutdownRepo/Exegol-docs) repo for the documentation, destined for users as well as developpers and contributors. The GitHub repo holds the sources that are compiled on https://exegol.readthedocs.io/.

# Sponsors

<div align="center">
  <a href="https://www.capgemini.com/" title="Follow">
    <img width="300" src="https://upload.wikimedia.org/wikipedia/fr/thumb/b/b5/Capgemini_Logo.svg/1280px-Capgemini_Logo.svg.png">
  </a>
</div>

Dramelac and I work at *Capgemini* and we thank them for allocating some time for us to develop and maintain Exegol! Visit Capgemini website at https://www.capgemini.com/.

___

<div align="center">
  <a href="https://www.hackthebox.com/" title="Follow">
    <img width="300" src="https://www.hackthebox.com/images/logo600.png">
  </a>
</div>

We also thank *HackTheBox* for continuously supporting the community and for helping us financially to acquire the necessary hardware for supporting multiple architectures (AMD64, ARM64). Show some love at https://www.hackthebox.com/ !

