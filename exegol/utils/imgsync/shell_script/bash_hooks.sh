#!/usr/bin/env bash

# =========
# Shell logging hooks for bash
# =========
# Global variables for cross function data access
LAST_COMMAND_RAW=""
LAST_COMMAND_START_TIME=""
ARTIFACT_ID=""

COMMANDS_BLACKLIST=("shell_logging_precmd" "__fzf_history__")

IS_INIT=""
INIT_OVER=""

# Mutex guard against DEBUG-trap recursion (suppresses logging of internal
# substitutions such as $(date ...) and the /proc uuid read run inside the handler)
_SENTINEL_ACTIVE=""

# -1 (not 0) so the first real command's HISTCMD never equals it and is never dropped
LAST_HISTNO=-1
# raw-command fallback dedup, used when HISTCMD is pinned (HISTSIZE=0 or HISTCMD==0)
_LAST_LOGGED_RAW=""

# =========
# Sentinel output capture: the session stream this shell is recorded into
# =========
# RESOLVED FROM THE EXEC-TIME ENVIRONMENT, NEVER FROM THE LIVE VARIABLE.
# spawn.sh exports SENTINEL_SESSION_LOG before `script` starts this shell, so it
# is an ordinary variable of the operator's own shell: `unset` it and the markers
# stop, `export` it at a planted file and the logger reads a forged window. What
# the operator cannot rewrite is /proc/<pid>/environ. Two ways a shell learns its
# stream, in priority order:
#
#   1. DIRECTLY-RECORDED SHELL -- the one `script` exec'd, a session leader whose
#      PARENT is that `script`. Its stream is read from the PARENT's frozen
#      environ, never its own, so `exec env SENTINEL_SESSION_LOG=/planted bash`
#      (still parented to `script`) is closed too.
#   2. ANY OTHER SHELL -- a sub-shell sharing the pty, or one with no recorder --
#      falls back to the OUTERMOST ancestor carrying the variable, self included,
#      so a planted self value never wins over the real stream above it. No
#      carrier means no recorder, and the hooks stay byte-identical to before this
#      feature existed. The live variable is deliberately NOT a fallback.
#
# A nested INTERACTIVE shell never reaches (2): sentinel_nested_record gives it
# its own `script` and stream, or none, so two shells' windows are never in the
# same file.
#
# Not a boundary, and published as such: the hooks are functions in the operator's
# shell and the marker id is a shell parameter, so they can be redefined and a
# marker pair forged — the same posture as every other sentinel event.
#
# The walks read /proc, stopping at pid 1 or 32 hops. An ancestor of another uid
# refuses its environ with EACCES whatever `-r` says (/proc applies a ptrace
# check, not the mode bits), so a refused read just skips that level.
function sentinel_proc_after_comm() {  # $1=pid -> the post-')' stat fields
  [[ -r "/proc/$1/stat" ]] || return 1
  local stat; stat=$(< "/proc/$1/stat") || return 1
  # The comm may itself contain spaces or parentheses, hence cutting at the LAST ')'.
  printf '%s' "${stat##*) }"
}
function sentinel_proc_comm() {  # $1=pid -> the process comm
  [[ -r "/proc/$1/stat" ]] || return 1
  local stat; stat=$(< "/proc/$1/stat") || return 1
  stat="${stat%)*}"; printf '%s' "${stat#*(}"
}
function sentinel_env_session() {  # $1=pid -> SENTINEL_SESSION_LOG from its environ
  [[ -r "/proc/$1/environ" ]] || return 1
  local entry
  while IFS= read -r -d '' entry; do
    if [[ "$entry" == SENTINEL_SESSION_LOG=* ]]; then
      printf '%s' "${entry#SENTINEL_SESSION_LOG=}"; return 0
    fi
  done < "/proc/$1/environ"
  return 1
}
function sentinel_session_log_resolve() {
  local rest ppid sid
  rest=$(sentinel_proc_after_comm $$) || return
  read -r _ ppid _ sid _ <<< "$rest"
  # (1) directly-recorded shell: authority is the parent `script`'s environ.
  if [[ -n "$ppid" && "$$" == "$sid" && "$(sentinel_proc_comm "$ppid" 2> /dev/null)" == script ]]; then
    sentinel_env_session "$ppid" 2> /dev/null && return
  fi
  # (2) fallback: outermost ancestor carrying the variable (self included).
  local pid=$$ found="" v hops=0
  while [[ "$pid" =~ ^[0-9]+$ ]] && (( pid > 1 && hops < 32 )); do
    v=$(sentinel_env_session "$pid" 2> /dev/null) && found="$v"
    rest=$(sentinel_proc_after_comm "$pid" 2> /dev/null) || break
    read -r _ pid _ <<< "$rest"
    hops=$((hops + 1))
  done
  printf '%s' "$found"
}
# ---- A nested interactive shell records ITSELF ----
# Typing `bash`/`zsh` at a recorded prompt used to re-source the hooks and resolve
# the SAME stream, so each inner command's runner punched a hole INSIDE the
# enclosing command's still-open window — reported as a faithful capture over NUL
# bytes. Instead the nested shell starts its OWN `script` on its OWN file. The
# outer `script` still records every byte the inner pty displays, so the enclosing
# window stays faithful.
#
# True iff a real `script` process in the ancestry is recording this shell — not
# the mere presence of the variable, which an inherited value with no `script`
# behind it (a test harness, a degraded container) also has; those keep the legacy
# resolution and must never be answered with a new recorder.
#
# A FALSE ANSWER IS NOT "there is no recorder", only "I cannot see one" — see
# sentinel_recorder_owns, which the gate consults next.
#
# It also counts them into `_sentinel_recorder_depth`: the same walk answers the
# recursion question below, and a second one would cost another /proc traversal at
# every shell start.
function sentinel_recorder_ancestor() {
  local rest pid hops=0
  _sentinel_recorder_depth=0
  rest=$(sentinel_proc_after_comm $$) || return 1
  read -r _ pid _ <<< "$rest"
  while [[ "$pid" =~ ^[0-9]+$ ]] && (( pid > 1 && hops < 32 )); do
    if [[ "$(sentinel_proc_comm "$pid" 2> /dev/null)" == script ]] \
       && sentinel_env_session "$pid" > /dev/null 2>&1; then
      _sentinel_recorder_depth=$((_sentinel_recorder_depth + 1))
    fi
    rest=$(sentinel_proc_after_comm "$pid" 2> /dev/null) || break
    read -r _ pid _ <<< "$rest"
    hops=$((hops + 1))
  done
  (( _sentinel_recorder_depth > 0 ))
}
# Is `script` process $1 the one actually writing $2? A `script` the operator
# started at a recorded prompt inherits SENTINEL_SESSION_LOG from it, so its
# environ names the ENCLOSING stream while its fds are on its own file — the open
# descriptor is the ground truth. `-ef` compares device+inode through the
# /proc/<pid>/fd symlink, so this is a builtin test with no readlink.
# Reading fd/ needs the same ptrace access as environ, which the only caller has
# already obtained, so an unreadable fd/ here is not a reachable degradation.
function sentinel_proc_ppid() {  # $1=pid -> its parent pid, or empty
  local rest _s pp
  rest=$(sentinel_proc_after_comm "$1") || return 1
  read -r _s pp _ <<< "$rest"
  printf '%s' "$pp"
}
function sentinel_is_dash_c_shell() {  # $1=pid -> 0 if it is a shell invoked with -c
  local comm arg
  comm=$(sentinel_proc_comm "$1" 2> /dev/null) || return 1
  case "$comm" in
    sh|dash|ash|bash|zsh|ksh|busybox) ;;
    *) return 1 ;;
  esac
  [[ -r "/proc/$1/cmdline" ]] || return 1
  while IFS= read -r -d '' arg; do
    [[ "$arg" == "-c" ]] && return 0
  done < "/proc/$1/cmdline"
  return 1
}
function sentinel_directly_recorded() {  # $1=pid of the candidate recorder
  local penv
  [[ -n "$1" ]] || return 1
  [[ "$(sentinel_proc_comm "$1" 2> /dev/null)" == script ]] || return 1
  penv=$(sentinel_env_session "$1" 2> /dev/null) && [[ -n "$penv" ]] || return 1
  sentinel_recorder_writes "$1" "$penv"
}
function sentinel_recorder_writes() {  # $1=script pid, $2=stream path
  local fd
  for fd in "/proc/$1/fd"/*; do
    [[ -e "$fd" ]] || continue
    [[ "$fd" -ef "$2" ]] && return 0
  done
  return 1
}
# Is ANY live `script` process writing $1?
#
# THE QUESTION THE ANCESTRY WALK CANNOT ANSWER. sentinel_recorder_ancestor asks
# "can I SEE my recorder", and reading a false answer as "there is not one" is the
# defect. A shell REPARENTED away from the recorder reaches that state from an
# ordinary prompt in one command (`setsid zsh -i`, `(bash -i &)`, any wrapper
# whose intermediate exits): the recording `script` leaves its ancestry, but its
# stdin/stdout/stderr are STILL the outer pty, so its marker pairs land in the
# enclosing typescript.
#
# So the fallback asks what actually decides it: is somebody recording THIS
# stream, anywhere in the container? An open descriptor is the ground truth.
# That discriminator — "is it being written", not "did the value come from my own
# environ" — is also what keeps the genuine degraded case right: an inherited
# SENTINEL_SESSION_LOG with no live recorder names a file nobody is writing, so
# nothing is shared and the legacy resolution stays byte-identical to before.
#
# COST: only reached when this shell carries a stream, is not the recorded shell,
# and cannot see a recorder. `comm` is read first, so the fd glob is entered only
# for `script` processes.
#
# TERMINATION: after a break-away the inner shell's ancestry up to its new
# `script` is entirely its own descendants, whose /proc it can always read, so the
# ancestry walk sees that `script` and the depth guard below bounds the chain. The
# blind case can only ever be the FIRST shell in a chain.
#
# ANSWERS THREE THINGS: 0 owned, 1 nobody is writing it, 2 cannot tell. The third
# is why this exists — returning a bare 1 from a refused /proc would make the gate
# fall through to the resolver's self-inclusive walk and hand the shell the stream
# it INHERITED, the enclosing one.
#
# The reachable shape is a nested shell running as a DIFFERENT UID with the
# environment kept (`sudo -E -u other zsh`, an image whose tooling runs under
# another account): /tmp/.sentinel is 0700 under the recorded uid, so `-e "$1"` is
# false while the file plainly exists, every ancestor's environ is refused, and the
# shell's output still lands in the enclosing typescript. Somebody IS writing that
# stream; the shell just cannot see who.
#
# So a blind spot is reported as 2, and the gate treats 2 like 0 — break away or
# refuse, never share. Only a positive "nothing is writing it" (1) falls through
# to the legacy resolution.
#
# TWO BLIND SPOTS, kept apart from their genuine counterparts:
#
#   * `-e "$1"` false: "not there" when the containing directory is searchable,
#     "not allowed to look" when it is not, so the directory decides which.
#   * a `script` whose /proc/<pid>/fd we may not read: the glob yields nothing and
#     sentinel_recorder_writes answers "not this one" for a recorder that may hold
#     our stream. `/proc/<pid>/stat` is world-readable, so the comm lookup is NOT
#     a blind spot — a failure there is a pid that exited under the scan.
# COULD `$1` -- a live `script` whose fd/ we may not read -- be holding `$2`?
#
# An uninspectable process is evidence about OUR stream only if it could
# plausibly hold it. Without this test, one unrelated recorder under another uid
# (a `--pid=host` container, tooling running `script` as a service account) made
# the predicate answer 2 for every stream, so every shell reaching that branch was
# treated as nested.
#
# Three pieces of evidence, in decreasing strength. The first is the one that
# works ACROSS UIDS, which is the whole point since the process that matters is by
# definition one we may not inspect:
#
#   1. its COMMAND LINE names the stream: a recorder is started as
#      `script -qef -c CMD FILE`, and /proc/<pid>/cmdline is world-readable —
#      unlike fd/ and environ, which /proc gates behind a ptrace check.
#   2. it shares our SESSION.
#   3. it shares our CONTROLLING TERMINAL, both non-zero (0 is "no tty").
#
# FAIL-CLOSED: if our own stat cannot be read the comparison is impossible and the
# candidate is treated as plausible. A reparented shell has neither our session
# nor a tty, so only (1) saves it.
function sentinel_recorder_plausible() {  # $1=script pid, $2=stream path -> 0 plausible
  local entry cmd="" rest sid tty mysid mytty
  # See sentinel_nested_cleanup for why the suppression precedes the input
  # redirection rather than following it.
  while IFS= read -r -d '' entry; do cmd="$cmd $entry"; done 2> /dev/null < "/proc/$1/cmdline"
  case "$cmd" in *"$2"*) return 0 ;; esac
  rest=$(sentinel_proc_after_comm "$1" 2> /dev/null) || return 1
  read -r _ _ _ sid tty _ <<< "$rest"
  rest=$(sentinel_proc_after_comm $$ 2> /dev/null) || return 0
  read -r _ _ _ mysid mytty _ <<< "$rest"
  [[ -n "$sid" && "$sid" == "$mysid" ]] && return 0
  [[ -n "$tty" && "$tty" != 0 && "$tty" == "$mytty" ]] && return 0
  return 1
}
function sentinel_recorder_owns() {  # $1=stream path -> 0 owned, 1 nobody, 2 cannot tell
  local proc pid blind=0
  [[ -n "$1" ]] || return 1
  if [[ ! -e "$1" ]]; then
    [[ -x "${1%/*}" ]] || return 2
    return 1
  fi
  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    [[ "$pid" == "$$" ]] && continue
    [[ "$(sentinel_proc_comm "$pid" 2> /dev/null)" == script ]] || continue
    sentinel_recorder_writes "$pid" "$1" && return 0
    # `! -d /proc/<pid>` disarms the one false positive: a `script` that exited
    # under the scan also has an unreadable fd/ and is genuinely writing nothing.
    # A live one with an fd/ we may not read is the real blind spot — but only if
    # it could be holding THIS stream.
    if [[ ! -r "/proc/$pid/fd" && -d "/proc/$pid" ]]; then
      sentinel_recorder_plausible "$pid" "$1" && blind=1
    fi
  done
  (( blind )) && return 2
  return 1
}
# Returns 0 when this shell may resolve a stream normally (it is directly
# recorded, or there is no recorder to break away from), and NON-ZERO when it is
# nested inside a recorder it must not share and could not break away from. The
# caller turns that non-zero into an EMPTY resolved stream: see the bootstrap.
function sentinel_nested_record() {
  [[ $- == *i* ]] || return 0
  local rec rest ppid
  rec=$(sentinel_session_log_resolve 2> /dev/null)
  [[ -n "$rec" ]] || return 0
  rest=$(sentinel_proc_after_comm $$) || return 0
  read -r _ ppid _ <<< "$rest"
  # A shell is DIRECTLY RECORDED iff its PARENT is the `script` recording it —
  # the same test the resolver makes. `$$ != sid` was a proxy, and a wrong one:
  # ANY session leader passes it, so a nested shell that leads a session for some
  # other reason fell through to the outermost-ancestor walk and silently shared
  # the ENCLOSING stream. `setsid`, `sudo -i`/`sudo -s` and `screen` all reach
  # that from an ordinary prompt in one command.
  if sentinel_directly_recorded "$ppid"; then
    return 0
  fi

# ONE INTERPOSED `$SHELL -c <my shell>` WRAPPER, AND ONLY THAT.
#
# `script -c CMD` runs `$SHELL -c CMD`, and a shell running one simple command
# normally execs it, leaving nothing between `script` and the shell. That is an
# optimisation, not an invariant: a $SHELL that forks leaves a live wrapper in
# between, and every directly-recorded shell then answered "no" to the parent test
# and broke away into a recorder of its own — measured at 7 nested recorders for
# one `sudo -i`.
#
# It does not let a genuinely nested shell through: `bash` typed at a recorded
# prompt has an INTERACTIVE parent, whose argv carries no `-c`. The step is taken
# only when the parent is a `-c` shell AND the grandparent passes the same full
# recorder test as the direct case.
  if [[ -n "$ppid" ]] && sentinel_is_dash_c_shell "$ppid"; then
    local gpid
    gpid=$(sentinel_proc_ppid "$ppid" 2> /dev/null)
    if sentinel_directly_recorded "$gpid"; then
      return 0
    fi
  fi
  # IS THERE A RECORDER TO BREAK AWAY FROM? Two questions, not one:
  #
  #   1. can I SEE a recording `script` above me?  -- sentinel_recorder_ancestor
  #   2. is anybody recording this stream at all?  -- sentinel_recorder_owns
  #
  # A no to (1) used to `return 0` into the resolver's self-inclusive fallback
  # walk, handing the shell the stream it INHERITED. A shell reparented away from
  # its recorder answers no to (1) while its bytes still reach the enclosing
  # typescript, so its windows opened inside the enclosing command's still-open
  # window and its runner punched a hole over it.
  #
  # Only 1 — "nobody is writing it", the degraded container / test-harness case —
  # may fall through to the legacy resolution. 0 (somebody is) and 2 (not allowed
  # to look) are both nested.
  if ! sentinel_recorder_ancestor; then
    sentinel_recorder_owns "$rec"
    (( $? == 1 )) && return 0
  fi
  # RECURSION GUARD. Termination otherwise rests on the re-exec'd shell being one
  # `script` exec'd directly — an assumption about `$SHELL -c`'s exec optimisation,
  # not an invariant. A `$SHELL` that forks leaves the inner shell looking nested
  # again and starts another recorder, which starts another: a fork bomb costing a
  # `script`, a shell and a session file per level.
  # The chain length is read from the ANCESTRY, not an exported counter the
  # operator could pre-set at the prompt to suppress their own capture. 8 is a
  # ceiling on absurdity — no interactive session nests that deep.
  (( _sentinel_recorder_depth < 8 )) || return 1
  # DECIDE THE BREAK-AWAY ON THE INVOCATION, NOT JUST ON INTERACTIVITY.
  #
  # The rc file is sourced BEFORE the shell acts on its arguments, so this hook
  # fires first, `script` starts a fresh interpreter with NONE of them, and
  # `exit "$rc"` reports that shell's status as the original invocation's. For
  # `bash -i -c CMD` that meant CMD was never run and never reported as not run.
  # `-ic` is not exotic: `tmux set default-command`, `xterm -e`, IDE terminals and
  # `ssh -t host 'bash -ic ...'` all use it.
  #
  # An invocation can only be carried across by re-quoting it into `script -c`'s
  # command STRING, and anything the rc file cannot see cannot be carried at all.
  # So: reproduce what can be reproduced faithfully and REFUSE THE CAPTURE for
  # everything else — never silently run something different. A refusal returns 1,
  # which blanks the resolved stream: the shell runs its own original invocation,
  # unrecorded, with `output_status: unavailable` on its commands.
  #
  # REPRODUCED: interactivity (`script` always allocates a pty) and the login flag.
  #
  # REFUSED:
  #   * a command string (`-c CMD`);
  #   * positional parameters (`sh -is a b`), silently dropped otherwise;
  #   * a SCRIPT FILE OPERAND (`bash -i prog.sh`) — a different test: it reaches
  #     the rc with `$#` == 0 and an empty BASH_EXECUTION_STRING, so it passed
  #     every other check and the replacement shell never ran the script. bash
  #     exposes the operand as `$0`, but `$0` is the invocation name otherwise —
  #     an absolute path to a real file — so `[[ -f "$0" ]]` alone would refuse
  #     every recorded session. Hence: a regular file that is NOT the interpreter
  #     running it;
  #   * a RESTRICTED shell, which matters most: `script -c "$interp"` starts an
  #     UNRESTRICTED interpreter, so breaking away would hand the operator a way
  #     out of the restriction;
  #   * any `$-` letter changing execution semantics that is not carried across
  #     (xtrace, verbose, nounset, errexit, noglob, noexec, onecmd, keyword,
  #     allexport, noclobber, privileged, restricted). A denylist, not a diff
  #     against a baseline `$-`: the baseline varies with job control, with stdin,
  #     and between dialects.
  #
  # NOT REFUSED, and why:
  #   * `-s` / a REDIRECTED STDIN: not lost — `script` copies its own stdin into
  #     the pty, so the commands are forwarded to the replacement shell. This is
  #     exactly why a script operand IS lost: an operand is read by the shell
  #     itself, so there is nothing for `script` to forward.
  #   * `--posix` (and zsh's `--emulate sh`): the gate never runs, because such a
  #     shell reads `$ENV` and never sources these hooks at all.
  #   * options with NO `$-` letter (`-o pipefail`, `-O extglob`, zsh `setopt`s)
  #     and an ALTERNATE STARTUP FILE. Deliberately not refused: from inside a
  #     startup file, `-o pipefail` on the command line is indistinguishable from
  #     `set -o pipefail` written three lines above, so refusing on the option's
  #     STATE would disable capture for every shell in any image whose rc sets it
  #     — a systematic loss traded for a rare substitution.
  [[ -n "${BASH_EXECUTION_STRING:-}" ]] && return 1
  (( ${_sentinel_shell_argc:-0} > 0 )) && return 1
  shopt -q restricted_shell && return 1
  case "$-" in *[xvuefntkaCpr]*) return 1 ;; esac
  # The script-file operand. `-ef` compares inodes, so a `$0` that IS the
  # interpreter this shell runs (the no-operand case under `script -c`) is not an
  # operand. An unset `$BASH` makes the test refuse — fail-closed, costing the
  # capture and never the shell.
  [[ -f "$0" && ! "$0" -ef "${BASH:-/nonexistent}" ]] && return 1
  # FROM HERE THIS SHELL IS NESTED and every remaining exit is a REFUSAL, never a
  # fallback to sharing. Sharing is the defect itself: the inner shell's bytes
  # reach the enclosing stream, so its windows open inside the enclosing command's
  # still-open window and its runner punches a hole in it — published as a
  # faithful capture over NUL bytes. `PATH=/nonexistent bash` reaches that from the
  # prompt in one line. Returning non-zero blanks the resolved stream instead, so
  # the nested shell emits no markers and its commands carry `output_status:
  # unavailable`. The capture is given up; the shell still runs.
  # `$BASH` is the full pathname this instance was executed with -- the running
  # interpreter, which is what the replacement must be. It is only trusted when
  # ABSOLUTE: a relative `./bash` would be re-resolved by `sh -c` against whatever
  # the working directory is by then, which need not be this one.
  local interp="${BASH:-}"
  [[ "$interp" == /* && -x "$interp" ]] || interp="$(command -v bash 2> /dev/null)"
  [[ -n "$interp" && -x "$interp" ]] || return 1        # no interpreter -> no capture
  # $interp REACHES `sh -c` AS PART OF A COMMAND STRING — the same situation
  # spawn.sh guards: a path carrying a space word-splits, and one carrying a quote,
  # a `$`, a backtick or a backslash breaks or re-interprets the quoting.
  # It also makes the failure unreachable rather than recoverable: `sh -c` reports
  # "command not found" AFTER `script` wrote its header, so the `[[ ! -s "$mine" ]]`
  # recovery below cannot see it and the nested shell exits with 127. A 126/127
  # heuristic is deliberately not added there — an interactive shell whose last
  # command was not found exits 127 too, and would get a surprise second shell.
  case "$interp" in *'"'* | *"'"* | *'`'* | *'$'* | *\\* | *[[:space:]]*) return 1 ;; esac
  command -v script > /dev/null 2>&1 || return 1        # no recorder -> no capture
  # The login flag is the one invocation property reproduced: the rc file can see
  # it, and it is one more word in `script`'s command string.
  local invoke="$interp"
  shopt -q login_shell && invoke="$invoke -l"
  local dir="${rec%/*}" mine="${rec%/*}/session_nested_$$.log" attempt=0
  # O_CREAT|O_EXCL (`set -C`) + umask 077 -> 0600, so a planted symlink in the
  # 0700 dir cannot redirect the write. A name collision only retries.
  until ( set -C; umask 077; : > "$mine" ) 2> /dev/null; do
    attempt=$((attempt + 1)); (( attempt <= 8 )) || return 1
    mine="${dir}/session_nested.${attempt}_$$.log"
  done
  chmod 600 "$mine" 2> /dev/null || { rm -f "$mine"; return 1; }
  # A PREFIX assignment, not an `export`: the recorder and the inner shell it
  # execs carry the stream in their environ — where both /proc resolvers read it —
  # while THIS shell's environment is untouched. That is what keeps the refusal
  # below indistinguishable from the pre-commit ones: none of them leaves a stream
  # exported at a file that has just been unlinked.
  SENTINEL_SESSION_LOG="$mine" script -qef -c "$invoke" "$mine"
  # CAPTURE THE STATUS BEFORE THE CLEANUP: sentinel_nested_cleanup ends in `rm -f`,
  # which returns 0 either way, so `exit $?` after it would discard the inner
  # shell's status — the code `script -e` goes to the trouble of propagating.
  local rc=$?
  # DID `script` EVER START A SHELL? A `script` that fails (pty exhaustion, no
  # /dev/pts, an `openpty` denied by seccomp) returns non-zero without starting
  # one, and the hook used to `exit` with it — so typing `bash` returned
  # immediately with NO SHELL AT ALL, on a container where it worked before.
  # A nested shell that cannot start a recorder is given no STREAM; it is never
  # given no shell.
  #
  # The discriminator is whether the recorder wrote its header: `script` emits it
  # as soon as the pty is up and before it execs anything, and the create above
  # left the file at zero bytes. (A `script` whose shell starts and then fails
  # leaves the header plus a diagnostic, so it is correctly read as "the inner
  # shell exited with this code".)
  #
  # REFUSE THE CAPTURE, NOT THE SHELL: fall through to the no-stream path, with
  # `output_status: unavailable` on the shell's commands.
  if [[ ! -s "$mine" ]]; then
    sentinel_nested_cleanup "$mine"
    return 1
  fi
  sentinel_nested_cleanup "$mine"
  exit "$rc"
}
# Release the nested stream once the inner shell is gone (spawn.sh's EXIT-trap
# cleanup, inlined for the file this shell owns): wait — bounded — for an
# in-flight runner or logger still reading THIS stream, so an unlimited
# output_capture is not cut short, then unlink.
function sentinel_nested_cleanup() {
  local target="$1" waited=0 proc pid busy entry cmd
  if [[ -r /proc/self/environ ]]; then
    while (( waited < 60 )); do
      busy=0
      for proc in /proc/[0-9]*; do
        pid="${proc##*/}"; [[ "$pid" == "$$" ]] && continue
        [[ -r "$proc/cmdline" ]] || continue
        # `[[ -r ]]` above is a TOCTOU test, not a lock: a process can exit before
        # this redirect, and the failure would print at the prompt once per pid,
        # up to 60 times. A failed redirect just leaves the loop body unrun, which
        # is the right answer for a dead pid.
        #
        # THE ORDER OF THE TWO REDIRECTIONS IS THE FIX: they are applied left to
        # right, so `done < "$proc/cmdline" 2> /dev/null` opens the input first and
        # reports the failure to the stderr in force at that moment — the terminal.
        # The suppression must come first.
        cmd=""; while IFS= read -r -d '' entry; do cmd="$cmd $entry"; done 2> /dev/null < "$proc/cmdline"
        case "$cmd" in *sentinel_runner.py* | *sentinel_logger.py*) ;; *) continue ;; esac
        [[ -r "$proc/environ" ]] || continue
        while IFS= read -r -d '' entry; do
          [[ "$entry" == "SENTINEL_SESSION_LOG=$target" ]] && { busy=1; break; }
        done 2> /dev/null < "$proc/environ"
        (( busy )) && break
      done
      (( busy )) || break
      sleep 1; waited=$((waited + 1))
    done
  else
    sleep 2
  fi
  rm -f "$target" 2> /dev/null
}
# The SHELL's positional parameter count, captured at file scope: inside a
# function `$#` is that function's own argument count, so the gate cannot ask the
# question for itself. A shell given arguments must not be replaced by one without
# them (see the invocation checks in sentinel_nested_record).
_sentinel_shell_argc=$#
# =========
# Bootstrap
# =========
# THE RESOLVED VALUE IS READONLY, or the /proc walk above is defeated by its own
# storage: the answer would land in an ordinary parameter both hooks re-read on
# every command, so assigning it at the prompt redirects the logger outright and
# the empty string switches the capture off.
#
# GUARDED ON THE ATTRIBUTE, NOT ON EMPTINESS:
#
#   * re-sourcing the rc is routine, and reassigning a readonly parameter is a
#     hard error. An ALREADY readonly value is ours from an earlier sourcing in
#     this same shell, so it is left alone.
#   * a merely SET value is not ours: an inherited/planted one carries no `r`
#     attribute and is overwritten by the real resolution. A `${VAR+x}`-style
#     guard would instead have frozen it — a better version of the hole.
#
# `readonly` is not a boundary: the hooks can be redefined and a marker pair
# forged. What it closes is the environment/parameter path.
#
# THE SAME ATTRIBUTE GATES THE GATE ITSELF, not just its answer's storage:
# `sentinel_nested_record` MAY START A `script` AND `exit`, and a re-source
# re-defines every function the previous pass unset, so it really did run again.
# Either the answer is unchanged and the whole /proc scan runs for nothing, or it
# changed — and the re-source breaks away, hands the operator a replacement shell
# they did not ask for, and terminates their session when it ends. Useless or
# harmful, with nothing in between, so it is computed once per shell.
#
# SEEDED FIRST because `${VAR@a}` on an UNSET parameter is an unbound-variable
# error under `set -u`, which aborts the command: the whole `if` body was skipped,
# the value never resolved, and the logger spawn in shell_logging_precmd died the
# same way — a `set -u` shell wrote ZERO audit events. `: "${VAR=}"` is `-u`-safe,
# assigns only when unset (so a re-source cannot trip the readonly), and the empty
# string it assigns carries no `r` attribute, so the rule above is preserved.
: "${SENTINEL_SESSION_LOG_RESOLVED=}"
if [[ ${SENTINEL_SESSION_LOG_RESOLVED@a} != *r* ]]; then
  # May exec-and-exit (the nested case). A non-zero return is the third answer:
  # nested inside a recorder it must not share and could not break away from, so
  # it resolves to NO stream rather than to the enclosing one.
  sentinel_nested_record
  _sentinel_nested_refused=$?
  if (( _sentinel_nested_refused )); then
    SENTINEL_SESSION_LOG_RESOLVED=""
  else
    SENTINEL_SESSION_LOG_RESOLVED="$(sentinel_session_log_resolve 2> /dev/null)"
  fi
  readonly SENTINEL_SESSION_LOG_RESOLVED
