"""Centralised regular expressions, charsets and regex-backed helpers.

Keeping the patterns in one dependency-light module (only ``re`` + ``typing``)
lets host-side config parsing (:mod:`exegol.config.UserConfig`) and the Sentinel
profile schema (:mod:`exegol.sentinel.SentinelProfile`) share the exact same
rules without duplicating a charset or risking an import cycle — ``SentinelProfile``
imports ``UserConfig``, so the shared rules cannot live in either of them.

Callers keep their own logging/error handling; this module only decides *validity*.
"""
import re
from typing import Optional

# --- Sentinel entity / source-key charset ------------------------------------
# '.' is the "sourcekey.name" reference separator, so it must never appear inside
# an entity name (trigger/action/profile) or a source key. Both are also used
# verbatim as on-disk directory names, so the charset doubles as a path-traversal
# guard: none of '.', '..', '/' or '\\' can match it.
SENTINEL_NAME_CHARSET: str = r"[A-Za-z0-9_-]+"
SENTINEL_NAME_RE = re.compile(SENTINEL_NAME_CHARSET)

# --- Sentinel git source validation (argument-injection control) -------------
# Both a URL and a ref travel verbatim into git's argv, and GitPython flattens
# clone options with ``shlex.split(" ".join(multi_options))``, so whitespace
# inside a ref becomes *additional* git options (e.g. ``--upload-pack=...`` ->
# arbitrary command execution). ``git ls-remote`` is also invoked without a
# ``--`` separator, so a value starting with '-' would be read as an option
# there. Allowlists (not blocklists) are the only robust guard.
SENTINEL_REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}")
SENTINEL_GIT_URL_RE = re.compile(r"(?:https?://|ssh://|git://|[A-Za-z0-9._-]+@[^\s:/]+:)[^\s]+")

# --- URL credential sanitisation ---------------------------------------------
# Matches the userinfo component of a URL authority ("//user:password@host" ->
# "//host"). Match up to the LAST '@' before the path so a password containing a
# literal '@' (e.g. "//user:p@ss@host/...") is stripped whole instead of leaking
# the "ss@host" tail.
_URL_USERINFO_RE = re.compile(r"//[^/\s]*@")


def sanitize_source_url(url: Optional[str]) -> Optional[str]:
    """Strip any ``user[:password]@`` userinfo from a git URL before it leaves the host.

    A private HTTPS source is exactly the case where an operator embeds a token
    (``https://user:ghp_xxx@host/org/profiles.git``), and the Sentinel ``_meta``
    block is bind-mounted into the container and shipped to the SIEM, where it
    would be persisted permanently and readable by anything that compromises the
    container.
    """
    if not url:
        return url
    return _URL_USERINFO_RE.sub("//", url)


def is_valid_sentinel_entity_name(name: str) -> bool:
    """True when ``name`` is a valid trigger/action/profile name (no '.' separator)."""
    return SENTINEL_NAME_RE.fullmatch(name) is not None


def is_valid_sentinel_source_key(key: str) -> bool:
    """True when ``key`` is a safe Sentinel source key / directory name.

    The charset already rejects '.', '..' and any path separator, but the
    separator/dot checks are kept explicit so the path-traversal intent survives
    even if the charset is later loosened.
    """
    key = str(key)
    if key in {".", ".."} or "/" in key or "\\" in key:
        return False
    return SENTINEL_NAME_RE.fullmatch(key) is not None


def is_valid_sentinel_ref(ref: str) -> bool:
    """True when ``ref`` is a safe git ref (branch/tag/SHA) for a Sentinel source."""
    return SENTINEL_REF_RE.fullmatch(str(ref)) is not None


def is_valid_sentinel_git_url(url: str) -> bool:
    """True when ``url`` is a git remote git reads as a plain URL.

    Rejects the ``helper::`` remote syntax (git resolves it to an arbitrary
    command) in addition to the transport/whitespace allowlist.
    """
    url = str(url)
    return SENTINEL_GIT_URL_RE.fullmatch(url) is not None and "::" not in url
