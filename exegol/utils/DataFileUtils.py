import json
import os
import re
import sys
import tempfile
from json import JSONEncoder, JSONDecodeError
from pathlib import Path
from types import MethodType, FunctionType
from typing import Union, Dict, cast, Optional, Pattern, Set, Any, List, Tuple

import yaml
import yaml.parser
import yaml.scanner

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger
from exegol.utils.FsUtils import SCRATCH_SUFFIX, mkdir, get_user_id, scratch_prefix, sweep_stale_scratch


def _current_umask() -> int:
    """The process umask, read the only way POSIX offers: by setting it back.

    `_create_config_file` needs it to give a newly created config the mode a plain
    `open(path, 'w')` would have produced -- mkstemp creates 0600 whatever the umask.
    """
    mask = os.umask(0o022)
    os.umask(mask)
    return mask

# Effectively infinite line width for `_yamlLiteral`, so PyYAML never folds a long path.
_YAML_LITERAL_WIDTH = 2 ** 31 - 1


class DataFileUtils:

    class ObjectJSONEncoder(JSONEncoder):
        def default(self, o: object) -> Dict:
            result = {}
            for key, value in o.__dict__.items():
                if key.startswith("_"):
                    continue
                result[key] = value
            return result

    def __init__(self, file_path: Union[Path, str], file_type: str, dynamic_default: Optional[Dict] = None):
        """Generic datastore backed by a config file.

        :param file_path: a bare string is placed inside the default exegol directory.
        :param file_type: 'yml' or 'json'.
        :param dynamic_default: config name -> callable, for a default that cannot be a literal.
        """
        if type(file_path) is str:
            file_path = ConstantConfig.exegol_config_path / file_path
        if file_type not in ["yml", "yaml", "json"]:
            raise NotImplementedError(f"The file type '{file_type}' is not implemented")
        # Config file options
        self._file_path: Path = cast(Path, file_path)
        self.__file_type: str = file_type
        self.__config_upgrade: bool = False
        # Set when the file said something unreadable (a scalar where a section belongs,
        # not merely a missing key): by _parse_config for a non-mapping root, by a
        # subclass's _process_data for a section. Suppresses the upgrade rewrite in
        # __load_file. A subclass must OR into it, never assign -- _parse_config arms it
        # before _process_data runs, and an assignment there disarms it.
        self._config_refused: bool = False
        # Set when the file parsed but declared nothing -- only comments, only `---`, or
        # only blank lines. Unlike _config_refused nothing is wrong with it, so the
        # defaults apply and no error is logged; the upgrade rewrite is still suppressed,
        # because it would replace the operator's comments, the file's only content, with
        # a generated template. See _parse_config.
        self._config_declares_no_keys: bool = False

        # Dynamic default
        self.__dynamic_default: Dict[str, Union[MethodType, FunctionType]] = dynamic_default if dynamic_default is not None else dict()

        self._raw_data: Any = None

        # Process
        self.__load_file()

    def _get_dynamic_default(self, attr_name: str) -> Union[str, int, bool]:
        if attr_name in self.__dynamic_default.keys():
            return self.__dynamic_default[attr_name]()
        raise NotImplementedError(f"The dynamic default value is not define for attribute '{attr_name}'")

    def __load_file(self) -> None:
        """Load the file and the parameters it declares."""
        if not self._file_path.parent.is_dir():
            logger.verbose(f"Creating config folder: {self._file_path.parent}")
            mkdir(self._file_path.parent)
        if not self._file_path.is_file():
            logger.verbose(f"Creating default file: {self._file_path}")
            self._create_config_file()
        else:
            self._parse_config()
            if self.__config_upgrade:
                if self._config_declares_no_keys:
                    # A document that declares no key is a complete statement ("use the
                    # defaults"), not an out-of-date file, and rewriting it would destroy
                    # the comments that are its entire content.
                    logger.verbose("Skipping the config file upgrade: the file declares no keys, "
                                   "and rewriting it would discard the comments it holds.")
                elif self._config_refused:
                    # A refused section leaves every key under it missing, so the upgrade
                    # flag is raised for all of them and this rewrite would normalise the
                    # operator's own line out of the file. The rewrite is for a config that
                    # is merely old; one that is wrong has to keep saying what the operator
                    # wrote, or the warning explaining it is a one-shot and their intent is
                    # gone from disk after a single run.
                    logger.verbose("Skipping the config file upgrade: part of it could not be read, "
                                   "and rewriting it would discard what the user actually wrote.")
                elif not self.__keep_pre_upgrade_backup():
                    # The copy is all that stands between a damaged file and a lost
                    # configuration for damage no detector caught, so without it the rewrite
                    # does not happen. The file stays out of date, which is the state it was
                    # already in, and readable.
                    logger.verbose("Skipping the config file upgrade: a copy of the current file "
                                   "could not be kept, and the rewrite would replace it with "
                                   "defaults for every key it does not declare.")
                else:
                    logger.verbose("Upgrading config file")
                    self._create_config_file()
                    # Re-read the rewritten file: the rewrite may seed keys (e.g. `*.sources`)
                    # that the attributes must reflect on this run, not the next one.
                    # The flag is cleared first so a still-missing key cannot cause a rewrite loop.
                    self.__config_upgrade = False
                    self._parse_config()

    def __keep_pre_upgrade_backup(self) -> bool:
        """Copy the file beside itself as ``<name>.bak`` before the upgrade rewrite.

        The rewrite is what turns damage into loss: ``_create_config_file`` writes
        ``_build_file_content()`` from the in-memory values, so every key the file did not
        declare — including every key below a truncation — is written back as its default.
        ``_parse_config`` refuses the truncations it can prove, but no detector catches a cut
        landing exactly on a newline. This is the net under that residue.

        The copy is verified before the rewrite is allowed: a short or failed copy is worse than
        none, because the caller would destroy the original believing it was kept. The symlink is
        resolved as ``_create_config_file`` resolves it, so the copy holds the bytes about to be
        replaced and lands beside the real file.

        It goes through a scratch file and a rename because a direct ``os.open`` of
        ``<name>.bak`` writes through whatever inode that name already resolves to.
        ``O_NOFOLLOW`` turns a symlink into ``ELOOP`` but says nothing about a hard link: that
        is a second name for an ordinary inode, so it opens cleanly, ``O_TRUNC`` empties the
        victim, and the read-back cannot see it because it reads the descriptor it just wrote.
        Under ``sudo exegol`` — where the config directory belongs to an unprivileged user by
        design — that is root truncating a file that user named, and removing a key is enough to
        reach this path. ``mkstemp`` + ``os.replace`` never opens a pre-existing name for
        writing, so it is immune to both and atomic besides. A pre-existing regular ``.bak`` is
        replaced rather than refused, or every later upgrade would freeze permanently; a
        directory at that name still fails and skips the rewrite.

        The mode is set on the descriptor before the rename, so the content never exists at a
        wider mode, and the read-back comes from that same descriptor — the inode about to
        become the copy.

        :return: True if a byte-identical copy is on disk, False otherwise.
        """
        try:
            target = self._file_path
            if target.is_symlink():
                target = Path(os.path.realpath(target))
            previous = target.read_bytes()
            backup = target.with_name(target.name + ".bak")
            mode = 0o600 if sys.platform == "win32" else (target.stat().st_mode & 0o777)
            # Same housekeeping as `_create_config_file`: a scratch abandoned by a killed
            # run is recognisable only by the marker `scratch_prefix` puts in it, and this
            # is the one moment a later run is known to be about to touch that name anyway.
            sweep_stale_scratch(target.parent, backup.name)
            fd, tmp_name = tempfile.mkstemp(dir=str(target.parent),
                                            prefix=scratch_prefix(backup.name),
                                            suffix=SCRATCH_SUFFIX)
            tmp_file = Path(tmp_name)
            replaced = False
            try:
                try:
                    # os.write may write fewer bytes than it was given (a signal, a large
                    # buffer, some filesystems), so the count is consumed rather than
                    # discarded. The read-back below would catch a short write, but only
                    # after it had already landed.
                    remaining = memoryview(previous)
                    while remaining:
                        remaining = remaining[os.write(fd, remaining):]
                    os.fsync(fd)
                    if sys.platform != "win32":
                        os.fchmod(fd, mode)
                    os.lseek(fd, 0, os.SEEK_SET)
                    written = b""
                    while True:
                        chunk = os.read(fd, 1 << 20)
                        if not chunk:
                            break
                        written += chunk
                finally:
                    os.close(fd)
                if written != previous:
                    return False
                os.replace(tmp_name, backup)
                replaced = True
            finally:
                # Never leave the scratch behind: it sits next to the operator's config
                # and nothing else would clean it up. After a successful replace the name
                # is already gone, so this fires only on the failure paths -- a short
                # read-back, or a rename blocked by a directory at <name>.bak.
                if not replaced:
                    tmp_file.unlink(missing_ok=True)
            logger.verbose(f"Kept a copy of the previous file at {backup} before upgrading it.")
            return True
        except OSError as e:
            logger.debug(f"Could not keep a copy of {self._file_path} before the upgrade "
                         f"rewrite: {e}")
            return False

    def _build_file_content(self) -> str:
        """Build the file content, for a file that does not exist yet or is being upgraded."""
        raise NotImplementedError(f"The '_build_default_file' method hasn't been implemented in the '{self.__class__}' class.")

    @staticmethod
    def _yamlLiteral(value: Any) -> str:
        """Render ``value`` as the YAML scalar text to put after ``key:`` in a `yml` template.

        PyYAML picks the quoting (``'yes'``, ``'%profile'``, bare ``100%``), so the writer
        matches `_parse_config`'s reader. Apply it once, to a raw value: it is not idempotent
        on its own output. A one-key mapping is dumped because a bare scalar dump appends a
        ``...`` document-end marker.

        :param value: the raw attribute value, ``str()``-ed first (``Path`` has no representer).
        :return: the scalar text to interpolate after ``key: ``.
        """
        key = "v"
        dumped = yaml.dump({key: str(value)}, default_flow_style=False,
                           width=_YAML_LITERAL_WIDTH, allow_unicode=True)
        prefix = f"{key}:"
        if not dumped.startswith(prefix):
            raise RuntimeError(f"Unexpected YAML emission while rendering a config value: {dumped!r}")
        return dumped[len(prefix):].strip()

    def _create_config_file(self) -> None:
        """Create or overwrite the file with what `_build_file_content` renders.

        Written through a scratch file and a rename, because `open(path, 'w')` truncates first
        and writes second: any interruption between those steps left a zero-byte config.yml,
        which `yaml.safe_load` reads as `None`. rename(2) within a directory is atomic, so a
        reader sees the whole old file or the whole new one, never a prefix. The scratch is
        unique per writer and lives in the same directory as the resolved target, so the rename
        stays a rename and two concurrent invocations cannot interleave into one path. The mode
        is set explicitly: the rename installs a fresh inode and mkstemp creates its file 0600
        regardless of umask, so permissions would otherwise be re-derived on every rewrite.

        A symlinked config.yml is resolved first: `open(path, 'w')` follows a link and writes
        through it, while `os.replace` replaces the link. Keeping ~/.exegol/config.yml as a link
        into a dotfiles repo is ordinary and this method runs on every config upgrade, so
        without the resolution the operator's real file was silently disconnected rather than
        modified — `git status` showed nothing, and the file they believed was their config
        stopped being read. Renaming over the link also dropped ACLs, xattrs, hard links and the
        owner, and even took the mode from the target, since stat() follows the link while the
        rename does not. A dangling link resolves to the path it names, so the create branch
        fills the target in rather than replacing the link.

        Abandoned scratch files are swept first: the `except: unlink` below covers exceptions
        only, and a SIGKILL between mkstemp and replace leaves a randomly-named scratch no later
        run has a fixed path to clean. This method is reached on essentially every `exegol`
        invocation, so every interrupted run left one more file in the operator's config
        directory, permanently.
        """
        try:
            target = self._file_path
            if target.is_symlink():
                target = Path(os.path.realpath(target))
            sweep_stale_scratch(target.parent, target.name)
            previous_mode: Optional[int] = None
            if target.is_file():
                previous_mode = target.stat().st_mode & 0o777
            fd, tmp_name = tempfile.mkstemp(dir=str(target.parent),
                                            prefix=scratch_prefix(target.name),
                                            suffix=SCRATCH_SUFFIX)
            os.close(fd)
            tmp_file = Path(tmp_name)
            try:
                # encoding pinned, matching the sibling writer at
                # ContainerConfig.__writeSentinelConfig. Without it the locale encoding is
                # used -- cp1252 on a Windows host, a supported platform -- and
                # _build_file_content() interpolates the operator's home directory, so a
                # username outside cp1252 raised UnicodeEncodeError. That is a ValueError:
                # the `except Exception` here unlinks the scratch and re-raises, and neither
                # handler below catches it, so first-run config creation failed with the
                # crash banner on every invocation, forever.
                with tmp_file.open("w", encoding="utf-8") as file:
                    file.write(self._build_file_content())
                    file.flush()
                    os.fsync(file.fileno())
                if sys.platform != "win32":
                    # Preserve what the file had, or fall back to the umask-derived
                    # mode a plain `open(..., 'w')` would have produced for a new
                    # file -- never mkstemp's 0600, which would silently harden an
                    # existing config.yml on every upgrade.
                    if previous_mode is not None:
                        os.chmod(tmp_file, previous_mode)
                    else:
                        os.chmod(tmp_file, 0o666 & ~_current_umask())
                if sys.platform == "linux" and os.getuid() == 0:
                    user_uid, user_gid = get_user_id()
                    os.chown(tmp_file, user_uid, user_gid)
                tmp_file.replace(target)
            except Exception:
                # Never leave the scratch behind: it sits next to the operator's config and
                # nothing else would clean it up. The name belongs to this writer alone, so
                # the unlink cannot hit another process's in-flight file.
                tmp_file.unlink(missing_ok=True)
                raise
        except PermissionError as e:
            logger.critical(f"Unable to open the file '{self._file_path}' ({e}). Please fix your file permissions or run exegol with the correct rights.")
        except OSError as e:
            logger.critical(f"A critical error occurred while interacting with filesystem: [{type(e)}] {e}")

    def _torn_write_header(self) -> Optional[str]:
        """The static leading bytes a partially written file would be a prefix of.

        ``None`` -- the default -- means this file type cannot be recognised that way, which
        leaves a zero-byte file as the only torn write ``_parse_config`` can identify.
        ``UserConfig`` overrides it with the literal comment header every generated
        ``config.yml`` starts with.

        Deliberately not ``_build_file_content()``: that interpolates live state and, for
        ``UserConfig``, resolves a dynamic default as a side effect, so calling it while parsing
        would mutate the object under the parser and produce bytes depending on the very config
        being read. The header is a literal, stable across versions and free of both problems.
        """
        return None

    def _torn_write_last_key(self) -> Optional[Pattern[str]]:
        """A pattern matching the last key this file type's template writes.

        The header proves a document came from this wrapper's template; this proves it reached
        the end of it. ``None`` -- the default -- means this file type has no such witness. See
        ``_parse_config`` for why an end-of-template witness is required before an unterminated
        final line may refuse anything.

        A pattern over the key, not the literal trailing block: that block is prose an operator
        is invited to edit, and every edit to it re-armed the wholesale refusal this witness
        exists to prevent.
        """
        return None

    def _torn_write_required_keys(self) -> Optional[Tuple[Tuple[str, ...], ...]]:
        """The key paths a complete file of this type declares above that last key, in the
        order the template writes them.

        The second, tolerant end-of-template witness, and the only one that survives the
        operator deleting the trailing block. The order is load-bearing:
        ``_reached_template_end`` reads the last entry, the only one whose presence says where
        the write stopped. The rest are carried so the drift tripwire can pin this tuple by
        equality against the generated template, which is what keeps the last entry actually
        last.

        ``None`` -- the default -- means this file type has no such list. A literal for the same
        reason as the header: ``_build_file_content()`` interpolates live state and mutates the
        object under the parser.
        """
        return None

    @staticmethod
    def __declares(data: Any, path: Tuple[str, ...]) -> bool:
        """Whether ``data`` declares the nested key ``path``, whatever its value.

        The value is deliberately not looked at: ``sources:`` with nothing under it,
        ``custom_images: []`` and an empty ``default_profile:`` are all complete statements.
        The only question is whether the document got this far.
        """
        node = data
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return False
            node = node[key]
        return True

    @staticmethod
    def __last_declaration(text: str, key: str) -> int:
        """Offset of the last line of ``text`` that declares ``key``, or ``-1``.

        Line-anchored and with the colon rather than ``text.rfind(key)``: the bare name also
        matches inside a comment or a URL, and the generated config.yml carries ``config``
        inside a documentation link in the block below the last required key — exactly where
        the caller measures. The quoted spelling is matched too, because YAML permits it and
        the operator's file is not the wrapper's output.

        The imprecision runs in both directions, and only one of them is safe:

          * over-approximating, by not modelling nesting: ``enabled`` appears under both
            ``log_rotation`` and ``log_output``, so a match may report a key path this
            document does not actually declare. That can only make the caller's "nothing
            below the last one" test stricter, which is the direction a fail-safe may err in.
          * under-approximating, on any spelling that is not a line-anchored ``key:`` at all
            -- a key inside a flow mapping (``network: {a: 1}``), or reached through an
            alias. Those return ``-1`` and are invisible to the caller, which is the
            permissive direction, so the caller must not read ``-1`` as "nothing found, so
            refuse": see the no-opinion branch in ``_reached_template_end``.
        """
        last = -1
        for match in re.finditer(
                r"""(?m)^[ \t]*(?:'|")?""" + re.escape(key) + r"""(?:'|")?[ \t]*:""", text):
            last = match.start()
        return last

    def _reached_template_end(self, normalised_text: str, data: Any) -> bool:
        """Positive evidence that a document reached the end of the template.

        Either witness is enough, and they cover different edits: the key pattern survives
        rewording or inlining the trailing block, the required-key list survives deleting it
        outright. See ``_parse_config``.

        Witness 2 asks for the last required key, not all of them, because a truncation removes
        a suffix: a torn document declares a prefix of the template's key sequence, so the only
        entry whose presence says where the write stopped is the last one. Requiring the earlier
        ones adds no coverage, and it costs every operator whose document is missing a key for a
        reason that is not a tear: dropping the unused ``sentinel:`` block, leaving
        ``log_rotation:`` empty, or a config predating a key this version added. Each was
        refused wholesale (``_raw_data = {}``, the upgrade suppressed so it never self-heals, a
        red error every run); all three declare the last required key, so all three now read
        normally.

        The precondition is checked, not assumed. "A truncation removes a suffix" is about
        bytes; "the last entry of the tuple" is about ``_TEMPLATE_KEY_PATHS`` order, and
        ``__declares`` reads the parsed mapping, which has no order — so on a reordered document
        the bridge is simply false, and the torn file is read, rewritten, and an operator's
        ``log_output.enabled: False`` replaced by the default on disk. So the order becomes a
        text-level test: no required key may be declared below the last one. A reordered
        document then falls through to the refusal, which is loud and recoverable, and no
        coverage is paid for it.

        What the check cannot reach, in block-spelled documents (a flow-style block has no
        residue, since the order check abstains and the conjunction below refuses every
        key-losing tear):

          * a cut inside the comment run directly below the last required key, with no key
            declared under it. That prefix is byte-for-byte a document whose blocks the
            operator deleted — the class witness 2 exists to accept — and no local rule
            separates the two: neither a coverage floor nor contiguity, since the document
            that must be read declares fewer required keys than the worst residue.
          * a cut inside the last required key's own value, which is not that class: a file
            ending ``exegol_default_netmask: 2`` is read as a /2, and the upgrade rewrite then
            persists both that value and the defaults for every block below the cut.

        Both are silent — the file is read and rewritten, not refused — so the published
        precondition ("if you have reordered blocks, keep the final newline") is what keeps an
        operator out of the window, and the residue is published beside it.
        ``__keep_pre_upgrade_backup`` is no net here: the ``.bak`` holds the torn bytes.

        The undecidable case stays refused: a document whose omission is a contiguous suffix of
        the key sequence is byte-for-byte what a tear at that point produces.
        """
        last_key = self._torn_write_last_key()
        if last_key is not None and last_key.search(normalised_text) is not None:
            return True
        required = self._torn_write_required_keys()
        if required and self.__declares(data, required[-1]):
            # The order precondition, checked against the document's own text.
            # `__declares` reads the parsed mapping, which has no order the suffix
            # argument can use; this reads the bytes. A required key written below the
            # last one means this document's tail is not the template's tail, so the
            # witness proves nothing about where the write stopped and refusal is safe.
            last_at = self.__last_declaration(normalised_text, required[-1][-1])
            if last_at < 0:
                # No line-anchored declaration: the parsed data says this document declares
                # the last required key, so the only way the text does not is a spelling
                # `__last_declaration` cannot see -- a flow mapping, an alias. The order
                # precondition is not expressible against these bytes, so it abstains.
                #
                # Abstaining must not mean accepting: returning True would drop the reorder
                # check for every document written in flow style. Refusing is no good
                # either -- that discards a complete config for its YAML style, the failure
                # this branch prevents. So fall back to the only question the text still
                # answers: does it declare every required key? A complete document does
                # whatever its spelling, and a truncated one cannot, since a tear removes a
                # suffix and takes a key with it.
                if all(self.__declares(data, path) for path in required):
                    return True
            elif all(self.__last_declaration(normalised_text, path[-1]) <= last_at
                     for path in required):
                return True
        return False

    def _parse_config(self) -> None:
        data: Dict = {}
        # Read the bytes and decode UTF-8 explicitly rather than letting `open(path, 'r')`
        # pick the locale encoding: one accented character saved by a cp1252 editor raised
        # UnicodeDecodeError, which is a ValueError and is caught by nothing below.
        # UserConfig() is built on essentially every invocation, so it reached
        # ExegolController's catch-all and every `exegol` command died with the "please
        # report a bug" banner — and the wrapper could not be used to fix the file breaking
        # it.
        #
        # The decode is strict and its failure a refusal, not errors="replace": a mangled
        # value would be fed to the choices=/type guards as though the operator had written
        # it, and the shape for "this file cannot be read" is one message, capture off, file
        # untouched.
        #
        # The read is inside the same arm, not just the decode: every OSError it can raise
        # reproduces that crash verbatim (a mode-000 config.yml gives PermissionError out of
        # UserConfig.__init__). The routes are narrower than a latin-1 comment but real — a
        # config left root-owned by an older `sudo exegol`, a network home returning EIO, an
        # SELinux denial, a mount gone read-only — and the outcome is the same unusable CLI.
        try:
            raw_bytes = self._file_path.read_bytes()
        except OSError as read_error:
            logger.error(f"The file {self._file_path} cannot be read ({read_error}). Ignoring it "
                         f"and using the default values; the file is left untouched so it can be "
                         f"corrected.")
            self._raw_data = {}
            self._config_refused = True
            self._process_data()
            return
        try:
            raw_text = raw_bytes.decode("utf-8")
            # A leading BOM is stripped before anything looks at the text: PyYAML strips
            # it before parsing, and the byte-level tests below must agree with the parser
            # about what the document is. "UTF-8 with BOM" is the Notepad default, and
            # without this a comments-only config.yml starts "\ufeff#" rather than "#", so
            # `declares_nothing` was false, the file was refused with capture off, and the
            # message blamed a truncated header. `json.loads` rejects a BOM outright, so
            # the same strip is what lets a .datacache from such an editor be read at all.
            raw_text = raw_text.lstrip("\ufeff")
        except UnicodeDecodeError as decode_error:
            logger.error(f"The file {self._file_path} is not valid UTF-8 "
                         f"({decode_error.reason} at byte {decode_error.start}). Ignoring it and "
                         f"using the default values; the file is left untouched so it can be "
                         f"corrected.")
            # Same arming as the YAMLError arm below: without it `data` stays {} — a dict —
            # so every section reads as absent rather than refused, capture falls back to
            # its default of on, and every key looks missing, so the upgrade rewrite
            # replaces the whole config.yml with defaults.
            self._raw_data = {}
            self._config_refused = True
            self._process_data()
            return
        try:
            if self.__file_type == "yml":
                data = yaml.safe_load(raw_text)
            elif self.__file_type == "json":
                data = json.loads(raw_text)
        # yaml.YAMLError, not yaml.parser.ParserError: `safe_load` raises a different
        # subclass per failing stage, and a tab used for indentation (ScannerError) or an
        # undefined alias (ComposerError) derive from neither. One tab in
        # ~/.exegol/config.yml escaped this handler and made the whole CLI unusable with a
        # traceback instead of the line below.
        except yaml.YAMLError:
            # The message names the file: this is the one diagnostic the operator gets, and
            # the wrapper keeps running afterwards, so "which file do I fix" has to be in it.
            logger.error(f"Error while parsing {self._file_path} ! Check for a syntax error.")
            # A syntax error is a refusal, like the non-mapping root below and for the same
            # reason: without the flag `data` stays {} — a dict, so that branch does not
            # fire — and every section reads as absent. Capture then falls back to on,
            # guessed, when `log_output.enabled: false` is the only complete control against
            # a client's secrets reaching their SIEM, and the upgrade rewrite replaces the
            # operator's entire config.yml with defaults after one run.
            self._config_refused = True
        except JSONDecodeError:
            logger.error(f"Error while parsing exegol data file {self._file_path} ! Check for syntax error.")
            # Same arming for the JSON side. It costs nothing for .datacache:
            # DataCache raises no upgrade flag, and save_updates() rebuilds the file
            # on the next run regardless.
            self._config_refused = True
        # ---------------------------------------------------------------------
        # Torn-write provenance, decided for every parse outcome.
        #
        # This used to live inside the `data is None` arm below, reached only while the
        # document declares nothing at all. `_TEMPLATE_HEADER` ends on a key line, so from
        # byte 212 of a 7,534-byte config.yml the document parses to a dict and that arm was
        # never entered: the detector covered 2.8% of the offsets a torn write can land on,
        # and on the rest every key below the cut read as missing, so the upgrade flag was
        # raised and __load_file rewrote the file with defaults for all of them — an
        # operator's `sentinel.log_output.enabled: false` gone from disk after one run, and
        # capture silently back on.
        #
        # Two provenance signals, both cheap:
        #
        #  * torn inside the header -- the whole document is a prefix of the static header.
        #    Covers offsets 0..len(header), zero bytes included.
        #  * torn past the header -- the document starts with the whole header, its last
        #    line is unterminated, and there is no positive evidence that it reached the end
        #    of the template (`_reached_template_end`).
        #
        #    The third conjunct is not optional. The header is present in every config.yml
        #    this wrapper generated and the operator then edited — the normal case — so
        #    without it the rule applied to virtually every real config, and a complete one
        #    saved without its final newline was refused wholesale: every key defaulted for
        #    the life of the file, a red error every run, and the upgrade suppressed so it
        #    never self-heals. Losing a trailing newline is ordinary (VS Code's
        #    trimFinalNewlines, a `$(cat ...)` round-trip, a copy-paste). The witness tells
        #    the two apart, and it is provenance rather than a guess about YAML: a document
        #    that reached the end of the bytes this wrapper writes can only be missing the
        #    newline. It must not be the trailing block itself — that is prose the template
        #    invites operators to edit, so deleting or rewording it made the witness
        #    unfindable and refused the whole config again — and judging the final line's
        #    YAML completeness instead is much weaker, since most of the offsets this rule
        #    catches end inside a comment, which no local rule tells from a complete one.
        #
        # Both comparisons are made on CRLF-normalised text: `_TEMPLATE_HEADER` is LF-only,
        # so a torn write that passed through a CRLF-normalising copy escaped the detector
        # entirely.
        #
        # Not caught: a truncation landing exactly on a newline looks complete and no local
        # signal separates it from an old file. __load_file's unconditional pre-upgrade
        # backup is the net under that residue — it is the rewrite, not the damage, that
        # turns a damaged file into a lost configuration.
        header = self._torn_write_header()
        normalised_text = raw_text.replace("\r\n", "\n")
        normalised_header = None if header is None else header.replace("\r\n", "\n")
        torn_in_header = normalised_header is not None and normalised_header.startswith(normalised_text)
        # The write reached the end of the template, so an unterminated last line is a
        # missing newline and not a buffer that stopped. Without a witness for this kind
        # of file there is no such evidence and the unterminated-line signal is not used
        # at all: refusing an operator's whole configuration needs positive evidence, not
        # the absence of one byte. `data` is passed as well as the text because one of the
        # two witnesses is structural -- on a parse failure it is still `{}`, which
        # declares nothing, so a truncation that broke the YAML cannot buy an acceptance.
        reached_template_end = self._reached_template_end(normalised_text, data)
        torn_past_header = bool(
            normalised_header is not None
            and normalised_text.startswith(normalised_header)
            and not normalised_text.endswith("\n")
            and not reached_template_end
        )
        torn_write = not raw_text or torn_in_header or torn_past_header
        if torn_write:
            # A truncated document is a refusal, not "the operator set nothing" and not "an
            # old file to be upgraded". Do not call _create_config_file here: a file that
            # cannot be used has to keep saying what it said, or the message explaining it is
            # a one-shot with nothing left to correct. `_config_refused` carries both halves
            # — capture turned off rather than defaulted to True, and the upgrade rewrite
            # suppressed. Exegol no longer produces torn writes itself, but a full disk, a
            # container teardown, an operator's own `> config.yml` or a copy that stopped
            # early all still do.
            if not raw_text:
                detail = "is empty"
            elif torn_in_header:
                detail = ("stops part-way through the header this wrapper generates, so it is a "
                          "partially written file rather than a configuration")
            else:
                detail = ("stops on an unterminated line and does not declare the keys this "
                          "wrapper writes last, so it is a partially written copy of a file "
                          "this wrapper generated rather than a configuration")
            logger.error(f"The file {self._file_path} {detail}. Ignoring it and using the "
                         f"default values; the file is left untouched so it can be corrected.")
            self._raw_data = {}
            self._config_refused = True
            self._process_data()
        elif data is None:
            # `safe_load` returns None for four different documents — zero bytes, comments
            # only, a bare `---`, blank lines — and only the first is the torn-write state.
            # The other three are valid YAML meaning "the operator declared nothing", and
            # commenting every line out is the obvious way to ask for the defaults. Refusing
            # them printed a false "is empty" error and armed _config_refused, which turns
            # output capture off on every invocation: the operator asked for defaults and got
            # the feature off.
            #
            # `st_size != 0` cannot separate them — a torn write is zero bytes only if it was
            # torn at byte zero, and the ~250-byte comment header means a write that stopped
            # inside it leaves an all-comments document that reads as "declares nothing".
            # Provenance separates them: a torn write is a proper prefix of the bytes this
            # wrapper generates, and a commented-out config diverges from the template at the
            # first `#`. That half is decided above for every parse outcome, so what is left
            # here is a document that parsed to nothing and is not a truncation.
            #
            # Vacuously true for a whitespace-only document, which is intended.
            declares_nothing = all(
                line.startswith("#") or line in ("---", "...")
                for line in (raw.strip() for raw in raw_text.splitlines()) if line
            )
            if declares_nothing:
                # Not a torn write: a document that says nothing. Take the defaults and leave
                # the file alone (see _config_declares_no_keys for why the upgrade rewrite is
                # suppressed rather than allowed to normalise the comments away). `verbose`,
                # not `debug`: every setting is at its default, capture included, and the file
                # will never receive newly added options — a consequence the operator cannot
                # otherwise see. Not a warning, since it is what the document asks for.
                logger.verbose(f"The file {self._file_path} declares no keys: every setting is at its "
                               f"default value, and the file is left untouched (so it will not be "
                               f"updated with newly added options either).")
                self._raw_data = {}
                self._config_declares_no_keys = True
                self._process_data()
                return
            # Parsed to nothing, is not comments-only, and is not a truncation of anything
            # this wrapper wrote. Still not a configuration, so it is refused for the same
            # reason as the non-mapping root below, and left alone so it can be corrected.
            logger.error(f"The file {self._file_path} declares no keys but is not a document this "
                         f"wrapper can recognise. Ignoring it and using the default values; the "
                         f"file is left untouched so it can be corrected.")
            self._raw_data = {}
            self._config_refused = True
            self._process_data()
        elif not isinstance(data, dict):
            # A non-mapping root is a refusal, not silence — the same distinction
            # __load_section draws one level down. Without it, a root that is a list or a
            # scalar reached _process_data with every section reading as absent: no warning
            # anywhere, capture defaulted back on (the one direction that must never be
            # guessed), and every key looked missing, so the upgrade rewrite replaced the
            # operator's entire file with defaults. One stray `- ` on the first key makes the
            # document a list. Do not call _create_config_file here: a config that is wrong
            # has to keep saying what the operator wrote, or the warning is a one-shot and
            # their intent is gone from disk after a single run.
            logger.error(f"The file {self._file_path} must be a mapping of keys, not a "
                         f"{type(data).__name__}. Ignoring it and using the default values; "
                         f"the file is left untouched so it can be corrected.")
            self._raw_data = {}
            self._config_refused = True
            self._process_data()
        else:
            self._raw_data = data
            self._process_data()

    def __load_config(self, data: dict, config_name: str, default: Optional[Union[bool, str, int, List[str], dict]],
                      choices: Optional[Set[str]] = None) -> Union[bool, str, int, List[str], dict]:
        """Load ``config_name`` from ``data``, or ``default`` (or the dynamic default) if it is
        absent -- which also raises the upgrade flag.

        :param choices: (optional) the acceptable values; anything else warns and takes the default.
        """
        try:
            if config_name not in data.keys():
                logger.debug(f"Config {config_name} has not been found in Exegol '{self._file_path.name}' config file. The file will be upgrade.")
                self.__config_upgrade = True
                return default if default is not None else self._get_dynamic_default(config_name)
            result = data.get(config_name)
            if result is None:
                return default if default is not None else self._get_dynamic_default(config_name)
            elif choices is not None and result not in choices:
                default = default if default is not None else self._get_dynamic_default(config_name)
                logger.warning(f"The configuration is incorrect! "
                               f"The user has configured the '{config_name}' parameter with the value '{result}' "
                               f"which is not one of the allowed options ({', '.join(choices)}). Using default value: {default}.")
                return default
            return result
        except TypeError:
            logger.error(f"Error while loading {config_name}! Using default config.")
        return default if default is not None else self._get_dynamic_default(config_name)

    def _load_config_bool(self, data: dict, config_name: str, default: Optional[bool] = None,
                          choices: Optional[Set[str]] = None) -> bool:
        """``__load_config`` typed as a bool."""
        return cast(bool, self.__load_config(data, config_name, default, choices))

    def _load_config_str(self, data: dict, config_name: str, default: Optional[str] = None, choices: Optional[Set[str]] = None) -> str:
        """``__load_config`` typed as a str."""
        return cast(str, self.__load_config(data, config_name, default, choices))

    def _load_config_int(self, data: dict, config_name: str, default: Optional[int] = None, choices: Optional[Set[str]] = None) -> int:
        """``__load_config`` typed as an int. A value that will not parse as one is fatal."""
        config = cast(Union[str, int], self.__load_config(data, config_name, default, choices))
        if isinstance(config, int):
            return config
        try:
            return int(config)
        except ValueError:
            logger.critical(f"Invalid value for {config_name}: received '{config}' instead of a number. Please use a correct format.")
            exit(1)

    def _load_config_path(self, data: dict, config_name: str, default: Optional[Path] = None) -> Path:
        """``config_name`` as a Path, with ``~`` expanded. Absent raises the upgrade flag."""
        try:
            result = data.get(config_name)
            if result is None:
                logger.debug(f"Config {config_name} has not been found in Exegol '{self._file_path.name}' config file. The file will be upgrade.")
                self.__config_upgrade = True
                return default if default is not None else cast(Path, self._get_dynamic_default(config_name))
            return EnvInfo.expand_user(result)
        except TypeError:
            logger.error(f"Error while loading {config_name}! Using default config.")
        return default if default is not None else cast(Path, self._get_dynamic_default(config_name))

    def _load_config_list_str(self, data: dict, config_name: str, default: Optional[List[str]] = None) -> List[str]:
        """``__load_config`` typed as a list of str, defaulting to an empty list."""
        return cast(List[str], self.__load_config(data, config_name, default=default if default is not None else list(), choices=None))

    def _load_config_dict(self, data: dict, config_name: str, default: Optional[dict] = None) -> dict:
        """``__load_config`` typed as a dict, defaulting to an empty dict."""
        return cast(dict, self.__load_config(data, config_name, default=default if default is not None else dict(), choices=None))

    def _process_data(self) -> None:
        raise NotImplementedError(f"The '_process_data' method hasn't been implemented in the '{self.__class__}' class.")
