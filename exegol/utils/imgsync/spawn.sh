#!/bin/bash

# DO NOT CHANGE the syntax or text of the following line, only increment the version number
# Spawn Version:3
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
      # Run it through a shell, like the two supported branches below: with the
      # sentinel recorder active $user_shell is a full `script -qef -c "..." "..."`
      # string, and an unquoted expansion word-splits it with the quotes kept
      # LITERAL, so `script` failed on a path starting with `"` and this function
      # exited 0 — no shell, success status.
      #
      # RUN IT, DO NOT `exec` IT: bash does not run EXIT traps on exec, and
      # sentinel_recorder registers the session cleanup before calling this, so
      # exec'ing leaves the whole unsliced session stream on disk. `exit $?` also
      # propagates the user shell's status.
      #
      # AND THE SHELL MUST NOT CLAIM TO BE RECORDED: the prompt's recording
      # indicator tests EXEGOL_START_SHELL_LOGGING, and here the method is
      # unavailable and the shell runs with no recorder at all.
      unset EXEGOL_START_SHELL_LOGGING
      "${SHELL:-/bin/sh}" -c "$user_shell"
      exit $?
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

# Deployed sentinel configuration, read-only mounted by the wrapper. Kept as a
# literal path (not an env override) on purpose: an override would be a way for
# a process inside the container to point the gate at a config of its own and
# opt out of recording.
SENTINEL_CFG="/var/log/exegol/sentinel/sentinel_config.json"
# Session streams live inside the container, never on the host volume and never on
# /workspace: unsliced bytes are the most sensitive object Sentinel writes and must
# not cross the bind mount.
SENTINEL_SESSION_DIR="/tmp/.sentinel"

# Decide whether a session recorder must be started at all.
#
# THREE answers, not two:
#   0 = required: either consumer is configured (the inline event field
#       profile.config.log_output.enabled, or an output_capture action).
#   1 = no consumer. The dispatch runs as it did before this feature existed.
#   2 = CANNOT TELL: the config is unreadable or malformed, or there is no python3.
#
# Only 1 may take the fast path. "We could not read the config" is not evidence
# that nothing consumes output, and starting an unrecorded shell on it is failing
# OPEN for an audit control — the published rule is that a missing recorder
# refuses the shell with a message naming the remedy. The file's ABSENCE is the
# one positive fact available: Sentinel is off, so nothing consumes output.
#
# Read as JSON, not grepped: the host writes log_rotation's "enabled": true into
# EVERY sentinel container, so a bare grep would start the recorder everywhere.
# python3 is already a hard dependency — both in-container scripts are Python.
function recorder_required() {
  [ -e "$SENTINEL_CFG" ] || return 1
  [ -r "$SENTINEL_CFG" ] || return 2
  command -v python3 &> /dev/null || return 2
  python3 - "$SENTINEL_CFG" <<'PYEOF'
import json, sys

try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        cfg = json.load(fh)
    # VALID JSON IS NOT A JSON OBJECT: `null`, `"x"` and `[]` all parse and then
    # raise on the reads below. An uncaught exception exits 1 — the same code this
    # gate uses for "no consumer" — so a config that declares an output_capture
    # action got an UNRECORDED shell, with only a buried traceback to say so.
    if not isinstance(cfg, dict):
        raise ValueError("the deployed config is not a JSON object")

    def section(parent, name):
        # A MISSING section is "nothing here" — a config that does not use the
        # feature, so "no consumer". A section that is present and is not a
        # mapping is a config we cannot read, which is never the same answer;
        # `or {}` would collapse the two.
        value = parent.get(name)
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("'%s' is not a mapping" % name)
        return value

    log_output = section(section(section(cfg, "profile"), "config"), "log_output")
    # `is True`, not truthiness: nothing re-validates the deployed config, and
    # `"enabled": "false"` (what a hand-edit or a YAML-to-JSON round-trip
    # produces) is a truthy string. The logger applies the identical test, so the
    # gate and the field agree — they used to agree on the wrong answer.
    def declares_capture(action):
        # THE SAME DISTINCTION AS section(), ONE LEVEL DOWN: an action that is
        # present and not a mapping is one we cannot read, and
        # `isinstance(action, dict) and ...` answered it with "no consumer".
        # `{"actions": {"cap": null}}` is a truncated config intact enough to NAME
        # an action and not to describe it, and it used to start an unrecorded
        # shell. Raising puts it on the `except` below.
        if not isinstance(action, dict):
            raise ValueError("an entry of 'actions' is not a mapping")
        return "output_capture" in action

    required = log_output.get("enabled") is True or any(
        declares_capture(action) for action in section(cfg, "actions").values()
    )
except Exception:
    # ANY failure to READ the answer is exit 2 — unreadable, malformed, or a shape
    # these reads cannot walk. It may never also mean "no consumer": that
    # conflation is how a config declaring output_capture got an unrecorded shell.
    sys.exit(2)
sys.exit(0 if required else 1)
PYEOF
}

