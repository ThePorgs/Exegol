"""Shared terminal-output helpers for the in-container Sentinel scripts.

Stdlib only: deployed inside the Exegol image next to ``sentinel_logger.py`` and
``sentinel_runner.py``, which are self-contained scripts with no site-packages.

Everything here is shared by the inline event field and the ``output_capture``
artifact, so the two destinations can never disagree:

* the marker protocol the shell hooks print around every command,
* locating one command's window inside the session stream,
* turning raw pty bytes into the text a human saw, and cutting it to a size cap
  on a character boundary,
* releasing the blocks behind a window the runner has finished with, so a loud
  command stops holding them,
* masking the values the profile asked to hide, in the inline field only.
"""

import ctypes
import ctypes.util
import os
import re
import stat
from typing import Any, IO, Iterable, List, NamedTuple, Optional, Tuple, Union

# Private OSC number for the window markers. A terminal silently discards an OSC
# number it does not know, and 5379 is adjacent to nothing in use, so nothing is
# ever drawn for it. OSC 133 was rejected for the opposite reason: VS Code, kitty,
# WezTerm and foot all render visible prompt decorations from it.
MARKER_OSC = 5379

# Terminated with BEL (0x07) rather than ST (ESC backslash): BEL is a single byte,
# so a partial write cannot split the terminator and leave a half-marker behind.
MARKER_BEL = "\x07"

# The reference form of a marker: a kind (``s``/``e``) and a 32-hex artifact id,
# anchored so the scan cannot match user data by accident. Bytes, not str — the
# session stream is raw pty output, scanned before any decode. find_window matches
# the literal bytes format_marker produces; this pattern is what the test suite
# holds the hooks, format_marker and the scan to.
MARKER_RE = re.compile(rb"\x1b\]" + str(MARKER_OSC).encode("ascii") + rb";([se]);([0-9a-f]{32})\x07")

# Backward-scan tuning. The chunk is the read granularity; each limit bounds a
# different walk of find_window, and they must not be conflated (see below).
SCAN_CHUNK = 64 * 1024

# Walk 1, EOF -> END MARKER. The distance is whatever OTHER commands appended
# after ours, so it is a property of the session FILE and must be bounded to keep
# the event's cost O(scan window) instead of O(session file).
# It is also a published cause of `output_status: unavailable`: when more than this
# is appended between the end-marker printf and the backgrounded logger's scan (a
# `&`-backgrounded producer still writing to the tty), the marker is never reached.
SCAN_LIMIT = 4 * 1024 * 1024

# Walk 2, end marker -> start marker. This distance is the command's own output, so bounding it
# by SCAN_LIMIT bounded no cost and instead capped the whole feature at a 4 MiB window:
# anything louder (`nmap -A` on a /24, `ffuf`, `find / -ls`) was silently reported
# `unavailable`, got no artifact, and never had its bytes released. Reaching this walk means
# the end marker was found, so the command really did print that much; the bound is kept only
# for the degenerate case of a start marker missing entirely (punched away, hook never fired).
# A larger window is still refused, and that ceiling is published.
WINDOW_SCAN_LIMIT = 512 * 1024 * 1024

# Walk 3, our start marker -> the previous command's end marker: the inter-window filler (see
# find_filler_start). Its own constant, far larger than SCAN_LIMIT, because this budget is a
# ceiling and not a cost: _rscan stops at the first match and the distance it walks is the
# filler, so a quiet prompt costs one chunk whatever the number is, and it only decides how
# large a filler is still worth reclaiming. 4 MiB is about 130 full-screen repaints — one long
# fuzzy-finder search passes it — so 256 MiB, still far short of walking a session file.
FILLER_SCAN_LIMIT = 256 * 1024 * 1024

