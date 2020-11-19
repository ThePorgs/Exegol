# General
- the `master` branch is the stable version. Please work and submit PR on the `dev` branch only. It's the most up-to-date. Once the new features are good to go, I merge the `master` and `dev` branches once in a while.
- `exegol.py` is the python wrapper to manage the image/container from the host
- by default, the wrappers pulls the latest DockerHub pre-built image for the install and updates
- DockerHub automatic builds are configured as follows : automatic build for each commit on the `master` branch (`latest` tag), manual builds for the `dev` branch (`dev` tag)
- if you want to locally build your image with your changes, run the wrapper with the following options: `python3 exegol.py --mode sources install`. This will operate a `git pull` in order to make sure you have the latest code base (but your local edits shouldn't be overwritten). once the `git pull` is over, the wrapper will run a `docker build`
- `sources/install.sh` is the install script ran during the build process, it installs tools, downloads resources and so on

# Tools
- tools are installed in `/opt/tools`
- if the tools you want to add are GUI-based, you can create the install function of your tool and then call that function in `install_tools_gui()`
- if the tools you want to add are not GUI-based, you can do the install function for the tool and then call it in `install_tools()`
- make sure to start the install function with : `colorecho "[EXEGOL] Installing {name of the tool}"`
- make sure to add the tool to the list in `README_long.md` in the format : name of the tool (repo link)

# Resources
*(e.g. a tool that cannot be used in Exegol but on the target for example, like Rubeus, mimikatz and so on)*
- resources are installed in `/opt/resources`
- just like the tools, make your install function, and then call it in `install_resources()`, start the function with the `colorecho`, report the new resource in `README_long.md`

# Aliases
- you can set alias in the `sources/zsh/aliases` file
- aliases can point to binaries or script that are not in the path for example

# History
- you can add history to the `sources/zsh/history` file
- the history is a helper to the users. Let's say I start to write "`secretsdump`", they'll be able to go through the commands in the history and then replace the placeholders with their values. I often rely on this history when I forget a tool or something, it can be helpful

And last thing, if you want to add anything else that is not a tool, a resource, history, aliases, config or whatever, feel free to ask for it :) the idea behind Exegol is to have the perfect, community-driven, hacking environment :rocket:
