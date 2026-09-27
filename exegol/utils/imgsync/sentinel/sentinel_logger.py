#!/usr/bin/env python3
import json
import os
import sys
import time
import fcntl
import fnmatch
import gzip
import uuid
import subprocess
from datetime import datetime, UTC
from pathlib import Path

LOG_DIR = Path("/var/log/exegol/sentinel")
LOG_FILE = LOG_DIR / "logs.json"
LOG_FILE_MODE = 0o640

# Minimum interval between two rotations. A tailer following renames can only hop one
# inode per poll, so two rotations between polls would skip a generation. logs.json may
# briefly exceed max_size instead, which is preferable to losing events.
DEFAULT_MIN_ROTATION_INTERVAL_SEC = 0.5

# The POST_EXEC runner is detached; the logger waits at most this long for it so that
# artifact_id is usually linked, without ever delaying the audit event on a long action.
RUNNER_HEADSTART_SEC = 1.0

import re
from typing import Optional, Tuple, List

# Shared with sentinel_runner.py so the inline event field and the output_capture
# artifact cannot disagree on marker syntax or cleaning. Two import shapes:
# deployed the scripts are flat in /.exegol/sentinel/, tests import them as a
# package.
try:
    from .sentinel_output import (  # type: ignore[import-not-found]
        OUTPUT_STATUS_ERROR, OUTPUT_STATUS_UNAVAILABLE, REDACTED_MARKER,
        TRUNCATION_MARKER_FMT, clean, floor_window, redact_values, scan_window,
        truncate_text,
        validated_session_path,
    )
except ImportError:
    from sentinel_output import (  # type: ignore[no-redef]
        OUTPUT_STATUS_ERROR, OUTPUT_STATUS_UNAVAILABLE, REDACTED_MARKER,
        TRUNCATION_MARKER_FMT, clean, floor_window, redact_values, scan_window,
        truncate_text,
        validated_session_path,
    )

# Default inline cap and cut mode, used when the deployed config carries no
# log_output block (an older host wrapper). Mirrors LogOutputConfig's defaults.
DEFAULT_OUTPUT_MAX_SIZE = 4 * 1024
DEFAULT_OUTPUT_TRUNCATION = "both"

# Default rotation cap, used when the deployed config carries no usable
# max_size. Mirrors LogRotationConfig's field default and UserConfig's "100MB".
DEFAULT_ROTATION_MAX_SIZE = 100 * 1024 * 1024

# Bounded retry for the end-marker scan. The hooks print the end marker into the pty slave
# and immediately background this logger, so `script` may not have flushed it into the file
# we scan yet; a single pass would report that as a permanent `output_status: unavailable`,
# indistinguishable from the benign causes. The 5 x 20 ms is paid only on that path: an
# existing window is found on the first pass, and no session file returns before the loop.
OUTPUT_WINDOW_SCAN_ATTEMPTS = 5
OUTPUT_WINDOW_SCAN_DELAY_SEC = 0.02

# Use os.environb to handle potential binary data in env vars
envb = os.environb

_VAR1 = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
_VAR2 = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)}")


# What get_env_safe returns for a value that is not valid UTF-8. Named because the
# redaction pass has to recognise it: substituting a stand-in into captured text
# would mask an unrelated literal while protecting nothing.
BINARY_VALUE_MARKER = "<BINARY DATA>"


def get_env_safe(key: str, default: str = "") -> str:
    val_b = envb.get(key.encode("utf-8", errors="ignore"), default.encode("utf-8"))
    try:
        return val_b.decode("utf-8")
    except UnicodeDecodeError:
        return BINARY_VALUE_MARKER

def expand_env_vars_safe(command: str, redact_names: List[str] | None = None) -> Tuple[str, dict[str, str], List[str]]:
    """
    Expand $VAR and ${VAR} safely:
      - No command execution (does NOT evaluate $(...) or backticks)
      - No expansion inside single quotes
      - Expansion inside double quotes and unquoted text
    This is NOT a full shell parser; it's a pragmatic safe expander.

    ``redact_names`` is the profile ``env_redact`` glob denylist. When a $VAR / ${VAR} whose
    name matches one of those globs (fnmatch.fnmatchcase) is expanded, its value is replaced
    by ``REDACTED_MARKER`` both in the returned resolved command string and in the returned
    env_vars map, so a secret pulled in via a variable never leaks into ``resolved_command``.
    Names are matched, values are masked.

    The third return value is the list of real values masked on this command line. It is not
    enough to mask captured output on its own -- a listed variable the command never names
    (`env`, `printenv`, `set`) never reaches it -- so the caller unions it with
    :func:`redact_candidates`.
    """
    def _is_redacted(name: str) -> bool:
        if not redact_names:
            return False
        return any(fnmatch.fnmatchcase(name, p) for p in redact_names)

    out: list[str] = []
    env_vars: dict[str, str] = {}
    redacted_values: list[str] = []
    i = 0
    n = len(command)
    in_single = False
    in_double = False

    while i < n:
        ch = command[i]

        # Toggle quote states (only when not escaped)
        if ch == "'" and not in_double:
            in_single = not in_single

        elif ch == '"' and not in_single:
            in_double = not in_double

        # Never expand inside single quotes. Checked before the backslash handler because a
        # backslash is literal there and must not swallow the closing quote.
        elif in_single:
            pass

        # Handle backslash escapes (keep behavior simple & safe)
        elif ch == "\\" and i + 1 < n:
            out.append(ch)
            out.append(command[i + 1])
            i += 2
            continue

        # Detect $() and backticks and leave them untouched (no parsing inside)
        elif ch == "$" and i + 1 < n and command[i + 1] == "(":
            # copy "$(" then continue; we do not attempt to parse nested parentheses here
            out.append("$(")
            i += 2
            continue
        elif ch == "`":
            out.append("`")
            i += 1
            continue

        # Expand $VAR / ${VAR}
        elif ch == "$":
            if i + 1 < n and command[i + 1] == "{":
                # Handle ${VAR}
                m = _VAR2.match(command, i)
            else:
                # Handle $VAR
                m = _VAR1.match(command, i)
            if m:
                name = m.group(1)
                if _is_redacted(name):
                    value = REDACTED_MARKER
                    real = get_env_safe(name)
                    # An unset variable and an undecodable one carry nothing to
                    # match against the decoded capture, so neither joins the list.
                    if real and real != BINARY_VALUE_MARKER:
                        redacted_values.append(real)
                else:
                    value = get_env_safe(name)

                out.append(value)
                env_vars[name] = value
                i = m.end()
                continue

        out.append(ch)
        i += 1

    return "".join(out), env_vars, redacted_values


def redact_candidates(redact_names: Optional[List[str]] = None) -> List[str]:
    """Every environment value whose name matches an ``env_redact`` glob.

    Globs the environment directly, independently of what the operator typed: the leak that
    matters for captured output is the command that never mentions the variable and prints it
    anyway (``env``, ``printenv``, a tool dumping its own config). Unioned by the caller with
    ``expand_env_vars_safe``'s list rather than replacing it -- that one also carries values
    redacted for another reason.

    Values that do not decode as UTF-8 are skipped: they carry nothing to match against the
    decoded capture. The length floor lives in :func:`sentinel_output.redact_values`.
    """
    if not redact_names:
        return []
    out: List[str] = []
    for name_b, value_b in envb.items():
        try:
            name = name_b.decode("utf-8")
            value = value_b.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if value and any(fnmatch.fnmatchcase(name, pattern) for pattern in redact_names):
            out.append(value)
    return out


def _prune(max_files: int) -> None:
    """Delete oldest rotated files when max_files > 0."""
    if max_files <= 0:
        return
    # Rotated files have the form logs.{ts}.json or logs.{ts}.json.gz
    rotated = sorted(
        p for p in LOG_DIR.iterdir()
        if p.name.startswith("logs.") and p.name != "logs.json"
    )
    for old in rotated[:-max_files]:
        try:
            old.unlink()
        except OSError:
            pass


def _newest_rotated_mtime() -> float:
    """Return the newest mtime among rotated ``logs.*`` files, or ``0.0`` if none."""
    newest = 0.0
    try:
        for p in LOG_DIR.iterdir():
            if p.name.startswith("logs.") and p.name != "logs.json":
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                if mtime > newest:
                    newest = mtime
    except OSError:
        return 0.0
    return newest


def _rotate(cfg: dict) -> bool:
    """Rename logs.json -> logs.{ts}.json[.gz], then prune. Must be called inside LOCK_EX.

    Returns False when debounced (see DEFAULT_MIN_ROTATION_INTERVAL_SEC).
    """
    # Debounce: skip rotating when a rotated sibling's mtime is within `grace`
    # seconds. Read as an optional dict key with a safe default, so
    # LogRotationConfig has no field for it and the host validator cannot reject a
    # bad value — coerced here, or `min_interval_sec: "5s"` raises TypeError, the
    # event is dropped, and so is every later one once the log passes max_size.
    _raw_grace = cfg.get("min_interval_sec", DEFAULT_MIN_ROTATION_INTERVAL_SEC)
    grace = (_raw_grace if isinstance(_raw_grace, (int, float))
             and not isinstance(_raw_grace, bool) and _raw_grace >= 0
             else DEFAULT_MIN_ROTATION_INTERVAL_SEC)
    if grace > 0 and (time.time() - _newest_rotated_mtime()) < grace:
        return False
    # Microseconds avoid same-second collisions and keep names sortable for pruning.
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    rotated = LOG_DIR / f"logs.{ts}.json"
    # rename() would silently overwrite an existing rotated file: add a counter instead.
    counter = 0
    while rotated.exists():
        counter += 1
        rotated = LOG_DIR / f"logs.{ts}.{counter}.json"
    LOG_FILE.rename(rotated)  # inode-preserving rename
    if cfg.get("compress", True):
        gz_path = rotated.with_suffix(rotated.suffix + ".gz")
        try:
            with rotated.open("rb") as src, gzip.open(gz_path, "wb") as dst:
                dst.write(src.read())
            rotated.unlink()
        except OSError:
            # Compression failure (e.g. ENOSPC) must not drop the event: keep the
            # uncompressed file and remove any partial .gz.
            try:
                gz_path.unlink()
            except OSError:
                pass
    # Pruning must never crash the writer or drop the current event.
    try:
        _prune(cfg.get("max_files", 0))
    except Exception:
        pass
    return True


def _write_event_locked(line: str, rotation_cfg: dict) -> None:
    """Append ``line`` to LOG_FILE under fcntl.LOCK_EX, rotating if oversized.

    Rotation (size check + rename + gzip + prune, see ``_rotate``) runs inside
    the held lock, before the write. To stay correct under concurrent writers:

      * After acquiring the lock we verify our fd still points at the inode that
        ``LOG_FILE`` names. If another writer rotated logs.json out from under us
        while we were blocked on the lock, our fd now references the rotated
        (possibly already-gzipped-and-unlinked) inode, so we drop it, reopen the
        fresh logs.json and re-lock — never writing the event into a stale inode.
      * Size is read via ``os.fstat`` on the *locked* fd, so the check reflects
        exactly the inode we are about to write to.
      * After we rotate, the fresh logs.json is empty, so a second writer that
        re-runs this loop will not double-rotate.
      * The write is FLUSHED before the unlock, so the bytes reach the inode we
        validated while we still own it -- without it the two guarantees above
        are words only (see the ``f.flush()`` call).
    """
    while True:
        if not LOG_FILE.is_file():
            LOG_FILE.touch(mode=LOG_FILE_MODE, exist_ok=True)
        f = LOG_FILE.open("a", encoding="utf-8")
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            # Rotated while waiting for the lock: reopen and retry.
            try:
                fd_ino = os.fstat(f.fileno()).st_ino
                path_ino = os.stat(LOG_FILE).st_ino
            except FileNotFoundError:
                path_ino = -1
                fd_ino = os.fstat(f.fileno()).st_ino
            if fd_ino != path_ino:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                f.close()
                continue

            if rotation_cfg.get("enabled", True):
                # Coerced, like _cap/_mode below: nothing re-validates the deployed config
                # in the container, and an unusable value here does not degrade -- it raises
                # out of the write and drops the event, and every later one. "100MB" is the
                # reachable case, the spelling UserConfig ships. An unreadable value falls
                # back to the default cap, never to "no bound": rotation is the only limit on
                # logs.json. An explicit 0 is different and is honoured as unlimited, the
                # reading max_files already has. bool is excluded -- rotating at 1 byte is
                # nobody's config.
                _raw_limit = rotation_cfg.get("max_size", DEFAULT_ROTATION_MAX_SIZE)
                if isinstance(_raw_limit, int) and not isinstance(_raw_limit, bool) and _raw_limit >= 0:
                    limit = _raw_limit or None  # 0 -> None == never rotate
                else:
                    limit = DEFAULT_ROTATION_MAX_SIZE
                if limit is not None and os.fstat(f.fileno()).st_size >= limit:
                    if _rotate(rotation_cfg):
                        # Reopen to write into the fresh logs.json, not the rotated inode.
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        f.close()
                        continue
                    # Debounced: write into the over-limit file (reopening would loop forever).

            f.write(line)
            # Flushed while the lock is still held. `f` is a buffered TextIOWrapper, so
            # `write` issues no write(2): without this the bytes sat in the user-space buffer
            # until `f.close()` in the `finally`, after LOCK_UN, which defeated everything
            # above -- the inode re-check was bypassed (a writer that rotated in that window
            # left our bytes in an unlinked inode: event lost, no error, exit code 0) and the
            # size check ran on bytes not yet on disk. flush() and not fsync(): what is
            # needed is write(2) ordering against another process holding the same lock,
            # which the page cache gives.
            f.flush()
            return
        finally:
            if not f.closed:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                f.close()