# Escape-sequence stripper. The branch order is load-bearing: the two-character
# ``ESC X`` branch must stay after the CSI/OSC/DCS branches, or it matches the
# ``ESC ]`` that opens every OSC and leaves the payload as visible text (an OSC
# title would surface as "0;root@exegol" in the audit event).
_ANSI_RE = re.compile(
    r"""(?x)
    \x1b \[ [0-?]* [ -/]* [@-~]          # CSI ... final byte
    # Bounded and newline-excluded, like the \Z-anchored twins below. As `.*?`
    # under re.S, one stray `ESC ]`/`ESC P` plus any later BEL silently deleted
    # everything in between — and both introducers and BEL are routine in what this
    # records (hexdump, strings, `cat` of a binary). An OSC/DCS payload is one line
    # by construction, so a newline means the sequence is already over; {0,512}
    # bounds a single line of binary. Past either bound the branch fails and we leak
    # the introducer instead of deleting the output after it.
  | \x1b \] (?: [^\x07\x1b\r\n] | \x1b (?![@-_]) ){0,512} (?: \x07 | \x1b\\ )
    # BEL is excluded from the payload: it is one of this branch's own terminators,
    # and a greedy `{0,512}` over it ran to the LAST BEL on the line —
    # `clean(b"\x1bP\x07REAL OUTPUT\x07tail")` returned "tail".
  | \x1b [P^_] [^\x07\x1b\r\n]{0,512} (?: \x1b\\ | \x07 )
    # Unterminated sequences at the end of the buffer: a window boundary or a
    # head/tail slice lands inside an escape routinely for colour-heavy output.
    # Without these the payload surfaces as visible text in the event. \Z-anchored,
    # so a sequence terminated later is still taken by the branches above.
    # CSI fires constantly: `ESC [` (0x5B) falls in the gap between the two-char
    # branch's ranges, so a dangling SGR matched nothing and `clean(b"hello\x1b[31")`
    # returned "hello[31".
  | \x1b \[ [0-?]* [ -/]* \Z              # unterminated CSI at end of buffer
    # The payload tolerates a raw ESC (a title may carry one) but ONLY one that
    # begins nothing: `(?![@-_])` excludes every byte that would make `ESC X` an
    # introducer. A plain `[^\x07]*` ran over embedded escapes and newlines to \Z,
    # so one stray `ESC ]` mid-stream deleted every byte after it from the event.
    # `\r`/`\n` are excluded for the case the ESC test cannot see: plain binary with
    # no escape and no BEL. {0,512} bounds the rest.
    # Past any of those the branch fails and the two-char branch leaks the
    # introducer — deliberate: a visible leak is recoverable by a human, a silent
    # deletion is not.
  | \x1b \] (?: [^\x07\x1b\r\n] | \x1b (?![@-_]) ){0,512} \Z  # unterminated OSC
    # Bounded and newline-excluded like its terminated twin, and not optional:
    # `ESC P junk \n real BEL after` would otherwise fall through to here and match
    # to \Z. BEL is excluded too — a payload containing one is a terminated DCS.
  | \x1b [P^_] [^\x07\x1b\r\n]{0,512} \Z    # unterminated DCS / PM / APC at end
  | \x1b [@-Z\\-_]                       # two-char ESC sequences (MUST stay last)
    # `[!-/]` is `[ -/]` WITHOUT space, and the run is bounded. Starting at 0x20
    # with a greedy `+`, a stray ESC before indentation ate the indentation and the
    # first real character — `clean(b"A\x1b     hello world")` returned "Aello
    # world". A real intermediate run is one or two bytes, so {1,4} costs nothing.
    # The residual is a leak (`ESC SP F` surfaces as " F"), the direction taken
    # everywhere here.
  | \x1b [!-/]{1,4} [0-~]                # ESC intermediate + final (e.g. ESC ( B)
    """,
    re.S,
)

# Residual control characters, once the escape sequences are gone. \t (0x09),
# \n (0x0a) and \r (0x0d) are deliberately absent: \r is consumed by the
# overwrite simulation below and the other two are legitimate layout.
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Inserted between the head and the tail of a "both"-mode TEXT cut, and charged to
# the budget: it is extra bytes on top of the two slices, so the cap must be
# reduced by its length or the payload exceeds it. Never written into a RAW cut —
# it would corrupt the stream, so a raw seam is manifest offsets and nothing else.
TRUNCATION_MARKER_FMT = "\n[... {dropped} bytes truncated ...]\n"