fi
# Nothing may recompute the value after this point, so the resolvers are removed
# rather than left in the operator's namespace as redefinable hooks.
unset -f sentinel_session_log_resolve sentinel_nested_record sentinel_nested_cleanup \
  sentinel_recorder_ancestor sentinel_recorder_writes sentinel_recorder_owns \
  sentinel_recorder_plausible \
  sentinel_proc_after_comm sentinel_proc_comm sentinel_env_session
# Scratch of the ancestry walk and of the gate's answer, kept out of the
# operator's namespace with them.
unset _sentinel_recorder_depth _sentinel_nested_refused

# =========
# EVERY PARAMETER READ BELOW THIS LINE IS `${VAR:-}`-GUARDED, WITHOUT EXCEPTION
# =========
# Not a style preference. Under `set -u` / `setopt nounset` a bare read of an
# unset parameter ABORTS THE ENCLOSING FUNCTION, and in an interactive shell it
# aborts the command instead of exiting, so it is completely silent. Aborting
# shell_logging_precmd costs three things at once:
#
#   * the end marker is never emitted, leaving an unterminated window;
#   * the logger is never spawned, so the command produces NO EVENT at all — not
#     even `output_status: unavailable`;
#   * the `LAST_COMMAND_RAW=""` reset at the bottom is skipped, so the next
#     preexec takes the pipeline-continuation branch and returns early. From then
#     on not even the start marker is emitted: THE LOSS IS TERMINAL FOR THE
#     SESSION, not per-command.
#
# Every parameter here is a global in the operator's own shell, one `unset` away
# from being gone — and `unset HISTSIZE` is half of the documented history-off
# idiom, so this is reachable with no intent at all.
#
# `tests/sentinel/test_hook_nounset_lint.py` fails the build on the next bare read
# added here.