def _locate_output_window(artifact_id: str) -> Optional[Tuple[int, int, bool]]:
    """Return this command's ``(start, end)`` offsets in the session stream.

    ``None`` whenever the recorder is not running, the stream is unreadable, or
    both markers are not present within the bounded backward scan. A missing
    window is a normal outcome (no recorder, a nested pty, redirected output) and
    must never cost the audit event — hence the bare except: every failure mode of
    a file we do not control resolves to the same answer, "no window".

    Retried because "not there yet" and "not coming" are different facts a single
    pass cannot tell apart. See :data:`OUTPUT_WINDOW_SCAN_ATTEMPTS`.
    """
    # Handed over by the hooks from the exec-time environment of the shell and its
    # ancestors, overriding the live exported variable — and validated anyway, so
    # the confinement still holds for a value arriving by any other route.
    session_path = validated_session_path(get_env_safe("SENTINEL_SESSION_LOG"))
    if not session_path or not artifact_id:
        return None
    for attempt in range(OUTPUT_WINDOW_SCAN_ATTEMPTS):
        try:
            with open(session_path, "rb") as stream:
                scan = scan_window(stream, artifact_id)
        except Exception:
            # Unreadable/absent stream -> no window, event unaffected. Not retried:
            # unlike a missing marker, this does not resolve itself.
            return None
        if scan.window is not None:
            return (scan.window[0], scan.window[1], False)
        # Only the recoverable failure is retried. A missing end marker is the race this
        # retry exists for: bounded by SCAN_LIMIT, cheap, and it resolves once `script`
        # flushes. A missing start marker with the end marker present is deterministic
        # (window past WINDOW_SCAN_LIMIT, or the marker punched away), and each re-ask walks
        # a full 512 MiB for the same final answer.
        if scan.end_marker_found:
            # Walk 2 gave up, which is itself the proof the range is ours. Reporting
            # `unavailable` would tell an analyst nothing was captured while up to
            # WINDOW_SCAN_LIMIT of output sits on disk, and would leave the release
            # with no offsets, so a `cat` of a 1 GB file keeps its gigabyte until the
            # shell exits. A floor window fixes both: the artifact is written and
            # marked truncated with its start declared a floor, and the bytes are
            # punched. See floor_window for why the range is proven, not guessed.
            if scan.end_offset is not None:
                floor_start, floor_end = floor_window(scan.end_offset)
                if floor_end > floor_start:
                    return (floor_start, floor_end, True)
            return None
        if attempt + 1 < OUTPUT_WINDOW_SCAN_ATTEMPTS:
            time.sleep(OUTPUT_WINDOW_SCAN_DELAY_SEC)
    return None


def _trim_split_marker_suffix(kept: str, full: str) -> str:
    """Drop a trailing fragment of :data:`REDACTED_MARKER` that the byte cut split.

    ``kept`` is a prefix of ``full``, the decoded whole slice. A ``both`` cut is a byte slice
    taken after redaction, so it can land inside a marker and leave ``<REDAC`` at the end of
    the head: no secret leaks, but the fragment reads as text the terminal printed and no SIEM
    rule matching ``<REDACTED>`` sees it. Trimmed only when ``full`` really carries the whole
    marker there, so genuine output ending in ``<RE`` is kept.
    """
    for k in range(len(REDACTED_MARKER) - 1, 0, -1):
        if kept.endswith(REDACTED_MARKER[:k]) and full.startswith(REDACTED_MARKER, len(kept) - k):
            return kept[:-k]
    return kept


def _trim_split_marker_prefix(kept: str, full: str) -> str:
    """Mirror of :func:`_trim_split_marker_suffix` for the tail slice.

    ``kept`` is a suffix of ``full``; a marker split by the tail cut leaves its
    end (``ACTED>``) at the front of the kept text.
    """
    offset = len(full) - len(kept)
    for k in range(len(REDACTED_MARKER) - 1, 0, -1):
        start = offset - (len(REDACTED_MARKER) - k)
        if start >= 0 and kept.startswith(REDACTED_MARKER[-k:]) and full.startswith(REDACTED_MARKER, start):
            return kept[k:]
    return kept