# Shared by the output_capture manifest's `status` and the audit event's
# `output_status`, so the two destinations cannot drift apart.
# `unavailable`: nothing to copy (recorder inactive, program opened its own pty, no
# `script` in the image, no marker pair). `error`: the stream was there and
# extraction failed. Without the distinction, a missing output file is
# indistinguishable from a command that printed nothing.
OUTPUT_STATUS_OK = "ok"
OUTPUT_STATUS_UNAVAILABLE = "unavailable"
OUTPUT_STATUS_ERROR = "error"


# The published marker for a value the profile asked to hide — angle brackets, the
# form the docs tell a SIEM operator to allowlist. Aliased by
# `sentinel_logger.expand_env_vars_safe` and `sentinel_runner.REDACTED`, so the
# command line, the env dump and the captured output cannot announce it differently.
REDACTED_MARKER = "<REDACTED>"

# Shorter values are NOT substituted in captured output: a one- or two-character
# value occurs by chance almost anywhere, so masking it would pepper the field with
# markers and destroy the evidence while protecting nothing. The command line still
# masks every listed value whatever its length — that substitution is bounded to
# variables the operator actually typed.
REDACT_MIN_VALUE_LEN = 4


class CutPlan(NamedTuple):
    """Which byte ranges of a window survive a cut, and the manifest offsets.

    Keeping the arithmetic separate from the data lets the runner copy any window
    find_window can locate — up to WINDOW_SCAN_LIMIT — without materialising it:
    it reads only ``ranges`` and seeks to each.
    """
    ranges: List[Tuple[int, int]]
    truncated: bool
    bytes_total: int
    truncated_at_byte: int
    tail_from_byte: Optional[int]


class TextCut(NamedTuple):
    """``truncate_text_offsets`` result: the text plus the manifest's offset fields."""
    text: str
    truncated: bool
    bytes_total: int
    truncated_at_byte: int
    tail_from_byte: Optional[int]


# The one directory a session stream may live in. spawn.sh creates it 0700 and
# refuses to follow a symlink at that path, so "inside this directory" is a real
# property, not a naming convention.
# A literal, never an environment override: the hooks already resolve the path from the
# exec-time environment of the shell and its ancestors, and this confinement is the second,
# independent layer, so a value reaching open() or punch_hole() by any route can still never
# name logs.json or an artifact.
SESSION_DIR = "/tmp/.sentinel"


def validated_session_path(path: Optional[str]) -> Optional[str]:
    """Return ``path`` resolved, or ``None`` if it is not a real session stream.

    Three checks, each load-bearing:

    * **resolved containment in :data:`SESSION_DIR`** -- ``realpath`` first, so a
      symlink inside the directory cannot point outside it. Compared
      component-wise, not with ``startswith``, or ``/tmp/.sentinel-evil`` passes;
    * **a regular file** -- a fifo or device would block the reader, or make
      ``punch_hole`` operate on something that is not a stream;
    * **owned by us** -- a stream owned by anyone else is not the one ``spawn.sh``
      created.

    The file mode is not checked: the directory is 0700, so no other user can put a file
    there, and anyone who could plant a 0644 file could plant a 0600 one.

    This bounds where the feature reads and punches; it does not authenticate what it reads.
    The hooks resolve the path from the exec-time environment of the shell and its ancestors
    and hold it in a readonly parameter, so no ``unset``/``export``/assignment can redirect
    the logger. The operator is still inside the mechanism, though: the marker id is a
    readable shell parameter, so a command can print a forged marker pair around text of its
    choosing and nothing downstream can tell it from a real capture, and markers appended to
    another shell's stream in the same directory make the runner zero a chosen byte range of
    it. Closing that needs the nonce to stop being printable from the user's shell — a design
    change, not a validation. The security page documents it; keep the two in step.
    """
    if not path:
        return None
    try:
        real = os.path.realpath(path)
        root = os.path.realpath(SESSION_DIR)
        if real != root and not real.startswith(root + os.sep):
            return None
        info = os.stat(real)
        if not stat.S_ISREG(info.st_mode):
            return None
        if info.st_uid != os.geteuid():
            return None
        return real
    except OSError:
        return None