# Function PREEXEC : called before each command or function execution
function shell_logging_preexec() {
  # SET mutex FIRST, before any $(...) / command substitution below runs, so
  # the DEBUG trap suppresses any command reachable while this handler executes.
  _SENTINEL_ACTIVE=1

  # Skip logging while .bashrc is still sourcing
  if [[ -n "${IS_INIT:-}" ]]; then
    _SENTINEL_ACTIVE=""
    return 0
  fi
  # Prevent internal or side-function logging.
  # `${arr[@]+"${arr[@]}"}` expands to NOTHING when the array is unset, which is
  # what the loop wants; `"${arr[@]:-}"` would inject a spurious empty element and
  # make the body compare against "". bash >= 4.4 tolerates the plain form under
  # `-u`, older ones do not, and the hook file is bind-mounted into whatever image
  # the operator built.
  for current in ${COMMANDS_BLACKLIST[@]+"${COMMANDS_BLACKLIST[@]}"}; do
    if [[ "${current:-}" = "${BASH_COMMAND:-}" ]]; then
        _SENTINEL_ACTIVE=""
        return 0
    fi
  done
  # a non-empty LAST_COMMAND_RAW means this DEBUG-trap firing is a LATER
  # pipeline stage of the SAME command line (the trap fires once per stage). Under
  # HISTSIZE=0 the `history 1` fallback in precmd is empty, so without this branch
  # only the first stage (e.g. `printf foo`) would ever be logged. Accumulate each
  # subsequent stage instead of dropping it. precmd resets LAST_COMMAND_RAW="" between
  # prompts, so this only ever joins stages of a single command line. The joining
  # operator is approximated as ` | ` (bash's DEBUG trap does not expose whether stages
  # were joined by |, &&, ;, etc.); when history is enabled `history 1` still supplies
  # the exact text. The _SENTINEL_ACTIVE mutex already suppresses internal
  # $(date ...) / UUID substitutions, so only genuine user stages reach here.
  # In this edge case the PRE_EXEC runner sees the first stage, not the full line.
  if [[ -n "${LAST_COMMAND_RAW:-}" ]]; then
    LAST_COMMAND_RAW="${LAST_COMMAND_RAW:-} | ${BASH_COMMAND:-}"
    _SENTINEL_ACTIVE=""
    return 0
  fi
  # Detect .bashrc execution and skip it (this must be the first command of .bashrc)
  if [[ -z "${INIT_OVER:-}" && "${BASH_COMMAND:-}" = "source /opt/.exegol_shells_rc" ]]; then
    IS_INIT="Y"
    _SENTINEL_ACTIVE=""
    return 0
  fi

  # BASH_COMMAND variable contain the command to be executed (not the exact same as the user entered)
  LAST_COMMAND_RAW="${BASH_COMMAND:-}"

  # Start timestamp UTC (ISO8601 ms)
  LAST_COMMAND_START_TIME="$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"

  # Generate unique artifact ID
  ARTIFACT_ID=$(< /proc/sys/kernel/random/uuid tr -d '-')

  # Run sentinel profile PRE_EXEC actions
  (LOG_COMMAND_RAW="${LAST_COMMAND_RAW:-}" \
   LOG_COMMAND="${LAST_COMMAND_RAW:-}" \
     /.exegol/sentinel/sentinel_runner.py PRE_EXEC "${ARTIFACT_ID:-}" &)

  # Open this command's window in the session stream. Emitted LAST so it is the
  # final byte before the child's own output, and still inside the
  # _SENTINEL_ACTIVE mutex. The guard keeps a container with no recorder
  # byte-identical to before this feature existed: nothing is written at all.
  # Builtin printf, no redirection, no command substitution — the emit must never
  # surface an error at the prompt.
  if [[ -n "${SENTINEL_SESSION_LOG_RESOLVED:-}" ]]; then
    printf '\033]5379;s;%s\007' "${ARTIFACT_ID:-}"
  fi

  # UNSET mutex on the final exit path
  _SENTINEL_ACTIVE=""
}