def _read_output_field(window: Tuple[int, int], cap: int, mode: str,
                       secrets: List[str]) -> Optional[Tuple[str, bool, int]]:
    """Return ``(text, truncated, window_bytes)`` for the inline event field.

    Reads O(cap) bytes, never O(window). When the window is larger than the
    head+tail budget the middle is never read at all, and ``truncated`` is true
    even if the surviving text cleans down below the cap -- bytes were dropped,
    and the field must say so.

    Only the read is O(cap): locating the window walks backwards from the end marker to the
    start marker, so that costs a pass over the window, and one larger than
    WINDOW_SCAN_LIMIT is refused outright rather than read cheaply.

    ``window_bytes`` comes from the marker offsets, not from what was read, so it reports the
    true size the terminal produced -- redaction changes the text, never the size. It is a raw
    byte count while ``text`` is cleaned, so the two disagree even when nothing was dropped:
    every escape sequence, ``\r`` and control byte ``clean`` strips is counted here and absent
    there. Only ``truncated`` reports whether content was dropped.

    ``secrets`` is the union of the values masked on the command line and every environment
    value whose name matches an ``env_redact`` glob -- the second half covers a command that
    prints a listed secret without ever naming it.
    """
    # Re-validated rather than passed down from _locate_output_window: this
    # function opens the file itself, and a check living at one call site is one
    # the next call site silently does without.
    session_path = validated_session_path(get_env_safe("SENTINEL_SESSION_LOG"))
    if session_path is None:
        return None
    start, end = window
    size = end - start
    if size < 0:
        return None
    # The guard covers the whole extraction, not just the read: a stream that was
    # there but could not be sliced, decoded or cut is exactly the `error` status
    # the caller publishes. Nothing here may propagate — it would cost the event.
    try:
        # Each slice is cleaned separately, and only the end the mode needs is read.
        # Concatenating the raw head and tail first was wrong twice over:
        #   (a) the head ends at an arbitrary byte, so it routinely ends inside an OSC/CSI,
        #       and the terminated-OSC branch then ran from that dangling introducer to the
        #       first BEL in the tail, deleting an unbounded run of genuine output. Cleaned
        #       apart, each introducer is terminal to its own buffer;
        #   (b) cleaning shrinks the head, so a `head`/`tail` cut of the concatenation could
        #       glue two non-contiguous ranges together with no seam at all.
        # `already_cut` is set by the `both` branch, which cuts itself: re-cutting
        # a field that carries a seam marker re-splits the marker.
        already_cut = False
        with open(session_path, "rb") as stream:
            if size <= 2 * cap:
                stream.seek(start)
                text = clean(stream.read(size))
                sliced = False
            elif mode == "tail":
                stream.seek(end - cap)
                text = clean(stream.read(cap))
                sliced = True
            elif mode == "both":
                # The whole `both` cut happens here and the result is final;
                # `already_cut` suppresses the downstream `truncate_text`. Splicing first and
                # cutting after cut the field twice, slicing through the marker just
                # inserted: a fragment of it was published as if the terminal had printed it,
                # followed by a second marker whose count described the spliced string rather
                # than the window -- on the shipped defaults, every window over 8KB. So cut
                # each slice to its own half of the budget, then splice, and emit one marker
                # carrying the real count.
                marker_upper = len(TRUNCATION_MARKER_FMT.format(dropped=size).encode("utf-8"))
                budget = cap - marker_upper
                if budget > 0:
                    half = budget // 2                  # floor half to the head...
                    tail_len = budget - half            # ...remainder to the tail
                    # Redact each slice before the cut, while it is still whole:
                    # the cap must be measured on what is published, and
                    # `<REDACTED>` is longer than the shortest value it replaces,
                    # so redacting after the cut could push the field back over the
                    # cap. A value cannot straddle the two slices — they are
                    # non-contiguous ranges of the stream.
                    stream.seek(start)
                    head_enc = redact_values(clean(stream.read(cap)), secrets).encode("utf-8")
                    stream.seek(end - cap)
                    tail_enc = redact_values(clean(stream.read(cap)), secrets).encode("utf-8")
                    # The byte cut can split a `<REDACTED>` marker; the fragment
                    # is trimmed rather than published as terminal output.
                    head_txt = _trim_split_marker_suffix(
                        head_enc[:half].decode("utf-8", "ignore"),
                        head_enc.decode("utf-8", "ignore"))
                    tail_txt = _trim_split_marker_prefix(
                        tail_enc[max(len(tail_enc) - tail_len, 0):].decode("utf-8", "ignore"),
                        tail_enc.decode("utf-8", "ignore"))
                    # Raw window size minus the two CLEANED slices, so it
                    # over-reports by whatever cleaning removed. Kept raw-anchored so
                    # it agrees with `output_bytes`, the number a consumer
                    # correlates against.
                    dropped = size - len(head_txt.encode("utf-8")) - len(tail_txt.encode("utf-8"))
                    text = head_txt + TRUNCATION_MARKER_FMT.format(dropped=dropped) + tail_txt
                    already_cut = True
                else:
                    # The cap cannot even hold the seam marker: leave the cut to
                    # `truncate_text_offsets`, which degrades to `head` for the same
                    # case. Emitting the marker alone would blow the cap.
                    stream.seek(start)
                    text = clean(stream.read(cap))
                sliced = True
            else:
                # `head`, and any unrecognised mode — the same fallback
                # `truncate_text_offsets` applies.
                stream.seek(start)
                text = clean(stream.read(cap))
                sliced = True

        # `clean` decodes with the REPLACING error handler, so binary output
        # yields a lossy but valid string instead of an exception. The runner's raw
        # artifact keeps the original bytes: the two destinations have different
        # jobs, so making both lossy or both exact would be wrong either way.
        # Mask after cleaning (a colour change mid-token splits the value in the raw stream;
        # only the cleaned text has it whole) and before the cut (the cap must be measured on
        # what is published).
        # Best effort: it cannot mask a secret that was never an environment
        # variable, one derived at runtime, or one rendered across a line wrap. The
        # only complete control is log_output.enabled: false, as the security page
        # says. The raw artifact is deliberately NOT redacted.
        if already_cut:
            # `both` already cleaned, redacted, cut and seamed each slice: handing
            # the result to `truncate_text` would cut through its marker.
            truncated = True
        else:
            redacted = redact_values(text, secrets)
            text, truncated, _total = truncate_text(redacted, cap, mode)
    except Exception:
        return None  # Unreadable/unsliceable stream -> `error`, never a dropped event

    return text, bool(truncated or sliced), size