def format_marker(kind: str, artifact_id: str) -> str:
    """Return the exact marker string the shell hooks ``printf``.

    ``kind`` is ``"s"``/``"start"`` or ``"e"``/``"end"``. The returned string is
    the single source of truth for the byte sequence: ``bash_hooks.sh`` and
    ``zsh_hooks.sh`` carry the same literal in their ``printf`` format strings
    and ``test_output_cleaning.py`` asserts the two forms match. A one-byte
    divergence between the hooks and ``MARKER_RE`` makes every window
    unavailable, silently and completely.
    """
    letter = kind[0].lower()
    if letter not in ("s", "e"):
        raise ValueError(f"invalid marker kind {kind!r}: expected 'start'/'s' or 'end'/'e'")
    return f"\x1b]{MARKER_OSC};{letter};{artifact_id}{MARKER_BEL}"


def clean(data: bytes) -> str:
    """Turn raw pty bytes into the text the operator actually saw.

    Strip escape sequences, then simulate ``\\r`` so an overwritten line collapses
    to its final frame (a progress bar becomes ``100% done``). Not terminal
    emulation: no cursor addressing, no scroll region. Overwritten frames survive
    in the raw artifact, never here.

    Decoding is lossy on purpose: a command that printed binary must not cost us
    the audit event.
    """
    text = data.decode("utf-8", "replace")
    text = _ANSI_RE.sub("", text)
    # Order is load-bearing. A pty applies ONLCR, so every displayed line ends
    # "\r\n": collapsing lone carriage returns first leaves "text\r", whose last
    # \r-segment is empty, and every line of every capture is silently deleted.
    # Normalise CRLF first.
    text = text.replace("\r\n", "\n")
    return "\n".join(_CTRL_RE.sub("", line.split("\r")[-1]) for line in text.split("\n"))


def redact_values(text: str, values: Iterable[str]) -> str:
    """Replace each of ``values`` by :data:`REDACTED_MARKER` in ``text``.

    A literal substitution, longest value first so a secret that CONTAINS another
    is masked whole rather than left as ``<REDACTED>456``. Values shorter than
    :data:`REDACT_MIN_VALUE_LEN` are skipped.

    Applied to the inline event field only: the event is ingested by a SIEM, the
    raw artifact is evidence and keeps the bytes the terminal produced.

    Best effort by nature — it cannot mask a secret that was never an environment
    variable, one derived at runtime, or one rendered across a line wrap. The only
    complete control is ``log_output.enabled: false``.
    """
    if not text:
        return text
    # Deduplicate, drop the too-short, and take the longest first.
    candidates = sorted({v for v in values if v and len(v) >= REDACT_MIN_VALUE_LEN},
                        key=len, reverse=True)
    for value in candidates:
        if value in text:
            text = text.replace(value, REDACTED_MARKER)
    return text


