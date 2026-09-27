#!/usr/bin/env zsh

# =========
# Shell logging hooks for zsh
# =========

# Global variables for cross function data access
typeset -g LAST_COMMAND_RAW=""
typeset -g LAST_COMMAND_RAW_FULL=""
typeset -g LAST_COMMAND_START_TIME=""
typeset -g ARTIFACT_ID=""

# =========
# Sentinel output capture: the session stream this shell is recorded into
# =========
# RESOLVED FROM THE EXEC-TIME ENVIRONMENT, NEVER FROM THE LIVE VARIABLE. The
# bash twin (bash_hooks.sh) carries the full rationale. Two ways a shell learns
# its stream, in priority order:
#
#   1. IT IS A DIRECTLY-RECORDED SHELL -- the one `script` exec'd itself, so it
#      is a session leader (`$$` == its own session id) whose PARENT is that
#      `script` process. Its stream is read from the PARENT's frozen
#      /proc/<ppid>/environ, never from its own: `exec env SENTINEL_SESSION_LOG=x
#      zsh` keeps `$$`==sid and stays parented to `script`, so reading the parent
#      closes that redirect too (a strengthening over the old self-inclusive walk).
#   2. ANY OTHER SHELL -- a sub-shell sharing the pty, or one started without a
#      recorder -- falls back to the OUTERMOST ancestor carrying the variable
#      (the old walk, self included). Outermost, so a nested
#      `SENTINEL_SESSION_LOG=/planted zsh` that could not start its own recorder
#      still resolves the real stream above the planted self value. No carrier
#      anywhere means no recorder, and the hooks emit nothing.
#
# A nested INTERACTIVE shell never reaches (2): sentinel_nested_record below
# gives it its own `script` and its own stream, or none, so two shells' windows
# are never in the same file. Not a boundary: the hooks and the marker id live in
# the operator's shell, so a redefined hook or a forged marker pair is still
# theirs to do.
#
# `${(0)...}` splits the NUL-separated environ; the parent pid is field 2 and the
# session id field 4 of /proc/<pid>/stat after the parenthesised comm (cut at the
# LAST `)`, the comm may contain both). `-r` is checked before every environ read:
# /proc applies a ptrace access check, so a readable-looking environ can still
# fail, and an unguarded `$(< ...)` would leak that error to the prompt.
function sentinel_proc_after_comm() {  # $1=pid -> the post-`)` stat fields, or empty
  [[ -r "/proc/$1/stat" ]] || return 1
  local stat; stat="$(< "/proc/$1/stat")" || return 1
  print -rn -- "${stat##*) }"
}
function sentinel_proc_comm() {  # $1=pid -> the process comm (may contain spaces)
  [[ -r "/proc/$1/stat" ]] || return 1
  local stat; stat="$(< "/proc/$1/stat")" || return 1
  print -rn -- "${${stat%\)*}#*\(}"
}
function sentinel_env_session() {  # $1=pid -> SENTINEL_SESSION_LOG from its environ
  [[ -r "/proc/$1/environ" ]] || return 1
  local entry
  for entry in "${(0)"$(< "/proc/$1/environ")"}"; do
    [[ "$entry" == SENTINEL_SESSION_LOG=* ]] && { print -rn -- "${entry#SENTINEL_SESSION_LOG=}"; return 0; }
  done
  return 1
}
function sentinel_session_log_resolve() {
  local -a pfields sfields
  sfields=("${(z)$(sentinel_proc_after_comm $$)}")
  local ppid="${sfields[2]}" sid="${sfields[4]}"
  # (1) directly-recorded shell: authority is the parent `script`'s environ.
  if [[ -n "$ppid" && "$$" == "$sid" && "$(sentinel_proc_comm $ppid 2> /dev/null)" == script ]]; then
    sentinel_env_session "$ppid" 2> /dev/null && return
  fi
  # (2) fallback: outermost ancestor carrying the variable (self included).
  local pid=$$ found="" v hops=0
  while [[ "$pid" == <1-> ]] && (( pid > 1 && hops < 32 )); do
    v="$(sentinel_env_session $pid 2> /dev/null)" && found="$v"
    pfields=("${(z)$(sentinel_proc_after_comm $pid 2> /dev/null)}")
    pid="${pfields[2]}"; [[ -n "$pid" ]] || break
    (( hops++ ))
  done
  print -rn -- "$found"
}
# ---- A nested interactive shell records ITSELF ----
# Typing `zsh`/`bash` at a recorded prompt used to re-source the hooks and resolve
# the SAME stream, so each inner command's runner punched a hole INSIDE the
# enclosing command's still-open window — reported as a faithful capture over NUL
# bytes. Instead the nested shell starts its OWN `script` on its OWN file. The
# outer `script` still records every byte the inner pty displays, so the enclosing
# window stays faithful; the nested file is cleaned up when that shell exits.
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
  local -a f; local pid hops=0
  typeset -g _sentinel_recorder_depth=0
  f=("${(z)$(sentinel_proc_after_comm $$)}"); pid="${f[2]}"
  while [[ "$pid" == <1-> ]] && (( pid > 1 && hops < 32 )); do
    if [[ "$(sentinel_proc_comm $pid 2> /dev/null)" == script ]] \
       && sentinel_env_session "$pid" > /dev/null 2>&1; then
      (( _sentinel_recorder_depth++ ))
    fi
    f=("${(z)$(sentinel_proc_after_comm $pid 2> /dev/null)}"); pid="${f[2]}"
    [[ -n "$pid" ]] || break; (( hops++ ))
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
  local rest; rest="$(sentinel_proc_after_comm "$1")" || return 1
  local -a f=("${(z)rest}")
  print -rn -- "${f[2]}"
}
function sentinel_is_dash_c_shell() {  # $1=pid -> 0 if it is a shell invoked with -c
  local comm; comm="$(sentinel_proc_comm "$1" 2> /dev/null)" || return 1
  case "$comm" in
    sh|dash|ash|bash|zsh|ksh|busybox) ;;
    *) return 1 ;;
  esac
  [[ -r "/proc/$1/cmdline" ]] || return 1
  local -a args=("${(0)"$(< "/proc/$1/cmdline")"}")
  local a
  for a in "${args[@]}"; do
    [[ "$a" == "-c" ]] && return 0
  done
  return 1
}
function sentinel_directly_recorded() {  # $1=pid of the candidate recorder
  local penv
  [[ -n "$1" ]] || return 1
  [[ "$(sentinel_proc_comm "$1" 2> /dev/null)" == script ]] || return 1
  penv="$(sentinel_env_session "$1" 2> /dev/null)" && [[ -n "$penv" ]] || return 1
  sentinel_recorder_writes "$1" "$penv"
}
function sentinel_recorder_writes() {  # $1=script pid, $2=stream path
  local fd
  for fd in /proc/$1/fd/*(N); do
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
# The bash twin carries the full rationale. In short:
# `blind` used to be set by ANY uninspectable `script` in the pid namespace, so
# one unrelated recorder under another uid made every stream answer 2 and the
# published "nobody is writing it" fall-through became unreachable. Three pieces
# of evidence: the recorder NAMES the stream on its command line (world-readable,
# which is what makes it usable for a process whose fd/ and environ are not), it
# shares our SESSION, or it shares our CONTROLLING TERMINAL with both non-zero.
# Fail-closed if our own stat cannot be read.
function sentinel_recorder_plausible() {  # $1=script pid, $2=stream path -> 0 plausible
  local cmd="" rest
  local -a sfields myfields parts
  # `-r` is checked before the read for the same reason every other /proc read in
  # this file checks it: an unguarded `$(< ...)` leaks its error to the prompt. An
  # unreadable cmdline is not fatal here -- the session/tty comparison below still
  # applies -- so it falls through rather than answering.
  if [[ -r "/proc/$1/cmdline" ]]; then
    parts=("${(0)"$(< /proc/$1/cmdline)"}")
    cmd="${(j: :)parts}"
    [[ "$cmd" == *"$2"* ]] && return 0
  fi
  rest="$(sentinel_proc_after_comm $1 2> /dev/null)" || return 1
  sfields=("${(z)rest}")
  rest="$(sentinel_proc_after_comm $$ 2> /dev/null)" || return 0
  myfields=("${(z)rest}")
  [[ -n "${sfields[4]}" && "${sfields[4]}" == "${myfields[4]}" ]] && return 0
  [[ -n "${sfields[5]}" && "${sfields[5]}" != 0 && "${sfields[5]}" == "${myfields[5]}" ]] && return 0
  return 1
}
function sentinel_recorder_owns() {  # $1=stream path -> 0 owned, 1 nobody, 2 cannot tell
  local proc pid blind=0
  [[ -n "$1" ]] || return 1
  if [[ ! -e "$1" ]]; then
    [[ -x "${1:h}" ]] || return 2
    return 1
  fi
  for proc in /proc/<1->; do
    pid="${proc:t}"
    [[ "$pid" == "$$" ]] && continue
    [[ "$(sentinel_proc_comm $pid 2> /dev/null)" == script ]] || continue
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
  [[ -o interactive ]] || return 0
  local rec="$(sentinel_session_log_resolve 2> /dev/null)"
  [[ -n "$rec" ]] || return 0
  local -a sfields=("${(z)$(sentinel_proc_after_comm $$)}")
  local ppid="${sfields[2]}"
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
# `script -c CMD` runs `$SHELL -c CMD`, and a shell asked to run one simple
# command normally execs it, leaving no process between `script` and the shell.
# That is an OPTIMISATION, NOT AN INVARIANT -- the recursion guard below has said
# so since it was written -- and a $SHELL that forks instead leaves a live
# wrapper in between. Measured: one `sudo -i` produced 7 nested recorders,
# because every directly-recorded shell answered "no" to the parent test and
# broke away into a recorder of its own.
#
# It does not let a genuinely nested shell through: `zsh` typed at a recorded
# prompt has an INTERACTIVE parent, whose argv carries no `-c`. The step is taken
# only when the parent is a `-c` shell AND the grandparent passes the same full
# recorder test as the direct case (comm `script`, its environ names a session
# log, and it holds an open descriptor on it). `sh -c 'zsh -i'` from a recorded
# prompt fails at the grandparent and stays nested.
  if [[ -n "$ppid" ]] && sentinel_is_dash_c_shell "$ppid"; then
    local gpid; gpid="$(sentinel_proc_ppid "$ppid" 2> /dev/null)"
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
  # Everything below re-execs an interpreter of this hook's own choosing, and the
  # rc file is sourced BEFORE the shell acts on its arguments -- so the hook fires
  # first, `script` starts a fresh interpreter with none of them, and `exit "$rc"`
  # reports that shell's status as if it were the original invocation's. For
  # `bash -i -c CMD` / `zsh -i -c CMD` that meant CMD WAS NEVER RUN and never
  # reported as not run: the operator (or the tool) was parked in an unrelated
  # interactive shell, and with no terminal on stdin it exited immediately having
  # done nothing. `bash -ic` is not exotic -- it is how `tmux set default-command`,
  # `xterm -e`, IDE terminals, wrapper scripts and `ssh -t host 'bash -ic ...'`
  # ask for a shell with the user's aliases and functions.
  #
  # util-linux `script` has no argv form -- `-c` is a STRING it hands to `sh -c`
  # (see `script --help`: "-c, --command <command>") -- so an invocation can only
  # be carried across by re-quoting it into that string, and any invocation
  # property that is not exposed to the rc file cannot be carried across at all
  # (`--rcfile` is not recoverable from within bash; neither is the distinction
  # between an option set at invocation and the same option set by the rc).
  #
  # SO: reproduce what can be reproduced faithfully and REFUSE THE CAPTURE for
  # everything else — never silently run something different. A refusal returns 1,
  # which blanks the resolved stream: the shell runs its own original invocation,
  # unrecorded, with `output_status: unavailable` on its commands.
  #
  # REPRODUCED: interactivity (`script` always allocates a pty) and the login flag.
  #
  # REFUSED:
  #   * a command string (`-c CMD`);
  #   * positional parameters (`sh -is a b`), silently dropped otherwise;
  #   * a SCRIPT FILE OPERAND (`zsh -i prog.zsh`) — a different test: it reaches
  #     .zshrc with `$#` == 0 and an empty ZSH_EXECUTION_STRING, so it passed every
  #     other check and the replacement shell never ran the script. `$ZSH_SCRIPT`
  #     is the script name when zsh was invoked to run one and unset otherwise.
  #     NOT `$ZSH_ARGZERO`, which is the shell's invocation name otherwise, and not
  #     `$0`, which is `zsh` in both cases (the bash twin has the opposite problem
  #     and needs a different test);
  #   * a RESTRICTED shell, which matters most: `script -c "$interp"` starts an
  #     UNRESTRICTED interpreter, so breaking away would hand the operator a way
  #     out of the restriction;
  #   * any `$-` letter changing execution semantics that is not carried across
  #     (xtrace, verbose, nounset, errexit, noglob, noexec, onecmd, keyword,
  #     allexport, noclobber, privileged, restricted). A denylist, not a diff
  #     against a baseline `$-`: the baseline varies with job control, with stdin,
  #     and between dialects.
  #
  # NOT REFUSED, and why — the bash twin carries the same reasoning at length. In
  # short: a REDIRECTED STDIN survives because `script` forwards its own stdin into
  # the pty; `--emulate sh` never reaches this gate, because such a shell does not
  # read .zshrc; and options with no `$-` letter plus an alternate startup file
  # (`ZDOTDIR`) are the deliberate residual — from inside .zshrc they are
  # indistinguishable from the same state set by .zshrc itself, so refusing on it
  # would disable capture systematically in any image whose rc sets one.
  [[ -n "${ZSH_EXECUTION_STRING:-}" ]] && return 1
  (( ${_sentinel_shell_argc:-0} > 0 )) && return 1
  [[ -o restricted ]] && return 1
  case "$-" in *[xvuefntkaCpr]*) return 1 ;; esac
  [[ -n "${ZSH_SCRIPT:-}" ]] && return 1
  # FROM HERE THIS SHELL IS NESTED and every remaining exit is a REFUSAL, never a
  # fallback to sharing. Sharing is the defect itself: the inner shell's bytes
  # reach the
  # enclosing stream, so its marker pairs open windows strictly INSIDE the
  # enclosing command's still-open window, and each inner runner then punches a
  # hole in it -- published as `status: "ok"`, `bytes_written == bytes_total`
  # over NUL bytes. `PATH=/nonexistent zsh` reaches that from the prompt in one
  # line. Returning non-zero blanks the resolved stream instead, so the nested
  # shell emits no markers at all and its commands carry `output_status:
  # unavailable` -- the same value a container with no recorder produces, and an
  # honest one. Availability of the CAPTURE is given up; the shell still runs.
  # THE RUNNING INTERPRETER, not a PATH lookup: `${commands[zsh]}` re-resolves
  # `zsh` against the current PATH, so a writable PATH entry would decide which
  # binary the operator's nested shell is. bash uses `$BASH` for the same reason.
  # NOT `$ZSH_ARGZERO`: it is the SCRIPT NAME when zsh was invoked to run one, so
  # under `zsh -i somescript.zsh` trusting it would re-exec that script as the
  # interpreter.
  #
  # `/proc/self/exe` is the running binary by construction, and `:A` resolves it
  # with no fork and no external. It cannot be spelled as the interpreter
  # directly, because `script` hands the string to `sh -c` and /proc/self is then
  # `sh`'s own view, not this shell's. `${commands[zsh]}` remains the fallback for
  # an image with no /proc (where the rest of this file has already given up).
  local interp="${${:-/proc/self/exe}:A}"
  [[ "$interp" == /* && -x "$interp" ]] || interp="${commands[zsh]}"
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
  (( $+commands[script] )) || return 1                  # no recorder -> no capture
  # The login flag is the one invocation property reproduced: the rc file can see
  # it, and it is one more word in `script`'s command string.
  local invoke="$interp"
  [[ -o login ]] && invoke="$invoke -l"
  local dir="${rec:h}" mine="${rec:h}/session_nested_$$.log" attempt=0
  # O_CREAT|O_EXCL (`set -C`) + umask 077 so the file is 0600 and a planted
  # symlink in the world-nothing 0700 dir cannot redirect the write. The dir was
  # created and symlink-checked by spawn.sh; a collision only retries the name.
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
  # DID `script` EVER START A SHELL? Past this point the gate has committed, and
  # until now there was no recovery left: `script` failing (pty exhaustion, a
  # container with no /dev/pts mounted, an `openpty` denied by seccomp) returned
  # non-zero without ever starting a shell, and the hook `exit`ed with it. Typing
  # `zsh` at the prompt then returned immediately with NO SHELL AT ALL, on a
  # container where typing `zsh` worked before this feature existed.
  #
  # A nested shell that cannot start a recorder is given no STREAM; it is never
  # given no shell. "Refuse the shell rather than run unrecorded" is scoped to the
  # SESSION shell in spawn.sh, where the operator gets a message naming a remedy;
  # here they would get a bare non-zero status.
  #
  # The discriminator is whether the recorder wrote its header. `script` emits it
  # into the typescript as soon as the pty is up and before it execs anything, so
  # an empty file means no shell was ever started; the create above left the file
  # at zero bytes, so this is exactly the question "did the recorder get going".
  # (A `script` that starts a shell which then immediately fails leaves the
  # header plus the shell's own diagnostic, so it is correctly read as "the inner
  # shell exited with this code" -- the whole point of `-e`.)
  #
  # REFUSE THE CAPTURE, NOT THE SHELL: fall through to the no-stream path, the
  # same one the four pre-commit bail-outs take. The shell keeps running with
  # `output_status: unavailable` on its commands.
  if [[ ! -s "$mine" ]]; then
    sentinel_nested_cleanup "$mine"
    return 1
  fi
  sentinel_nested_cleanup "$mine"
  exit "$rc"
}
# Release the nested stream once the inner shell is gone (spawn.sh's EXIT-trap
# cleanup, inlined for the file this shell owns): wait -- bounded -- for an
# in-flight runner or logger still reading THIS stream so an unlimited
# output_capture is not cut short, then unlink. Pure zsh over /proc, no `grep`.
function sentinel_nested_cleanup() {
  local target="$1" waited=0 proc pid busy entry
  if [[ -r /proc/self/environ ]]; then
    while (( waited < 60 )); do
      busy=0
      for proc in /proc/<1->; do
        pid="${proc:t}"; [[ "$pid" == "$$" ]] && continue
        [[ -r "$proc/cmdline" ]] || continue
        # `[[ -r ]]` above is a TOCTOU test, not a lock: a process can exit between
        # it and this read, and an unsuppressed failure prints
        # `zsh: no such file or directory: /proc/<pid>/cmdline` -- at the moment
        # the operator is returning to their prompt, once per pid, up to 60 times.
        # The suppression sits on the ASSIGNMENT rather than inside the `$(<...)`:
        # zsh diagnoses the unreadable file in the enclosing shell, so a
        # `2> /dev/null` written inside the substitution does not catch it (and
        # would also cost the no-fork fast path). Same for the environ loop below,
        # whose read happens while the `for` word list is expanded.
        local cmd="$(< $proc/cmdline)" 2> /dev/null
        [[ "$cmd" == *sentinel_runner.py* || "$cmd" == *sentinel_logger.py* ]] || continue
        [[ -r "$proc/environ" ]] || continue
        for entry in "${(0)"$(< $proc/environ)"}"; do
          [[ "$entry" == "SENTINEL_SESSION_LOG=$target" ]] && { busy=1; break; }
        done 2> /dev/null
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
# THE RESOLVED VALUE IS READONLY -- see the long note at the same point in
# bash_hooks.sh. In short: the /proc walk was defeated by its own storage, since
# `SENTINEL_SESSION_LOG_RESOLVED=<planted>` at the prompt redirected the logger
# and the empty string switched capture off entirely.
#
# The guard tests the READONLY ATTRIBUTE rather than emptiness. `source ~/.zshrc`
# at the prompt is routine and reassigning a readonly parameter is a hard error,
# so a value that is already readonly is ours and is left alone; a value that is
# merely set (an inherited `export SENTINEL_SESSION_LOG_RESOLVED=/planted`) is
# not ours and is overwritten by the real resolution before being frozen.
#
# `readonly` is not a boundary: the hooks remain redefinable and a forged marker
# pair remains printable. It closes the environment/parameter path only.
#
# THE SAME ATTRIBUTE GATES THE GATE ITSELF, not just the storage of its answer --
# see the long note at the same point in bash_hooks.sh. In short:
# `sentinel_nested_record` MAY START A `script` AND `exit`, and it used to run
# unconditionally above this `if`, so `source ~/.zshrc` at the prompt re-ran it.
# Either the answer was unchanged and the scan ran for nothing (the value is
# already readonly, so it could not be stored), or the answer had changed and the
# re-source broke away -- starting a recorder, replacing the operator's shell, and
# terminating their session on the `exit "$rc"` when that shell ended. Computed
# once per shell, keyed on the attribute the value is keyed on.
#
# SEEDED FIRST -- see the same point in bash_hooks.sh. `${(t)VAR}` on an UNSET
# parameter is a "parameter not set" error under `setopt nounset`, exactly as
# bash's `${VAR@a}` is, and it skipped this whole `if` body: no gate, no
# resolution, no freeze, and the logger hand-off in shell_logging_precmd died the
# same way. Measured: a `setopt nounset` interactive zsh wrote ZERO audit events
# where the same shell without it wrote one per command.
#
# `: ${VAR=}` is `nounset`-safe, assigns ONLY when unset (so a re-source cannot
# trip the readonly), and the empty string carries no `readonly` attribute -- a
# planted/inherited value still fails the `*readonly*` test and is still
# overwritten by the real resolution.
# shellcheck disable=SC2296 (zsh syntax not supported by shellcheck)
: ${SENTINEL_SESSION_LOG_RESOLVED=}
if [[ ${(t)SENTINEL_SESSION_LOG_RESOLVED} != *readonly* ]]; then
  # May exec-and-exit (the nested case). A non-zero return is the third answer:
  # nested inside a recorder it must not share and could not break away from, so
  # it resolves to NO stream rather than to the enclosing one.
  sentinel_nested_record
  _sentinel_nested_refused=$?
  if (( _sentinel_nested_refused )); then
    typeset -gr SENTINEL_SESSION_LOG_RESOLVED=""
  else
    typeset -gr SENTINEL_SESSION_LOG_RESOLVED="$(sentinel_session_log_resolve 2> /dev/null)"
  fi
fi
# Nothing may recompute the value after this point, so the resolver functions do
# not stay in the operator's namespace as redefinable hooks.
unfunction sentinel_session_log_resolve sentinel_nested_record sentinel_nested_cleanup \
  sentinel_recorder_ancestor sentinel_recorder_writes sentinel_recorder_owns \
  sentinel_recorder_plausible \
  sentinel_proc_after_comm sentinel_proc_comm sentinel_env_session
# Scratch of the ancestry walk and of the gate's answer, kept out of the
# operator's namespace with them.
unset _sentinel_recorder_depth _sentinel_nested_refused

# =========
# EVERY PARAMETER READ BELOW THIS LINE IS `${VAR:-}`-GUARDED, WITHOUT EXCEPTION
# =========
# Not a style preference: it is the fix for a blocker that was diagnosed and
# patched twice as "this ONE expansion is unsafe", and came back both times
# because the neighbouring reads were left bare.
#
# Under `setopt nounset` / `set -u` a bare read of an unset parameter is a "parameter not set"
# error that ABORTS THE ENCLOSING FUNCTION, and in an interactive shell it aborts the
# command instead of exiting -- so it is completely silent. Aborting
# shell_logging_precmd costs three things at once:
#
#   * the end marker is never emitted, leaving an unterminated window in the
#     session stream;
#   * the logger is never spawned, so the command produces NO EVENT -- not
#     `output_status: unavailable`, nothing at all;
#   * the `LAST_COMMAND_RAW=""` reset at the bottom is skipped, so the NEXT
#     preexec takes the pipeline-continuation branch and returns early. From then
#     on not even the start marker is emitted: THE LOSS IS TERMINAL FOR THE
#     SESSION, not per-command.
#
# Every parameter here is a global in the operator's own interactive shell, so
# each one is a single `unset` away from being unset whatever the surrounding
# code assumes -- and `unset HISTSIZE` is half of the documented
# `unset HISTFILE; unset HISTSIZE` idiom, i.e. reachable with no intent at all
# and a one-line audit-evasion primitive typed at a recorded prompt.
#
# `tests/sentinel/test_hook_nounset_lint.py` fails the build on the next bare
# read added here, which is what stops a fourth iteration of this finding.

# Hook called BEFORE command execution
function shell_logging_preexec() {
  # $1 : command from the user that will be executed
  LAST_COMMAND_RAW="${1:-}"
  # $3 : fully resolved command without alias
  LAST_COMMAND_RAW_FULL="${3:-}"
  # Start timestamp UTC (ISO8601 ms)
  LAST_COMMAND_START_TIME="$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"
  # Generate unique artifact ID
  ARTIFACT_ID=$(< /proc/sys/kernel/random/uuid tr -d '-')

  # Run sentinel profile PRE_EXEC actions in a detached bg job
  LOG_COMMAND_RAW="${LAST_COMMAND_RAW_FULL:-}" \
  LOG_COMMAND="${LAST_COMMAND_RAW:-}" \
    /.exegol/sentinel/sentinel_runner.py PRE_EXEC "${ARTIFACT_ID:-}" &!

  # Sentinel output capture: open this command's window in the session stream.
  # Emitted LAST so it is the final byte written before the child's own output.
  # The guard is what keeps a container with no recorder byte-identical to
  # before this feature existed: with no recorder in the ancestry nothing is
  # written to the terminal at all. The RESOLVED path, not the live variable:
  # see sentinel_session_log_resolve. Builtin printf, no redirection, no command
  # substitution -- the emit must never be able to surface an error at the prompt.
  if [[ -n "${SENTINEL_SESSION_LOG_RESOLVED:-}" ]]; then
    printf '\033]5379;s;%s\007' "${ARTIFACT_ID:-}"
  fi
}

# Hook called AFTER command execution and before PROMPT display
function shell_logging_precmd() {
  # Saving previous command returned code for later use
  local exit_code=$?

  # If no registered command, logger is skipped
  [[ -z "${LAST_COMMAND_RAW:-}" ]] && return 0

  # End timestamp
  local end_ts
  end_ts="$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"

  local cmd_raw cmd
  cmd="${LAST_COMMAND_RAW:-}"

  # shellcheck disable=SC2296 (zsh syntax not supported by shellcheck)
  cmd_raw="${LAST_COMMAND_RAW_FULL:-}"

  # Close this command's window before the logger reads it, so the window is
  # complete when the backgrounded logger scans for it. `local exit_code=$?` was
  # captured at the top of this function: a printf clobbers $?, so the marker
  # must never precede that capture.
  if [[ -n "${SENTINEL_SESSION_LOG_RESOLVED:-}" ]]; then
    printf '\033]5379;e;%s\007' "${ARTIFACT_ID:-}"
  fi

  # Send metadata and write in background. SENTINEL_SESSION_LOG is handed over
  # EXPLICITLY from the resolved value, overriding whatever the live exported
  # variable says: this is the one place the logger's environment is decided.
  LOG_CWD="${PWD:-}" \
  LOG_SHELL_TYPE="zsh" \
  SENTINEL_SESSION_LOG="${SENTINEL_SESSION_LOG_RESOLVED:-}" \
  LOG_COMMAND_RAW="${cmd_raw:-}" \
  LOG_COMMAND="${cmd:-}" \
  LOG_START_TIME="${LAST_COMMAND_START_TIME:-}" \
  LOG_END_TIME="${end_ts:-}" \
  LOG_EXIT_CODE="${exit_code:-}" \
  ARTIFACT_ID="${ARTIFACT_ID:-}" \
    /.exegol/sentinel/sentinel_logger.py &!

  # Reset for next command
  LAST_COMMAND_RAW=""
  LAST_COMMAND_RAW_FULL=""
  LAST_COMMAND_START_TIME=""
  ARTIFACT_ID=""
}

# =========
# Wiring hooks zsh
# =========

typeset -a preexec_functions
# append the function to our array of preexec functions
preexec_functions+=(shell_logging_preexec)

typeset -a precmd_functions
# append the function to our array of precmd functions
precmd_functions+=(shell_logging_precmd)