# --------------------------------------------------------------------------
# Operator-supplied metadata and tags (EXEGOL_SENTINEL_META / _TAGS)
#
# No try/except below, deliberately, in a file that is defensive everywhere else: `split`,
# `strip` and `partition` are total over any `str` and get_env_safe always returns one, so a
# handler would be unreachable code implying a failure mode that does not exist. Malformed
# input degrades to fewer entries instead, which keeps a typo in an exported variable from
# costing the audit event. get_env_safe decodes the whole variable as one string, so a single
# non-UTF-8 byte collapses EXEGOL_SENTINEL_TAGS to one tag holding the marker, and yields no
# key at all for EXEGOL_SENTINEL_META (the marker contains no `=`).
# --------------------------------------------------------------------------


def _split_user_elements(raw: str) -> List[str]:
    """Comma-split an operator variable: strip each element, drop empty ones.

    One rule, so `a,,b`, a trailing comma and stray spaces are harmless.
    """
    return [element.strip() for element in raw.split(",") if element.strip()]


def _parse_user_tags(raw: str) -> List[str]:
    """The split result as-is: no de-duplication, order exactly as typed."""
    return _split_user_elements(raw)


def _parse_user_metadata(raw: str) -> dict[str, str]:
    """Parse `k=v` elements into a string->string map.

    Split on the FIRST `=` only, so a value may contain `=`. An element with no
    `=`, or an empty key, is dropped; an empty VALUE is kept (`k=` maps `k` to the
    empty string) — a deliberately blank key is not a malformed element. A repeated
    key keeps the last occurrence.
    """
    metadata: dict[str, str] = {}
    for element in _split_user_elements(raw):
        key, separator, value = element.partition("=")
        if not separator:
            continue
        key = key.strip()
        if not key:
            continue
        metadata[key] = value.strip()
    return metadata