def plan_byte_cut(total: int, cap: Optional[int], mode: str = "head") -> CutPlan:
    """Decide which byte ranges of a ``total``-byte window survive the cap.

    The single definition of the cut arithmetic. The runner applies it to a file
    by seeking, which keeps an unlimited capture off the heap for every window
    find_window can locate.

    This is the ``format: raw`` path: no decoding, no cleaning, and **no seam
    marker** — one inside a raw stream would corrupt it. The seam exists only as
    the returned offsets, so the manifest is the sole way to read a truncated raw
    artifact.

    Reconstruction identity, held by every mode here and by
    :func:`truncate_text_offsets`::

        truncated_at_byte + (bytes_total - tail_from_byte) + marker_len == bytes_written

    where ``tail_from_byte`` defaults to ``bytes_total`` when absent and
    ``marker_len`` is zero for raw and for the ``head`` and ``tail`` modes.

    The comparison is strictly greater-than: a window of exactly ``cap`` bytes is
    complete, not truncated. A manifest that claims truncation for a complete
    artifact is the one error a consumer cannot detect.

    ``cap`` of ``None`` (or a non-positive value) means unlimited.
    """
    if cap is None or cap <= 0 or total <= cap:
        # tail_from_byte is None because nothing was dropped: the identity above
        # then reads total + 0 + 0 == total.
        return CutPlan([(0, total)], False, total, total, None)
    if mode == "tail":
        return CutPlan([(total - cap, total)], True, total, 0, total - cap)
    if mode == "both":
        head_len = cap // 2                 # floor half to the head...
        tail_len = cap - head_len           # ...remainder to the tail
        ranges = [(0, head_len), (total - tail_len, total)]
        return CutPlan([r for r in ranges if r[1] > r[0]], True, total, head_len, total - tail_len)
    # head, and any unknown mode: the profile's own default keeps the beginning.
    return CutPlan([(0, cap)], True, total, cap, None)


def truncate_text_offsets(text: str, cap: Optional[int], mode: str = "both") -> TextCut:
    """Cut ``text`` to ``cap`` bytes of UTF-8, with the same offsets as :func:`plan_byte_cut`.

    The cut is taken on ENCODED bytes and decoded back with ``errors="ignore"``:
    a multi-byte character split by the cut is dropped cleanly. ``"replace"``
    would insert a 3-byte U+FFFD instead and push the payload PAST the cap --
    the opposite of what a cap is for.

    Because that drop shortens the kept slices, the returned offsets are
    measured on what SURVIVED rather than on what was sliced, so the
    reconstruction identity documented in :func:`plan_byte_cut` still holds
    exactly.
    """
    encoded = text.encode("utf-8")
    total = len(encoded)
    if cap is None or cap <= 0 or total <= cap:
        return TextCut(text, False, total, total, None)

    if mode == "tail":
        cut = encoded[total - cap:].decode("utf-8", "ignore")
        kept = len(cut.encode("utf-8"))
        return TextCut(cut, True, total, 0, total - kept)

    if mode == "both":
        # Charge the marker to the budget, one pass, no iteration: the omitted
        # count can never exceed the total and therefore never has more decimal
        # digits, so rendering the marker with `total` is an upper bound on its
        # length. budget + marker_upper == cap by construction.
        marker_upper = len(TRUNCATION_MARKER_FMT.format(dropped=total).encode("utf-8"))
        budget = cap - marker_upper
        if budget > 0:
            half = budget // 2
            tail_len = budget - half
            head_txt = encoded[:half].decode("utf-8", "ignore")
            tail_txt = encoded[total - tail_len:].decode("utf-8", "ignore")
            head_kept = len(head_txt.encode("utf-8"))
            tail_kept = len(tail_txt.encode("utf-8"))
            marker = TRUNCATION_MARKER_FMT.format(dropped=total - head_kept - tail_kept)
            return TextCut(head_txt + marker + tail_txt, True, total,
                           head_kept, total - tail_kept)
        # The cap cannot even hold the seam marker. Degrading to `head` keeps the
        # payload inside the cap; emitting the marker anyway would blow it.

    cut = encoded[:cap].decode("utf-8", "ignore")
    return TextCut(cut, True, total, len(cut.encode("utf-8")), None)


def truncate_text(text: str, cap: Optional[int], mode: str = "both") -> Tuple[str, bool, int]:
    """``(cut, truncated, total)`` -- the three-value shape ``sentinel_logger`` unpacks.

    A thin projection of :func:`truncate_text_offsets`, not a second
    implementation. The offsets are not appended: the logger unpacks exactly three
    values.
    """
    result = truncate_text_offsets(text, cap, mode)
    return result.text, result.truncated, result.bytes_total


