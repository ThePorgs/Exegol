<div align="center">
  <img alt="latest commit on master" width="600" src="https://raw.githubusercontent.com/ThePorgs/Exegol-docs/main/.assets/rounded_social_preview.png">
  <br><br>
  <a target="_blank" rel="noopener noreferrer" href="https://pypi.org/project/Exegol" title=""><img src="https://img.shields.io/pypi/v/Exegol?color=informational" alt="pip package version"></a>
  <img alt="Python3.7" src="https://img.shields.io/badge/Python-3.7+-informational">
  <img alt="latest commit on master" src="https://img.shields.io/docker/pulls/nwodtuhs/exegol.svg?label=downloads">
  <br><br>
  <img alt="latest commit on master" src="https://img.shields.io/github/last-commit/ThePorgs/Exegol/master?label=latest%20release">
  <img alt="latest commit on dev" src="https://img.shields.io/github/last-commit/ThePorgs/Exegol/dev?label=latest%20dev">
  <br><br>
  <img alt="current version" src="https://img.shields.io/badge/linux-supported-success">
  <img alt="current version" src="https://img.shields.io/badge/windows-supported-success">
  <img alt="current version" src="https://img.shields.io/badge/mac-supported-success">
  <br>
  <img alt="amd64" src="https://img.shields.io/badge/amd64%20(x86__64)-supported-success">
  <img alt="arm64" src="https://img.shields.io/badge/arm64%20(aarch64)-supported-success">
  <br><br>
  <a target="_blank" rel="noopener noreferrer" href="https://twitter.com/intent/follow?screen_name=_nwodtuhs" title="Follow"><img src="https://img.shields.io/twitter/follow/_nwodtuhs?label=Shutdown&style=social" alt="Twitter Shutdown"></a>
  <a target="_blank" rel="noopener noreferrer" href="https://twitter.com/intent/follow?screen_name=Dramelac_" title="Follow"><img src="https://img.shields.io/twitter/follow/Dramelac_?label=Dramelac&style=social" alt="Twitter Dramelac"></a>
  <br>
  <a target="_blank" rel="noopener noreferrer" href="https://www.blackhat.com/eu-22/arsenal/schedule/index.html#exegol-29180" title="Schedule">
   <img alt="Black Hat Europe 2022" src="https://img.shields.io/badge/Black%20Hat%20Arsenal-Europe%202022-blueviolet">
  </a>
  <a target="_blank" rel="noopener noreferrer" href="https://www.blackhat.com/asia-23/arsenal/schedule/#exegol-professional-hacking-setup-30815" title="Schedule">
   <img alt="Black Hat Asia 2023" src="https://img.shields.io/badge/Black%20Hat%20Arsenal-Asia%202023-blueviolet">
  </a>
  <a target="_blank" rel="noopener noreferrer" href="https://www.blackhat.com/us-23/arsenal/schedule/#exegol-professional-hacking-setup-31711" title="Schedule">
   <img alt="Black Hat USA 2023" src="https://img.shields.io/badge/Black%20Hat%20Arsenal-USA%202023-blueviolet">
  </a>
  <br><br>
  <a target="_blank" rel="noopener noreferrer" href="https://discord.gg/cXThyp7D6P" title="Join us on Discord"><img src="https://raw.githubusercontent.com/ThePorgs/Exegol-docs/main/.assets/discord_join_us.png" width="150" alt="Join us on Discord"></a>
  <br><br>
</div>

> Exegol is a community-driven hacking environment, powerful and yet simple enough to be used by anyone in day to day engagements. Exegol is the best solution to deploy powerful hacking environments securely, easily, professionally.
> Exegol fits pentesters, CTF players, bug bounty hunters, researchers, beginners and advanced users, defenders, from stylish macOS users and corporate Windows pros to UNIX-like power users.

# Getting started

You can refer to the [Exegol documentation](https://exegol.readthedocs.io/en/latest/getting-started/install.html).

> Full documentation homepage: https://exegol.rtfd.io/.

## Project structure

Below are some bullet points to better understand how Exegol works
- This repository ([Exegol](https://github.com/ThePorgs/Exegol)) contains the code for the Python wrapper. It's the entrypoint of the Exegol project. The wrapper can be installed from sources, but [a PyPI package](https://pypi.org/project/Exegol/) is available.
- The [Exegol-images](https://github.com/ThePorgs/Exegol-images) repo is loaded as a submodule. It includes all necessary assets to build Docker images. Notabene: the image are already built and offered on [the official Dockerhub registry](https://hub.docker.com/repository/docker/nwodtuhs/exegol).
- The [Exegol-resources](https://github.com/ThePorgs/Exegol-resources) repo is loaded as a submodule. It includes all resources mentioned previously (LinPEAS, WinPEAS, LinEnum, PrivescCheck, SysinternalsSuite, mimikatz, Rubeus, PowerSploit and many more.).
- The [Exegol-docs](https://github.com/ThePorgs/Exegol-docs) repo for the documentation, destined for users as well as developpers and contributors. The GitHub repo holds the sources that are compiled on https://exegol.readthedocs.io/.