# Is a logger or a detached runner still working on THIS session's stream?
#
# SCOPED TO THIS SESSION, which a `pgrep -f sentinel_...` was not: it matched
# every such process in the CONTAINER, and concurrent shells are the norm
# (`exegol exec`, more terminals). `exec_command` has no default timeout, so one
# unbounded action from another shell could hold this shell's exit for the whole
# 60 s ceiling.
#
# THE ENVIRONMENT IS THE ONLY THING THAT CAN SCOPE IT:
#   * not the process group — the logger is backgrounded from a subshell and the
#     runner is spawned with start_new_session=True, so a `pgrep -g` on the
#     recorder's pgid matches NOTHING and the wait becomes an immediate unlink;
#   * not the command line — neither argv names the stream.
# Both DO inherit SENTINEL_SESSION_LOG. Pairing it with the program name keeps an
# ordinary backgrounded job of the operator's own from holding the exit open.
#
# PURE BASH, NO grep. Both /proc entries are NUL-separated and `read -r -d ''`
# splits them, which drops two hazards of the earlier `grep -z` form: `-z` is
# absent from BusyBox grep (the match errored, the predicate returned 1 for every
# process, and the wait silently became an immediate `rm -f`) and means DECOMPRESS
# on ugrep; and the path was interpolated UNESCAPED into a BRE, safe only because
# of a `tr` filter enforced 100 lines away. The comparison below is exact string
# equality.
# shellcheck disable=SC2317 # invoked indirectly, through the EXIT trap set below
function sentinel_stream_in_use() {
  local proc pid entry cmdline
  for proc in /proc/[0-9]*; do
    pid=${proc#/proc/}
    [ "$pid" = "$$" ] && continue
    # A process can exit between the glob and the read; a failed redirect just
    # leaves the loop body unrun, which is right for a dead pid.
    #
    # THE SUPPRESSION GOES BEFORE THE INPUT REDIRECTION: redirections are applied
    # left to right, so `done < "$proc/cmdline" 2> /dev/null` opens the input first
    # and reports the failure to the stderr in force then — the terminal. This runs
    # from the EXIT trap, as the operator's session closes.
    cmdline=""
    while IFS= read -r -d '' entry; do
      cmdline="$cmdline $entry"
    done 2> /dev/null < "$proc/cmdline"
    case "$cmdline" in
      *sentinel_runner.py* | *sentinel_logger.py*) ;;
      *) continue ;;
    esac
    while IFS= read -r -d '' entry; do
      [ "$entry" = "SENTINEL_SESSION_LOG=$SENTINEL_SESSION_LOG" ] && return 0
    done 2> /dev/null < "$proc/environ"
  done
  return 1
}

# Release the session stream once the shell is gone; spawn.sh owns the whole
# lifecycle (create, export, sweep orphans, delete). Registered on EXIT so it also
# runs when the shell was wrapped by shell_logging, which exits on its own path.
# shellcheck disable=SC2317 # invoked indirectly, through the EXIT trap set below
function sentinel_session_cleanup() {
  [ -n "$SENTINEL_SESSION_LOG" ] || return 0
  # Wait on the CONDITION, not on a clock. A fixed `sleep 2` bore no relation to
  # the work: an unlimited output_capture on a huge window takes far longer, and
  # unlinking before the runner opens the stream degrades the capture to
  # "unavailable" — evidence lost at the moment the operator is done. It also
  # charged every Sentinel shell two seconds for the common empty case.
  # Still bounded, and it unlinks regardless at the end: holding the file longer
  # keeps unsliced bytes on disk, which is what this cleanup exists to prevent.
  local waited=0
  if [ -r /proc/self/environ ]; then
    while sentinel_stream_in_use && [ "$waited" -lt 60 ]; do
      sleep 1
      waited=$((waited + 1))
    done
  else
    # No readable /proc: fall back to a fixed wait rather than unlinking at once.
    # The gate tests the capability the predicate actually uses — it is pure bash
    # over /proc and nothing else, so /proc readability is the whole dependency.
    sleep 2
  fi
  rm -f "$SENTINEL_SESSION_LOG" 2> /dev/null
}