def _as_bytes(artifact_id: Union[str, bytes]) -> bytes:
    return artifact_id if isinstance(artifact_id, bytes) else artifact_id.encode("ascii", "ignore")


def _rscan(fh: IO[bytes], end_pos: int, marker: bytes, scan_limit: int, chunk: int) -> Optional[Tuple[int, int]]:
    """Return ``(start, end)`` offsets of the LAST ``marker`` ending at or before ``end_pos``.

    Walks backwards in ``chunk``-sized steps, reading ``len(marker) - 1`` extra
    bytes past the top of each step so a marker straddling a step boundary is
    still complete in the buffer. Without that overlap the scan misses markers
    INTERMITTENTLY, depending only on where the command landed in the stream --
    the worst failure mode this module could have.

    Returns ``None`` once ``scan_limit`` bytes have been walked, so the caller
    reports "no window" rather than reading the whole session file.
    """
    mlen = len(marker)
    overlap = mlen - 1
    pos = end_pos
    walked = 0
    while pos > 0 and walked < scan_limit:
        step = min(chunk, pos)
        start = pos - step
        # Never read past end_pos: a marker that lies beyond the caller's bound
        # (e.g. an end marker after the one we already matched) must not match.
        read_end = min(end_pos, pos + overlap)
        fh.seek(start)
        buf = fh.read(read_end - start)
        idx = buf.rfind(marker)
        if idx != -1:
            abs_start = start + idx
            return abs_start, abs_start + mlen
        walked += step
        pos = start
    return None


# The END marker's fixed prefix, and the fixed total length of any marker. Both
# are derived from MARKER_OSC/format_marker rather than spelled out, so the
# hooks, MARKER_RE and this scan cannot drift apart independently.
END_MARKER_PREFIX = f"\x1b]{MARKER_OSC};e;".encode("ascii")
MARKER_LEN = len(format_marker("e", "0" * 32).encode("ascii"))


def floor_window(end_offset: int, window_scan_limit: Optional[int] = None) -> Tuple[int, int]:
    """A bounded window ending at ``end_offset`` whose start is a PROVEN LOWER BOUND.

    Used only when the end marker was found and walk 2 gave up. That failure is
    itself the proof the range is ours: commands in one session file are
    sequential and a nested interactive shell writes to its own file, so any other
    command's marker lies further back than the bound just walked. Every byte in
    ``[end - limit, end)`` is this command's own output.

    It is a floor, not a guess — but not a complete capture either, so the caller
    marks the artifact truncated and says the start is a floor.
    """
    limit = WINDOW_SCAN_LIMIT if window_scan_limit is None else window_scan_limit
    return max(0, end_offset - limit), end_offset


def find_filler_start(fh: IO[bytes],
                      before: int,
                      scan_limit: Optional[int] = None,
                      chunk: Optional[int] = None) -> Optional[int]:
    """First byte after the nearest END marker preceding ``before``, or None.

    ``before`` is this command's ``start`` offset, so the range this identifies --
    ``[return value, before)`` -- is the inter-window filler: the prompt, the echoed command
    line and its bracketed-paste wrapper, and every ZLE redraw the operator's typing produced.

    That range is safe to punch by construction: a window is exactly ``[start_i, end_i)``, the
    previous command's window ends at the marker this walks back to, and ours begins at
    ``before``. The previous command's runner may still be chunk-copying its own window when
    the punch lands, and that is fine — the ranges are disjoint. The old ``[0, end]`` punch was
    not, and produced manifests asserting a faithful capture of NUL bytes.

    Matched by literal prefix and then validated against ``MARKER_RE``, so a truncated or
    garbled marker yields None (no punch) rather than an offset inside somebody's data. Any
    artifact id matches: the previous command's identity is irrelevant, only where its window
    ended.

    Bounded by ``FILLER_SCAN_LIMIT``, not ``SCAN_LIMIT`` — see that constant for why a bigger
    number costs nothing here. No marker within it means no punch, so an oversized filler is
    simply not reclaimed. Returns None for the first command of a session too, leaving the
    header alone.
    """
    limit = FILLER_SCAN_LIMIT if scan_limit is None else scan_limit
    step = SCAN_CHUNK if chunk is None else chunk
    hit = _rscan(fh, before, END_MARKER_PREFIX, limit, step)
    if hit is None:
        return None
    prefix_start = hit[0]
    fh.seek(prefix_start)
    if MARKER_RE.fullmatch(fh.read(MARKER_LEN)) is None:
        return None
    filler_start = prefix_start + MARKER_LEN
    return filler_start if filler_start < before else None