# Function PRECMD : called before prompt display and after command execution
function shell_logging_precmd() {
  # Saving previous command returned code for later use
  local exit_code=$?

  # Reset init at the end of .bashrc loading
  if [[ -n "${IS_INIT:-}" ]]; then
    IS_INIT=""
    INIT_OVER="Y"
    return 0
  fi

  # If no registered command, logger is skipped
  if [[ -z "${LAST_COMMAND_RAW:-}" ]]; then
    return 0
  fi

  # End timestamp
  local end_ts
  end_ts="$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"

  # Get last history command
  local histno hist_line
  histno=${HISTCMD:-0}
  hist_line=$(HISTTIMEFORMAT='' history 1 | sed 's/^ *[0-9]\+ *//')

  local cmd cmd_raw
  cmd_raw="${LAST_COMMAND_RAW:-}"

  # dedup branch. When history is disabled (HISTSIZE=0) or HISTCMD is pinned at
  # 0, the HISTCMD guard is unusable (every command shares the same number).
  # We no longer fall back to raw-string comparison in this case: that comparison
  # silently drops a second genuine execution of the same command (audit integrity gap).
  # Re-entrant preexec firing is already prevented by the _SENTINEL_ACTIVE mutex,
  # so no additional dedup is needed when HISTSIZE=0.
  # `$HISTSIZE` may be UNSET, not merely 0 -- `unset HISTSIZE` is a documented way
  # to disable history, and this test exists BECAUSE the author anticipated
  # history being disabled. A bare read here aborted precmd under `set -u` before
  # the end marker and before the logger spawn, and (via the skipped
  # LAST_COMMAND_RAW reset below) took every LATER command with it.
  if [[ "${HISTSIZE:-}" == "0" || "${histno:-0}" -eq 0 ]]; then
    : # _SENTINEL_ACTIVE already prevents double-preexec; no string dedup needed
  else
    # Add a fail-safe in-case this function is called multiple time to avoid log duplication
    if [[ "${histno:-0}" -eq "${LAST_HISTNO:--1}" ]]; then
      return 0
    fi
    LAST_HISTNO=${histno:-0}
  fi

  # If the history line is empty fallback to $LAST_COMMAND_RAW
  [[ -z "${hist_line:-}" ]] && cmd="${LAST_COMMAND_RAW:-}" || cmd="${hist_line:-}"

  # Close this command's window before the logger reads it: after the dedup branch
  # so exactly one end marker is emitted per event, and before the backgrounded
  # logger so the window is complete when it scans.
  # `local exit_code=$?` was captured at the top of this function: a printf
  # clobbers $?, so the marker must never precede that capture.
  if [[ -n "${SENTINEL_SESSION_LOG_RESOLVED:-}" ]]; then
    printf '\033]5379;e;%s\007' "${ARTIFACT_ID:-}"
  fi

  # Run the logger in the background. SENTINEL_SESSION_LOG is handed over from the
  # RESOLVED value, overriding the live exported variable: the logger and the
  # runner read the path from their environment, decided here and nowhere else.
  (LOG_CWD="${PWD:-}" \
  LOG_SHELL_TYPE="bash" \
  SENTINEL_SESSION_LOG="${SENTINEL_SESSION_LOG_RESOLVED:-}" \
  LOG_COMMAND_RAW="${cmd_raw:-}" \
  LOG_COMMAND="${cmd:-}" \
  LOG_START_TIME="${LAST_COMMAND_START_TIME:-}" \
  LOG_END_TIME="${end_ts:-}" \
  LOG_EXIT_CODE="${exit_code:-}" \
  ARTIFACT_ID="${ARTIFACT_ID:-}" \
    /.exegol/sentinel/sentinel_logger.py &)

  # Reset for next command
  LAST_COMMAND_RAW=""
  LAST_COMMAND_START_TIME=""
  ARTIFACT_ID=""
}

