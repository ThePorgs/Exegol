#!/bin/bash

# DO NOT CHANGE the syntax or text of the following line, only increment the version number
# Spawn Version:2
# The spawn version allow the wrapper to compare the current version of the spawn.sh inside the container compare to the one on the current wrapper version.
# On new container, this file is automatically updated through a docker volume
# For legacy container, this version is fetch and the file updated if needed.

function shell_logging() {
    # First parameter is the method to use for shell logging (default to script)
    local method=$1
    # The second parameter is the shell command to use for the user
    local user_shell=$2
    # The third enable compression at the end of the session
    local compress=$3

    # Test if the command is supported on the current image
    if ! command -v "$method" &> /dev/null
    then
      echo "Shell logging with $method is not supported by this image version, try with a newer one."
      $user_shell
      exit 0
    fi

    # Logging shell using $method and spawn a $user_shell shell

    umask 007
    mkdir -p /workspace/logs/
    local filelog
    filelog="/workspace/logs/$(date +%d-%m-%Y_%H-%M-%S)_shell.${method}"

    case $method in
      "asciinema")
        # echo "Run using asciinema"
        asciinema rec -i 2 --stdin --quiet --command "$user_shell" --title "$(hostname | sed 's/^exegol-/\[EXEGOL\] /') $(date '+%d/%m/%Y %H:%M:%S')" "$filelog"
        ;;

      "script")
        # echo "Run using script"
        script -qefac "$user_shell" "$filelog"
        ;;

      *)
        echo "Unknown '$method' shell logging method, using 'script' as default shell logging method."
        script -qefac "$user_shell" "$filelog"
        ;;
    esac

    if [[ "$compress" = 'True' ]]; then
      echo 'compressing logs, please wait...'
      gzip "$filelog"
    fi
    exit 0
}

# Find default user shell to use from env var
user_shell=${EXEGOL_START_SHELL:-"/bin/zsh"}

# If shell logging is enable, the method to use is stored in env var
if [ "$EXEGOL_START_SHELL_LOGGING" ]; then
  shell_logging "$EXEGOL_START_SHELL_LOGGING" "$user_shell" "$EXEGOL_START_SHELL_COMPRESS"
else
  $user_shell
fi

exit 0