def find_window(fh: IO[bytes],
                artifact_id: Union[str, bytes],
                scan_limit: Optional[int] = None,
                chunk: Optional[int] = None,
                window_scan_limit: Optional[int] = None) -> Optional[Tuple[int, int]]:
    """Return the ``(start, end)`` byte offsets of one command's output window.

    ``start`` is the first byte after the ``start`` marker, ``end`` the first
    byte of the ``end`` marker, so the window excludes both markers, the echoed
    command line and its bracketed-paste wrapper (all of which precede the start
    marker in the stream).

    Scans backwards from EOF because the window of the command that just ended is at the end
    of the file. The end marker is matched first, then the last start marker before it: a
    nested shell re-emitting the same artifact id would otherwise widen the window to the
    outer command's whole session.

    The two walks have separate budgets. ``scan_limit`` bounds EOF -> end marker, a distance
    set by what other commands appended; ``window_scan_limit`` bounds end marker -> start
    marker, a distance that is this command's output. Charging the second to the first made
    ``SCAN_LIMIT`` a hard ceiling on the window size the feature could find at all.

    Returns ``None`` when either marker is missing within its bounded scan. The
    caller must treat that as "no window" and never guess a byte offset.
    """
    return scan_window(fh, artifact_id, scan_limit, chunk, window_scan_limit).window


class WindowScan(NamedTuple):
    """``find_window``'s answer plus the ONE fact the caller cannot re-derive.

    ``find_window`` collapses two very different failures into ``None``, and the
    caller's retry policy depends on telling them apart:

    * **the end marker was not found** -- the recoverable one. The hooks print it
      into the pty slave and immediately background the logger, so ``script`` may
      simply not have flushed it yet. It resolves itself, it is bounded by
      ``SCAN_LIMIT`` (4 MiB), and it is cheap to re-ask.
    * **the end marker was found but the start marker was not** -- deterministic.
      The window is larger than ``WINDOW_SCAN_LIMIT``, or the start marker was
      punched away or never emitted. Nothing changes between attempts, and each
      re-ask walks a full 512 MiB for the same answer.
    """
    window: Optional[Tuple[int, int]]
    end_marker_found: bool
    #: Offset of the END marker's first byte whenever it was found, including when
    #: the start marker was not: it is the anchor a floor window is measured back
    #: from, so a command too loud for walk 2 still gets its bytes released and a
    #: truncated artifact instead of nothing.
    end_offset: Optional[int] = None


def scan_window(fh: IO[bytes],
                artifact_id: Union[str, bytes],
                scan_limit: Optional[int] = None,
                chunk: Optional[int] = None,
                window_scan_limit: Optional[int] = None) -> WindowScan:
    """:func:`find_window`, with the outcome distinguished. See :class:`WindowScan`.

    This is the implementation; ``find_window`` is the projection that drops the
    extra field. That way round because only the logger's retry loop needs to know
    WHICH marker was missing.
    """
    limit = SCAN_LIMIT if scan_limit is None else scan_limit
    window_limit = WINDOW_SCAN_LIMIT if window_scan_limit is None else window_scan_limit
    step = SCAN_CHUNK if chunk is None else chunk
    aid = _as_bytes(artifact_id)
    end_marker = format_marker("e", aid.decode("ascii", "ignore")).encode("ascii")
    start_marker = format_marker("s", aid.decode("ascii", "ignore")).encode("ascii")

    size = fh.seek(0, os.SEEK_END)
    end_match = _rscan(fh, size, end_marker, limit, step)
    if end_match is None:
        return WindowScan(None, False, None)
    start_match = _rscan(fh, end_match[0], start_marker, window_limit, step)
    if start_match is None:
        return WindowScan(None, True, end_match[0])
    return WindowScan((start_match[1], end_match[0]), True, end_match[0])