# Prepare the session stream. Returns non-zero WITHOUT touching the shell when the
# recorder cannot be started, so the caller refuses explicitly instead of letting
# `script` fail with an unhelpful "cannot open <path>".
function sentinel_recorder() {
  # util-linux `script` is the recorder — the same tool family --log has shipped
  # with for years. An image too old to have it cannot record.
  command -v script &> /dev/null || return 1

  # $user_shell is interpolated below into a string `script -c` hands to `sh -c`,
  # so a value containing a double quote breaks out of the quoting and injects a
  # command. Not a privilege boundary today — the value comes from the container's
  # own environment — but it is the one string-concatenation eval on a path built
  # to be tamper-resistant.
  #
  # THE METACHARACTER DENYLIST IS WHAT IS LOAD-BEARING, not the shape of the value.
  # An earlier guard also required a slash, but the wrapper sends BARE NAMES
  # (argparse constrains EXEGOL_START_SHELL to {zsh, bash, tmux}), so the slash
  # requirement rejected every value it actually sends and the refusal below fired
  # on every spawn — no Sentinel container could open a shell at all, under a
  # message blaming `script`.
  # A bare name is resolved through PATH instead, so what reaches `sh -c` is always
  # an absolute path that exists, and the denylist is applied to the RESOLVED value
  # (covering a PATH entry with a space or a quote). Whitespace is refused too: a
  # value that word-splits is as broken as one that breaks the quoting.
  case "$user_shell" in
    */*) ;;
    *) user_shell="$(command -v -- "$user_shell" 2> /dev/null)" || return 1 ;;
  esac
  case "$user_shell" in
    *'"'* | *"'"* | *'$'* | *'`'* | *\\* | *[[:space:]]*) return 1 ;;
  esac
  # An absolute, executable interpreter, whether it was given as a path or
  # resolved from a bare name: refuse here rather than let `script` fail with an
  # unhelpful "cannot open" after the session file has already been created.
  case "$user_shell" in
    /*) ;;
    *) return 1 ;;
  esac
  [ -x "$user_shell" ] || return 1


  # 0700, applied explicitly: the image sets `umask 0007`, so a umask-masked
  # mkdir would leave the directory group-readable, and /tmp is world-writable.
  #
  # The DIRECTORY is as much of a target as the file: `mkdir -p` succeeds SILENTLY
  # on a symlink to a directory, and `chmod` then follows it. `/tmp/.sentinel ->
  # /workspace/logs` would put the unsliced stream on the host bind mount;
  # `-> /` would `chmod 700` the container root. Checked before AND after the
  # mkdir, since the link could be planted between the two.
  if [ -L "$SENTINEL_SESSION_DIR" ]; then
    return 1
  fi
  mkdir -p "$SENTINEL_SESSION_DIR" 2> /dev/null || return 1
  { [ -d "$SENTINEL_SESSION_DIR" ] && [ ! -L "$SENTINEL_SESSION_DIR" ]; } || return 1
  chmod 700 "$SENTINEL_SESSION_DIR" 2> /dev/null || return 1

  # Sweep session files whose owning shell is gone (a container that was killed
  # rather than stopped). The pid is the filename suffix.
  local orphan orphan_pid
  for orphan in "$SENTINEL_SESSION_DIR"/session_*.log; do
    [ -e "$orphan" ] || continue
    orphan_pid="${orphan##*_}"
    orphan_pid="${orphan_pid%.log}"
    case "$orphan_pid" in
      '' | *[!0-9]*) continue ;;
    esac
    # A leftover whose PID suffix is OUR pid cannot belong to a live recorder — we
    # have not created our own file yet — but `kill -0` says "alive", so the sweep
    # kept it, the `set -C` create below refused, and the dispatch refused the
    # shell under a remedy message that is wrong for this cause. Reachable: /tmp
    # survives a container restart, a restarted container numbers PIDs from 1
    # again, and session_id comes from EXEGOL_NAME, identical across restarts.
    if [ "$orphan_pid" = "$$" ]; then
      rm -f "$orphan" 2> /dev/null
      continue
    fi
    kill -0 "$orphan_pid" 2> /dev/null || rm -f "$orphan" 2> /dev/null
  done

  # One spawn.sh run = one script = one unique session file. The name ends in .log
  # so entrypoint.sh's existing WAIT_LIST pgrep covers the recorder.
  local session_id session_file attempt
  # This filter used to be load-bearing for a regex 100 lines up; that predicate
  # now compares strings exactly, so the set is free to change on its own merits.
  session_id="$(printf '%s' "${EXEGOL_NAME:-${HOSTNAME:-exegol}}" | tr -c 'A-Za-z0-9_.-' '_')"
  session_file="$SENTINEL_SESSION_DIR/session_${session_id}_$$.log"

  # O_CREAT|O_EXCL equivalent: `set -C` makes `>` refuse an existing path, and
  # `umask 077` in the same subshell makes the 0600 mode umask-independent.
  # Refusing rather than reusing matters because /tmp is world-writable: a
  # planted symlink would otherwise redirect the recorder's writes over an
  # arbitrary file and corrupt the audit stream.
  #
  # A NAME COLLISION IS NOT FATAL: the sweep above already removed the one leftover
  # that can legitimately carry our pid, and refusing would cost the operator their
  # shell over a filename. The counter goes in the id part, never the suffix — the
  # sweep reads everything after the LAST underscore as the pid, so the name must
  # keep ending in `_<pid>.log`.
  attempt=0
  until (set -C; umask 077; : > "$session_file") 2> /dev/null; do
    attempt=$((attempt + 1))
    [ "$attempt" -le 8 ] || return 1
    session_file="$SENTINEL_SESSION_DIR/session_${session_id}.${attempt}_$$.log"
  done
  chmod 600 "$session_file" 2> /dev/null || return 1

  # Exported BEFORE the shell starts, so the hooks, the logger and the runner
  # inherit it like the LOG_* variables.
  export SENTINEL_SESSION_LOG="$session_file"
  trap sentinel_session_cleanup EXIT

  # Fresh file, never `script -a`: an appended typescript writes a new header per
  # session and defeats the one-file-per-session model the window scan relies on.
  local recorded_shell
  recorded_shell="script -qef -c \"$user_shell\" \"$SENTINEL_SESSION_LOG\""

  if [ "$EXEGOL_START_SHELL_LOGGING" ]; then
    # Sentinel's recorder is the INNERMOST layer: --log's script/asciinema wraps it
    # and harmlessly records the markers too, while the reverse nesting would put
    # the user-facing log inside the audit stream.
    shell_logging "$EXEGOL_START_SHELL_LOGGING" "$recorded_shell" "$EXEGOL_START_SHELL_COMPRESS"
  fi

  script -qef -c "$user_shell" "$SENTINEL_SESSION_LOG"
  exit $?
}

# =========
# Dispatch
# =========
# Everything below this line runs on every spawn. Keep function definitions above
# it: tests exercise recorder_required by loading the prefix of this file.

# Find default user shell to use from env var
user_shell=${EXEGOL_START_SHELL:-"/bin/zsh"}

# $SHELL MUST NOT BE THIS SCRIPT, or every dispatch below becomes a fork bomb:
# `script -c CMD` does not exec CMD, it runs `$SHELL -c CMD`, and `sudo -i` sets
# SHELL from root's passwd entry — which in the Exegol image is this file. Each
# dispatch re-enters spawn.sh, starts another recorder and repeats, one pty and
# one SHLVL per turn, until bash refuses at `shell level (1000) too high`.
#
# Only the pathological value is replaced (`-ef` compares the file, so a renamed
# or symlinked spawn.sh is still caught); a normal session's SHELL is untouched.
#
# THE REPLACEMENT IS $user_shell, NOT /bin/sh, AND THAT IS LOAD-BEARING.
# `$SHELL -c <one simple command>` is exec-optimised, so nothing is interposed
# between `script` and the shell. With /bin/sh it did not optimise: `sh -c
# /bin/zsh` stayed alive as its own process, and the hooks' "am I directly
# recorded?" test asks whether this shell's PARENT is the recording `script`, so
# every recorded shell looked nested and started its own recorder — measured at 7
# for one `sudo -i`.
# The fallback stays /bin/sh for what the guard was written against:
# EXEGOL_START_SHELL may carry arguments rather than be an interpreter path, so
# only a bare executable path is published as $SHELL.
if [ -n "${SHELL:-}" ] && [ "$SHELL" -ef "$0" ]; then
  if [ -x "$user_shell" ]; then
    export SHELL="$user_shell"
  else
    export SHELL=/bin/sh
  fi
fi

# Sentinel output capture gate. When it says no, nothing below changes: no script
# process, no session file, and the shell is spawned on exactly the path it took
# before this feature existed.
recorder_required
recorder_gate=$?
if [ "$recorder_gate" -eq 0 ]; then
  sentinel_recorder
  # Only reached when the recorder could not be started. Audit completeness is
  # preferred over availability here, and only here.
  echo "Sentinel is configured to capture command output, but the session recorder could not be started."
  echo "The shell was not started, because commands would otherwise run unrecorded."
  # EVERY LINE OF THE REMEDY HAS TO CHANGE THE GATE'S ANSWER: this arm can leave a
  # container unable to open a shell at all, so a remedy that does not work sends
  # the operator round a loop. "Restart the container" does not refresh a config
  # frozen by update_strategy: disabled; editing log_output.enabled changes nothing
  # when a profile declares an output_capture action, since either consumer
  # requires the recorder; and deleting the deployed config is the recovery that
  # always works.
  echo "Remedy: if 'script' (util-linux) is missing from this image, update the Exegol image;"
  echo "        no restart helps that. If the container's start shell is not a usable"
  echo "        interpreter, recreate it with a supported one ('exegol start --shell zsh')."
  echo "        To stop requiring capture, set sentinel.log_output.enabled to false in"
  echo "        ~/.exegol/config.yml AND redeploy it -- a config frozen by"
  echo "        sentinel.update_strategy: disabled needs 'exegol restart --sentinel-refresh'."
  echo "        That edit does NOT help if a profile declares an output_capture action:"
  echo "        either consumer requires the recorder."
  echo "        To recover a container that cannot open a shell at all, delete sentinel_config.json"
  echo "        from this container's directory under the host 'sentinel_path' volume -- the"
  echo "        shell then starts unrecorded -- or recreate the container without --sentinel."
  exit 1
elif [ "$recorder_gate" -eq 2 ]; then
  # The same refusal, for the question we could not answer rather than the recorder
  # we could not start. Starting the shell here would be indistinguishable from a
  # container where nothing consumes output, with nothing saying which it was.
  echo "Sentinel could not determine whether command output must be captured: its deployed"
  echo "configuration at /var/log/exegol/sentinel/sentinel_config.json is unreadable or malformed,"
  echo "or this image has no python3 to read it with."
  echo "The shell was not started, because commands would otherwise run unrecorded."
  # EVERY LINE BELOW HAS TO CHANGE THE GATE'S ANSWER, for the same reason as the
  # arm above. `always_enable: false` does not turn Sentinel off for an EXISTING
  # container (it is fixed at creation by the volume mount); a restart only helps
  # when the CONFIG is the problem and the strategy refreshes it, never for a
  # missing python3; and removing the deployed config is the one remedy that always
  # works.
  echo "Remedy: if the deployed configuration is stale or truncated, restart the container to"
  echo "        redeploy it. A config frozen by sentinel.update_strategy: disabled is NOT"
  echo "        refreshed by a plain restart -- use 'exegol restart --sentinel-refresh' to force it."
  echo "        If this image has no python3, no restart will help: update the Exegol image."
  echo "        To recover a container that cannot open a shell at all, delete sentinel_config.json"
  echo "        from this container's directory under the host 'sentinel_path' volume -- the"
  echo "        shell then starts unrecorded -- or recreate the container without --sentinel."
  exit 1
fi

# If shell logging is enable, the method to use is stored in env var
if [ "$EXEGOL_START_SHELL_LOGGING" ]; then
  shell_logging "$EXEGOL_START_SHELL_LOGGING" "$user_shell" "$EXEGOL_START_SHELL_COMPRESS"
else
  $user_shell
fi

exit 0