# =========
# Wiring hooks bash
# =========

# Trap DEBUG = "preexec" for bash
# This function is called before each interactive command
function bash_preexec_trap() {
  # suppress internal substitutions fired while the handler is running
  [[ -n "${_SENTINEL_ACTIVE:-}" ]] && return 0
  shell_logging_preexec
}

# PROMPT_COMMAND = "precmd" for bash
# We add our function to other PROMPT_COMMAND if already exist
function bash_precmd_inject() {
  # We set PROMPT_COMMAND to call our own precmd first and then others.
  # `:-` because an interactive bash does not necessarily HAVE a PROMPT_COMMAND,
  # and reading it bare under `set -u` aborts this function before the injection
  # -- which removes the precmd hook entirely and takes every audit event with it.
  local old_pc="${PROMPT_COMMAND:-}"
  if [[ -z "${old_pc:-}" ]]; then
    PROMPT_COMMAND="shell_logging_precmd"
  else
    PROMPT_COMMAND="shell_logging_precmd; ${old_pc:-}"
  fi
}

# Enable trap DEBUG only for interactive shell
if [[ $- == *i* ]]; then
  # Setup precmd "hook"
  bash_precmd_inject
  # Setup preexec "hook"
  trap 'bash_preexec_trap' DEBUG
fi