# ---------------------------------------------------------------------------
# Space release
# ---------------------------------------------------------------------------

# fallocate(2) mode flags. FALLOC_FL_PUNCH_HOLE deallocates the blocks behind a
# byte range and makes it read back as zeros; FALLOC_FL_KEEP_SIZE stops the call
# from moving EOF. Keeping the file's apparent size is not cosmetic here: `script`
# keeps appending through its own fd and every offset the logger already handed
# out is absolute, so a release that shrank the file would invalidate the window
# of every command still in flight.
FALLOC_FL_KEEP_SIZE = 0x01
FALLOC_FL_PUNCH_HOLE = 0x02

# Resolved lazily and cached, the failure included: this module is imported on
# every command, so a libc that cannot be loaded (non-Linux host, stripped image)
# must neither crash the logger at import nor be retried per command.
_libc: Optional[Any] = None
_libc_resolved = False

# errno of the most recent failed punch, so the caller can name it in its
# one-line degradation log without importing ctypes itself. Valid only
# immediately after a punch_hole() call that returned False.
_last_punch_errno = 0


def _get_libc() -> Optional[Any]:
    """Return a cached CDLL exposing ``fallocate``, or ``None`` if unavailable."""
    global _libc, _libc_resolved
    if not _libc_resolved:
        _libc_resolved = True
        try:
            lib = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
            # Explicit argtypes are mandatory: offset and length are 64-bit off_t,
            # and letting ctypes infer them truncates a >2 GiB length to 32 bits on
            # some ABIs — punching a hole of the wrong size over live audit data.
            lib.fallocate.argtypes = [ctypes.c_int, ctypes.c_int,
                                      ctypes.c_longlong, ctypes.c_longlong]
            lib.fallocate.restype = ctypes.c_int
            _libc = lib
        except Exception:
            _libc = None  # no libc, no fallocate symbol, not Linux: degrade
    return _libc


def last_punch_errno() -> int:
    """errno of the last failed :func:`punch_hole`, or 0 if the last call succeeded."""
    return _last_punch_errno


def punch_hole(path: str, offset: int, length: int) -> bool:
    """Deallocate ``[offset, offset + length)`` of ``path`` in place.

    Returns True when the range was released (or when there was nothing to
    release), False on any failure. It NEVER raises: the caller is the detached
    runner, where an exception would cost an artifact or a manifest, and a
    filesystem that refuses the operation is a supported degradation
    (grow-until-session-end), not an error.

    A non-positive ``length`` issues no syscall at all, so "no window" and "an
    empty window" both cost nothing and neither is reported as a failure.
    """
    global _last_punch_errno
    _last_punch_errno = 0
    if length <= 0:
        return True
    libc = _get_libc()
    if libc is None:
        return False
    try:
        fd = os.open(path, os.O_RDWR)
    except OSError as e:
        _last_punch_errno = e.errno or 0
        return False
    try:
        ctypes.set_errno(0)
        # THE OR IS MANDATORY: fallocate(2) requires FALLOC_FL_PUNCH_HOLE to be
        # ORed with FALLOC_FL_KEEP_SIZE, and the punch flag alone fails outright
        # with EOPNOTSUPP. Dropping either turns every release into a silent no-op
        # that looks exactly like an unsupported filesystem.
        rc = libc.fallocate(fd, FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE,
                            offset, length)
        if rc != 0:
            # EOPNOTSUPP (95) / ENOSYS (38) on a filesystem without punch-hole
            # support; anything else is just as non-fatal here.
            _last_punch_errno = ctypes.get_errno()
            return False
        return True
    except Exception:
        return False
    finally:
        os.close(fd)