def main() -> int:
    # Get artifact ID from env or generate new one
    artifact_id = get_env_safe("ARTIFACT_ID")
    if not artifact_id:
        artifact_id = uuid.uuid4().hex

    # Define artifact directory
    artifacts_dir = LOG_DIR / "artifacts" / artifact_id

    # Locate this command's byte range first: both the inline field read below and
    # the detached runner's environment need it, and the runner inherits its
    # environment once, so there is no hook after the spawn.
    _located = _locate_output_window(artifact_id)
    output_window = (_located[0], _located[1]) if _located else None
    output_floor = bool(_located[2]) if _located else False

    # Récupération des champs transmis par zsh
    hostname = get_env_safe("HOSTNAME")
    container_name = get_env_safe("EXEGOL_NAME", hostname)
    cwd = get_env_safe("LOG_CWD")
    shell_type = get_env_safe("LOG_SHELL_TYPE")
    command_raw = get_env_safe("LOG_COMMAND_RAW")
    command = get_env_safe("LOG_COMMAND")

    start_time = get_env_safe("LOG_START_TIME")
    end_time = get_env_safe("LOG_END_TIME")

    exit_code_str = get_env_safe("LOG_EXIT_CODE", "")
    try:
        exit_code = int(exit_code_str) if exit_code_str else None
    except ValueError:
        exit_code = None

    # Backup datetime
    if not start_time:
        # Strip tzinfo so isoformat() does not emit "+00:00" before the "Z" designator.
        start_time = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"
    if not end_time:
        end_time = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"
    # Read rotation config and env_redact in one pass; null nodes are coalesced to {} / [].
    rotation_cfg: dict = {}
    env_redact: list = []
    log_output_cfg: dict = {}
    sentinel_cfg_path = LOG_DIR / "sentinel_config.json"
    if sentinel_cfg_path.exists():
        try:
            with sentinel_cfg_path.open("r", encoding="utf-8") as f:
                _sc = json.load(f)
            _cfg = (_sc.get("profile") or {}).get("config") or {}
            # A SCALAR IS NOT AN EMPTY SECTION: `or {}` rescues None and {} only, so
            # `"log_rotation": true` reaches .get() as an AttributeError — caught for
            # this read, but not for the USE, where it escapes main() and every
            # command prints a traceback and writes no event. Check the type where
            # the value is extracted.
            _lr = _cfg.get("log_rotation")
            rotation_cfg = _lr if isinstance(_lr, dict) else {}
            _er = _cfg.get("env_redact")
            env_redact = _er if isinstance(_er, list) else []
            _lo = _cfg.get("log_output")
            log_output_cfg = _lo if isinstance(_lo, dict) else {}
        except Exception:
            rotation_cfg = {}   # Defensive: missing/malformed config -> fallback to default
            env_redact = []     # No masking when config is missing/unreadable
            log_output_cfg = {} # No inline output when config is missing/unreadable

    # Expand with env_redact so a secret pulled in via a variable is masked in
    # BOTH resolved_command and envs_in_command, not just the latter.
    full_cmd, env_vars, redacted_values = expand_env_vars_safe(command_raw, env_redact)
    # Masking captured OUTPUT needs the whole env_redact-matching set, not just what
    # this command line referenced: `env` and friends print secrets they never name.
    # The command line keeps using `redacted_values` alone — substituting a value
    # the operator never typed would corrupt the record of what they ran.
    output_secrets = sorted(set(redacted_values) | set(redact_candidates(env_redact)))
    # Inline terminal output. Additive fields, so schema_version stays 1. The
    # presence matrix has four rows and no nulls anywhere:
    #
    #   disabled by config    -> none of the four keys
    #   window found          -> output + output_truncated + output_bytes, no status
    #   no window             -> output_status: unavailable, and NO byte count
    #   extraction failed     -> output_status: error
    #
    # Absence is the signal, like artifact_id below: a parser reads a missing key,
    # never a null, which would be a third state no consumer was told about.
    # An empty window is NOT a failure — output redirected to a file printed
    # nothing on the terminal, which is the empty string with a zero byte count.
    # No field announces that an output_capture artifact was written: artifact_id
    # is the link. The runner is detached, so a flag set here could only report an
    # intention.
    output_fields: dict = {}
    # `is True`, not truthiness: nothing re-validates the deployed config in the container,
    # and a hand-edit or YAML-to-JSON round-trip produces `"enabled": "false"` -- a truthy
    # string that reads as a disable. spawn.sh's recorder gate had the same shape, so both
    # agreed and the failure was invisible: the recorder ran and every event carried
    # `output`. `log_output.enabled: false` is the only complete control against a client's
    # secrets reaching their SIEM, so a silently ignored disable is a privacy defect:
    # anything that is not a real bool falls back to the disable.
    if log_output_cfg.get("enabled") is True:
        if output_window is None:
            # Recorder inactive, program opened its own pty, no `script` in the
            # image, or no marker pair. No byte count is guessed: it comes from the
            # two marker offsets, and with fewer there is no honest number.
            output_fields["output_status"] = OUTPUT_STATUS_UNAVAILABLE
        else:
            # Coerced, not trusted: nothing re-validates the deployed config in the
            # container. An untyped `max_size` does not degrade, it detonates -- a str
            # survives `2 * cap` and raises on the comparison -- and _read_output_field's
            # blanket handler turns that into `output_status: "error"` on every event of that
            # container, with no message saying why. "4KB" makes it reachable, being the
            # spelling UserConfig ships. A bad value falls back to the shipped default rather
            # than disabling the field: the operator asked for output, and a silently capped
            # field beats `error`. 0 is rejected with the negatives.
            _raw_cap = log_output_cfg.get("max_size", DEFAULT_OUTPUT_MAX_SIZE)
            _cap = (_raw_cap if isinstance(_raw_cap, int) and not isinstance(_raw_cap, bool)
                    and _raw_cap > 0 else DEFAULT_OUTPUT_MAX_SIZE)
            _raw_mode = log_output_cfg.get("truncation", DEFAULT_OUTPUT_TRUNCATION)
            _mode = _raw_mode if _raw_mode in ("head", "tail", "both") else DEFAULT_OUTPUT_TRUNCATION
            _field = _read_output_field(
                output_window,
                _cap,
                _mode,
                output_secrets,
            )
            if _field is None:
                # The stream was there and extraction failed: a different fact from
                # `unavailable`, and the word the manifest uses for it.
                output_fields["output_status"] = OUTPUT_STATUS_ERROR
            else:
                (output_fields["output"],
                 output_fields["output_truncated"],
                 output_fields["output_bytes"]) = _field

    # Launch the POST_EXEC actions DETACHED, in their own session, so the runner
    # survives this already-backgrounded logger and can run unlimited-timeout
    # exec_command actions. It is never waited on: the audit event must not be
    # delayed or dropped by a long action (see RUNNER_HEADSTART_SEC below).
    #
    # The spawn is last, after the inline field has been read. The runner punches a hole over
    # [start, end) on every POST_EXEC path -- precisely the bytes the inline read consumes --
    # and nothing serialises the two. Spawned first, whoever won the race decided whether the
    # event carried any output: a punched hole reads back as NUL bytes, `_CTRL_RE` strips
    # them, and the event came out with `output: ""` and a true `output_bytes`,
    # indistinguishable from the "printed nothing" row of the presence matrix.
    #
    # The ordering costs nothing: everything the read needs is already known here,
    # and the runner's start is delayed by a bounded amount.
    # The window scan must also stay above the spawn — the runner is detached and
    # inherits its environment once, so there is no env hook afterwards, and having
    # it locate the markers itself would re-couple the event to the runner.
    runner_proc = None
    try:
        runner_proc = subprocess.Popen(
            ["/.exegol/sentinel/sentinel_runner.py", "POST_EXEC", artifact_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            # Empty when there is no window: the runner reads "" as absent and
            # writes an unavailable manifest rather than guessing an offset. The
            # SENTINEL_ prefix keeps these out of every exec_command child.
            env={**os.environ,
                 "SENTINEL_OUT_START": str(output_window[0]) if output_window else "",
                 "SENTINEL_OUT_END": str(output_window[1]) if output_window else "",
                 # The start is a proven lower bound, not the real start: the runner
                 # must publish that, or the artifact reads as a complete capture.
                 "SENTINEL_OUT_FLOOR": "1" if output_floor else ""},
        )
    except Exception as e:
        sys.stderr.write(f"[command_logger] Failed to launch sentinel profile actions: {e}\n")

    if not LOG_DIR.is_dir():
        try:
            # Private (0o700): the captured cmdline/env must not be group- or
            # world-readable inside the container.
            LOG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        except Exception as e:
            # In case of any error, write only to stderr
            sys.stderr.write(f"[command_logger] Failed to create log dir {LOG_DIR}: {e}\n")
            return 1

    # Annotated `dict` rather than inferred: the event is heterogeneous by
    # construction, and an inferred union from this literal rejects every later
    # assignment of a shape it does not already contain.
    event: dict = {
        "start_time": start_time,
        "end_time": end_time,
        "hostname": hostname,
        "container_name": container_name,
        "working_directory": cwd,
        "shell": shell_type,
        "user_command": command,
        "resolved_command": full_cmd,
        "envs_in_command": env_vars,
        "exit_code": exit_code,
        "event_id": uuid.uuid4().hex,
        "schema_version": 1,
    }

    # Merged rather than assigned key by key, so the read can happen before the
    # runner exists while the four output* keys keep their published position
    # after `schema_version`.
    event.update(output_fields)

    # Operator-supplied engagement context, read here rather than earlier so the
    # two keys land in the published order: after the output* block, before
    # artifact_id. Moving this read would silently reorder the written line.
    # Guarded so an empty result writes NO key: absence is the signal here as it is
    # for output* and artifact_id — never a null, never an empty container.
    # Nested, not flat, and that is the whole collision defence: the operator picks these key
    # names, so a flat merge would let one named `exit_code` displace a schema field. Under
    # `metadata` it is a metadata key and nothing else, which is why no reserved-key list
    # exists here. Deliberately not passed through env_redact: the operator chooses what goes
    # in them, so a secret pasted into EXEGOL_SENTINEL_META reaches the SIEM verbatim on every
    # event -- published on the security page rather than mitigated here.
    # schema_version is not bumped: both keys are additive.
    user_metadata = _parse_user_metadata(get_env_safe("EXEGOL_SENTINEL_META"))
    if user_metadata:
        event["metadata"] = user_metadata
    user_tags = _parse_user_tags(get_env_safe("EXEGOL_SENTINEL_TAGS"))
    if user_tags:
        event["tags"] = user_tags

    # Brief head start so the common case links artifact_id: the runner creates its
    # artifact dir near-instantly when an action triggers. Still running (a long
    # exec_command) means the event is written anyway; it finishes on its own.
    if runner_proc is not None:
        try:
            runner_proc.wait(timeout=RUNNER_HEADSTART_SEC)
        except subprocess.TimeoutExpired:
            pass
    if artifacts_dir.is_dir():
        event["artifact_id"] = artifact_id

    # ensure_ascii=False keeps non-ASCII output readable instead of exploding into
    # \uXXXX escapes. The cap bounds the PAYLOAD, not the JSON-escaped line: a
    # window full of quotes can serialise somewhat longer than max_size.
    line = json.dumps(event, ensure_ascii=False) + "\n"
    try:
        _write_event_locked(line, rotation_cfg)
    except Exception as e:
        # In case of any error, write-only to stderr
        sys.stderr.write(f"[command_logger] Failed to write log to {LOG_FILE}: {e}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
