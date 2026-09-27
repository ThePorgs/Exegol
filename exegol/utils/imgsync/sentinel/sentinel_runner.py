#!/usr/bin/env python3
import logging
import json
import os
import sys
import shlex
import re
import fnmatch
import shutil
import subprocess
import signal
import stat
import time
import asyncio
from enum import StrEnum
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple, Union

# Shared with sentinel_logger.py so the inline event field and the output_capture
# artifact agree on cleaning, cutting and status vocabulary. Two import shapes:
# deployed the scripts are flat in /.exegol/sentinel/, tests import them as a package.
try:
    from .sentinel_output import (  # type: ignore[import-not-found]
        OUTPUT_STATUS_ERROR, OUTPUT_STATUS_OK, OUTPUT_STATUS_UNAVAILABLE,
        REDACTED_MARKER,
        MARKER_LEN,
        clean, find_filler_start, last_punch_errno, plan_byte_cut, punch_hole,
        truncate_text_offsets,
        validated_session_path,
    )
except ImportError:
    from sentinel_output import (  # type: ignore[no-redef]
        OUTPUT_STATUS_ERROR, OUTPUT_STATUS_OK, OUTPUT_STATUS_UNAVAILABLE,
        REDACTED_MARKER,
        MARKER_LEN,
        clean, find_filler_start, last_punch_errno, plan_byte_cut, punch_hole,
        truncate_text_offsets,
        validated_session_path,
    )

# Constants
LOG_DIR = Path("/var/log/exegol/sentinel")
CONFIG_PATH = LOG_DIR / "sentinel_config.json"
DEBUG_LOG_PATH = LOG_DIR / "sentinel_runner_debug.log"
ARTIFACTS_BASE_DIR = LOG_DIR / "artifacts"
# Value marker for env_redact-matched vars (key preserved). Aliased, never
# re-typed: a second copy is a chance to show two markers for the same decision.
REDACTED = REDACTED_MARKER
# Per-command artifact directory mode: 0o750, not 0o700, so a host SIEM agent in
# sentinel_gid can enter and read the manifests without root. Needs an explicit
# chmod: Path.mkdir(mode=...) is umask-masked and would drop the group bits.
ARTIFACT_DIR_MODE = 0o750
# chmod value keeping the setgid bit inherited from the host-created instance dir,
# otherwise files created inside lose the sentinel_gid group ownership.
ARTIFACT_DIR_CHMOD = ARTIFACT_DIR_MODE | stat.S_ISGID  # 0o2750
# Explicit artifact file mode: group-readable regardless of the inherited umask.
ARTIFACT_FILE_MODE = 0o640
# exec_command per-action limit defaults (UPPER_SNAKE so tests can monkeypatch).
# No default timeout: an exec_command runs until done, a per-action `timeout` or a stop signal.
DEFAULT_EXEC_MAX_OUTPUT = 1_000_000  # bytes = 1 MB
DEFAULT_EXEC_DRAIN_TIMEOUT = 5       # sec: bound the post-kill pipe drain
# Read granularity of the output_capture copy: chunked, not read whole, so an
# unlimited capture of a multi-gigabyte window never materialises on the heap.
# UPPER_SNAKE so tests can monkeypatch it.
OUTPUT_COPY_CHUNK = 1024 * 1024      # bytes = 1 MB
EXEC_TERMINATION_GRACE_SEC = 5       # sec: SIGTERM -> SIGKILL grace on shutdown
# Last-resort bound for `format: text` with no `max_size`. SentinelProfile refuses that
# combination host-side, but the runner never re-validates the deployed config, so a stale or
# hand-edited one still reaches here. It bounds the artifact, not the read: _copy_window_text
# must clean the whole window to know `bytes_total` in cleaned bytes, so peak memory is
# bounded only by WINDOW_SCAN_LIMIT. `raw` is unaffected and stays unlimited by default.
DEFAULT_TEXT_CAPTURE_CAP = 1_000_000  # bytes = 1 MB


def get_env_safe(key: str, default: str = "") -> str:
    """Read environment variable safely"""
    return os.environ.get(key, default)


def set_artifact_file_mode(path: Path) -> None:
    """Best-effort ``chmod ARTIFACT_FILE_MODE`` on a written artifact (failures ignored)."""
    try:
        os.chmod(path, ARTIFACT_FILE_MODE)
    except OSError:
        pass

class ModeEnum(StrEnum):
    PRE_EXEC = "PRE_EXEC"
    POST_EXEC = "POST_EXEC"

class ActionTypeEnum(StrEnum):
    DUMP_ENV = "dump_env"
    NETWORK_CAPTURE = "network_capture"
    DUMP_KERBEROS = "dump_kerberos"
    EXEC_COMMAND = "exec_command"
    OUTPUT_CAPTURE = "output_capture"

class TriggerTypeEnum(StrEnum):
    COMMAND = "command"
    REGEX = "regex"
    PARAMETER = "parameter"
    ENV_VAR = "env_var"
    TRIGGER = "trigger"

class SentinelActionRunner:
    ACTION_MODE_MAP = {
        ActionTypeEnum.DUMP_ENV: [ModeEnum.POST_EXEC],
        ActionTypeEnum.NETWORK_CAPTURE: [ModeEnum.PRE_EXEC, ModeEnum.POST_EXEC],
        ActionTypeEnum.DUMP_KERBEROS: [ModeEnum.POST_EXEC],
        ActionTypeEnum.EXEC_COMMAND: [ModeEnum.POST_EXEC],
        # POST_EXEC only: the window this action copies does not exist until the
        # command ended and the hook printed its end marker.
        ActionTypeEnum.OUTPUT_CAPTURE: [ModeEnum.POST_EXEC],
    }

    def __init__(self, mode: str, artifact_id: str):
        self.mode: ModeEnum = ModeEnum(mode)  # PRE_EXEC or POST_EXEC
        self.artifact_id = artifact_id
        # Use a real path for artifacts, but allow tests to override it via monkeypatching ARTIFACTS_BASE_DIR
        self.artifact_dir = ARTIFACTS_BASE_DIR / artifact_id
        # One release per runner invocation. Also keeps the degradation log to a
        # single line on a filesystem that refuses the punch.
        self._session_released = False

        # Configure logging
        self.logger = logging.getLogger(f"SentinelActionRunner.{self.artifact_id}")
        self.logger.setLevel(logging.DEBUG)
        if os.environ.get("SENTINEL_DEBUG_LOG") and not self.logger.handlers:
            try:
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(DEBUG_LOG_PATH)
                formatter = logging.Formatter(f'[%(asctime)s] [{self.artifact_id}-{self.mode}] %(levelname)s: %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
            except Exception:
                pass
        if not self.logger.handlers:
            self.logger.addHandler(logging.NullHandler())

        self.config = self._load_config()
        # User command
        self.command = get_env_safe("LOG_COMMAND")
        # Resolved command
        self.command_raw = get_env_safe("LOG_COMMAND_RAW")
        self.env = dict(os.environ)

        # Parse command for inline env vars, executables and arguments
        parsed_env, self.parsed_commands, self.parsed_args = self._parse_shell_command(self.command_raw or self.command)

        self.logger.debug(f"Parsed command from: {self.command_raw}")
        self.logger.debug(f"Parsed command: {self.parsed_commands}")
        self.logger.debug(f"Parsed args: {self.parsed_args}")
        self.logger.debug(f"Parsed env vars from CLI: {parsed_env}")

        # Merge inline env vars (they take precedence)
        self.env.update(parsed_env)

        self._trigger_cache: Dict[str, Union[asyncio.Task, asyncio.Future[bool]]] = {}
        # exec_command child processes still in flight, so a stop signal can be
        # propagated to their process groups on shutdown.
        self._active_children: Set[Any] = set()
        self._terminating = False

    @staticmethod
    def _parse_shell_command(command_raw: str):
        """
        Parse a shell command string to extract environment variables,
        executables, and arguments.
        """
        env: Dict[str, str] = dict()
        commands: Set[str] = set()
        args: Set[str] = set()

        if not command_raw:
            return env, commands, args

        try:
            # Pre-process to handle semicolons as tokens
            tokens = shlex.split(command_raw.replace(';', ' ; '), comments=True)
        except ValueError:
            # Fallback for unbalanced quotes
            tokens = command_raw.replace(';', ' ; ').split()

        interpreters = {"python", "python2", "python3", "bash", "zsh", "sh", "pwsh", "powershell", "ruby", "perl", "php", "java"}
        intermediate_commands = {"sudo", "grc", "proxychains", "proxychains4"}

        is_new_command = True
        for i, token in enumerate(tokens):
            # Check for command separators
            if token in (';', '&&', '||', '|'):
                is_new_command = True
                continue

            # Check for env var assignment (VAR=val)
            if '=' in token and is_new_command:
                parts = token.split('=', 1)
                key = parts[0]
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                    val = parts[1]
                    # Remove trailing semicolon if it's there
                    if val.endswith(';'):
                        val = val[:-1]
                    env[key] = val
                    continue

            # If it's not an assignment and we are expecting a command
            if is_new_command:
                commands.add(token)

                # Special case for intermediate command like 'sudo', it's often followed by another command.
                # If the command is intermediate, is_new_command = True and the next argument will be registered as a command
                if token in intermediate_commands:
                    is_new_command = True
                    continue

                # Handle interpreters (python, bash, etc.) and venv pythons
                is_interpreter = False
                token_path = Path(token)
                if token_path.name in interpreters or token_path.name.startswith("python3."):
                    is_interpreter = True
                    # If it's a full path, also add the name only (e.g. /usr/bin/python3 -> python3)
                    if len(token_path.parts) > 1:
                        commands.add(token_path.name)

                if is_interpreter:
                    # Look for the next token that doesn't start with '-'
                    for next_token in tokens[i+1:]:
                        if next_token in (';', '&&', '||', '|'):
                            break
                        if not next_token.startswith('-'):
                            # This is likely the script/command
                            commands.add(next_token)
                            # Also add filename only if it's a path (contains slashes)
                            # Path(nt).name works even for "./script.py" or "script.py"
                            nt_path = Path(next_token)
                            commands.add(nt_path.name)
                            try:
                                commands.add(str(nt_path.expanduser().resolve()))
                            except Exception:
                                pass
                            break
                    # We continue because the interpreter itself is a command,
                    # but we are still in the "arguments" of the interpreter for the rest of the tokens
                    is_new_command = False
                else:
                    is_new_command = False
            else:
                args.add(token)

        return env, commands, args

    def _load_config(self) -> Optional[Dict]:
        if not CONFIG_PATH.exists():
            self.logger.debug(f"Config file not found at {CONFIG_PATH}")
            return None
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                config = json.load(f)
                self.logger.debug(f"Config loaded successfully from {CONFIG_PATH}")
                return config
        except Exception as e:
            self.logger.error(f"Failed to load config from {CONFIG_PATH}: {e}")
            return None

    async def _check_trigger(self, trigger: Optional[Dict], trigger_name: Optional[str] = None) -> bool:
        if trigger_name:
            if trigger_name == "always":
                self.logger.debug("Trigger 'always' matched")
                return True
            if trigger_name == "never":
                self.logger.debug("Trigger 'never' did not match")
                return False
            if trigger_name in self._trigger_cache:
                res = await self._trigger_cache[trigger_name]
                self.logger.debug(f"Trigger '{trigger_name}' result from cache: {res}")
                return res

            # Place a resolved-False future in the cache before creating the real task.
            # This breaks cycles: if trigger A references B and B references A, B's
            # lookup of A hits this sentinel and returns False instead of deadlocking.
            cycle_breaker: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
            cycle_breaker.set_result(False)
            self._trigger_cache[trigger_name] = cycle_breaker

            # Use a wrapper to ensure we store the task in the cache
            # before it might be awaited elsewhere.
            task = asyncio.create_task(self._check_trigger_logic(trigger))
            self._trigger_cache[trigger_name] = task
            res = await task
            self.logger.debug(f"Trigger '{trigger_name}' evaluated: {res}")
            return res

        if trigger is None:
            return False
        return await self._check_trigger_logic(trigger)

    async def _check_trigger_logic(self, trigger: Optional[Dict]) -> bool:
        if trigger is None:
            return False
        if self.config is None:  # explicit guard
            raise RuntimeError("Runner config is missing. Trigger cannot be checked")
        if TriggerTypeEnum.COMMAND in trigger:
            options = trigger[TriggerTypeEnum.COMMAND]
            name = options.get("name", "")
            ignore_extension = options.get("ignore_extension", False)
            if not name: return False

            names = [name] if isinstance(name, str) else name

            # Match on any of the parsed commands
            for cmd_path in self.parsed_commands:
                check_cmd = cmd_path
                if ignore_extension:
                    check_cmd = str(Path(cmd_path).with_suffix(''))

                for n in names:
                    if check_cmd == n or Path(check_cmd).name == n:
                        return True
            return False
        elif TriggerTypeEnum.REGEX in trigger:
            options = trigger[TriggerTypeEnum.REGEX]
            pattern = options.get("pattern", "")
            ignore_case = options.get("ignore_case", False)
            flags = re.IGNORECASE if ignore_case else 0
            # Check both command and command_raw
            res = False
            if self.command:
                res = res or re.search(pattern, self.command, flags) is not None
            if self.command_raw:
                res = res or re.search(pattern, self.command_raw, flags) is not None
            return res
        elif TriggerTypeEnum.PARAMETER in trigger:
            options = trigger[TriggerTypeEnum.PARAMETER]
            argument = options.get("argument", "")
            if not argument: return False
            # Check in parsed args or in the raw command string
            if argument in self.parsed_args:
                return True
            return argument in self.command if self.command else False
        elif TriggerTypeEnum.ENV_VAR in trigger:
            options = trigger[TriggerTypeEnum.ENV_VAR]
            variable = options.get("variable", "")
            if isinstance(variable, list):
                return any(v in self.env for v in variable)
            return variable in self.env
        elif TriggerTypeEnum.TRIGGER in trigger:
            options = trigger[TriggerTypeEnum.TRIGGER]
            operator = options.get("operator", "AND")
            triggers = options.get("triggers", [])

            tasks = []
            for t_item in triggers:
                if isinstance(t_item, str):
                    # Referenced trigger by name
                    t_data = self.config.get("triggers", {}).get(t_item)
                    if t_data:
                        tasks.append(self._check_trigger(t_data, t_item))
                elif isinstance(t_item, dict):
                    if "trigger" in t_item:
                        # Referenced trigger by name in a dict: {trigger: "name"}
                        name = t_item["trigger"]
                        t_data = self.config.get("triggers", {}).get(name)
                        if t_data:
                            tasks.append(self._check_trigger(t_data, name))
                    else:
                        # Anonymous/Inline trigger
                        tasks.append(self._check_trigger(t_item))

            if not tasks:
                return False

            results = await asyncio.gather(*tasks)
            return all(results) if operator == "AND" else any(results)
        return False

    async def run(self):
        """Drive one runner pass, releasing the session region no matter what.

        The finally is the backstop: anything raising mid-pass (a bad regex in a
        trigger, a malformed ``actions`` node) used to skip the release entirely.
        The explicit calls inside the pass are kept and not redundant — they free
        a finished command's bytes BEFORE the long ``gather`` rather than after
        it; ``_session_released`` then makes this one a no-op.
        """
        try:
            await self._run_inner()
        finally:
            self._release_session_region()

    async def _run_inner(self):
        if not self.config:
            self.logger.debug("No config loaded, skipping run")
            if self.mode == ModeEnum.POST_EXEC:
                # Remove the empty artifact directory. ignore_errors is load-bearing:
                # rmtree raises FileNotFoundError when the directory is absent, and a
                # fast command reaches POST_EXEC before PRE_EXEC created it. The raise
                # would skip the release below.
                shutil.rmtree(self.artifact_dir, ignore_errors=True)
                # The logger exports the offsets unconditionally, so a window exists
                # even with no config: release here too, or this path never frees it.
                self._release_session_region()
            return

        self.logger.info(f"Starting runner in {self.mode} mode")
        # Forward a stop signal to in-flight exec_command process groups.
        self._install_signal_handlers()
        profile_data = self.config.get("profile", {})
        triggers_map = self.config.get("triggers", {})
        actions_map = self.config.get("actions", {})

        triggered_actions_data: List[Tuple[str, Dict]] = []

        # Get all actions compatible with current mode
        compatible_action_names = set()
        for a_name, a_data in actions_map.items():
            # a_data should now have the format {ActionTypeEnum: options}
            for a_type in ActionTypeEnum:
                if a_type in a_data:
                    if self.mode in self.ACTION_MODE_MAP.get(a_type, []):
                        compatible_action_names.add(a_name)
                    break

        rules_to_check = []
        for rule in profile_data.get("rules", []):
            rule_actions = rule.get("actions", [])
            # Skip rule if no action is compatible with current mode
            if not any(a_name in compatible_action_names for a_name in rule_actions):
                continue
            rules_to_check.append(rule)

        async def check_rule(rule):
            rule_triggers = rule.get("triggers", [])
            tasks = []
            operator = "AND"

            if isinstance(rule_triggers, list):
                # Format: triggers: ["ref1", "ref2"]
                for t_name in rule_triggers:
                    if t_name in ["always", "never"]:
                        tasks.append(self._check_trigger(None, t_name))
                        continue
                    t_data = triggers_map.get(t_name)
                    if t_data:
                        tasks.append(self._check_trigger(t_data, t_name))
            elif isinstance(rule_triggers, dict):
                # Format: triggers: { operator: OR, refs: ["ref1", "ref2"] }
                operator = rule_triggers.get("operator", "AND")
                refs = rule_triggers.get("refs", [])
                for t_name in refs:
                    if t_name in ["always", "never"]:
                        tasks.append(self._check_trigger(None, t_name))
                        continue
                    t_data = triggers_map.get(t_name)
                    if t_data:
                        tasks.append(self._check_trigger(t_data, t_name))

            if not tasks:
                return False

            results = await asyncio.gather(*tasks)
            return all(results) if operator == "AND" else any(results)

        # Check all relevant rules in parallel
        rule_results = await asyncio.gather(*(check_rule(r) for r in rules_to_check))

        for rule, is_triggered in zip(rules_to_check, rule_results):
            if is_triggered:
                self.logger.debug(f"Rule triggered: {rule}")
                for a_name in rule.get("actions", []):
                    if a_name in compatible_action_names:
                        a_data = actions_map.get(a_name)
                        # Keep the name for exec_<name>.json; dedup by value (first name wins).
                        if a_data and a_data not in [d for _, d in triggered_actions_data]:
                            triggered_actions_data.append((a_name, a_data))

        self.logger.info(f"Triggered {len(triggered_actions_data)} actions")

        # Create the artifact directory; chmod since mkdir(mode=...) is umask-masked, and
        # use ARTIFACT_DIR_CHMOD to keep the inherited setgid bit.
        if not self.artifact_dir.exists():
            try:
                ARTIFACTS_BASE_DIR.mkdir(parents=True, exist_ok=True, mode=ARTIFACT_DIR_MODE)
                self.artifact_dir.mkdir(parents=True, exist_ok=True, mode=ARTIFACT_DIR_MODE)
                os.chmod(self.artifact_dir, ARTIFACT_DIR_CHMOD)
            except Exception:
                pass
            # Last, and in its own handler: this chmod is the operation least likely
            # to succeed here (EPERM/EROFS on the bind mount), and inside the block
            # above a single raise from it would skip the mkdirs entirely, leaving no
            # artifact directory at all. A best-effort mode correction must never
            # prevent the directory every action writes into from existing.
            try:
                os.chmod(ARTIFACTS_BASE_DIR, ARTIFACT_DIR_CHMOD)
            except OSError:
                pass

        if triggered_actions_data:
            # In POST_EXEC, wait for PRE_EXEC only if a PRE_EXEC-capable action exists.
            if self.mode == ModeEnum.POST_EXEC and self._has_pre_exec_action():
                self._wait_for_pre_exec()

            # The output decision runs first and alone: output_capture handlers are
            # synchronous, so the copy is done before anything else starts and the
            # release below happens WHILE a long action of the same pass runs. Releasing
            # after the gather would let one unlimited exec_command hold a finished
            # command's gigabyte for as long as it lives.
            output_actions = [(a_name, a_data) for a_name, a_data in triggered_actions_data
                              if ActionTypeEnum.OUTPUT_CAPTURE in a_data]
            other_actions = [(a_name, a_data) for a_name, a_data in triggered_actions_data
                             if ActionTypeEnum.OUTPUT_CAPTURE not in a_data]
            for a_name, a_data in output_actions:
                await self._execute_action(a_name, a_data)
            self._release_session_region()

            # Run the remaining actions concurrently and wait for all of them before
            # exiting. Only exec_command actually yields (at its subprocess), so long
            # commands run in parallel instead of blocking the others.
            if other_actions:
                await asyncio.gather(
                    *(self._execute_action(a_name, a_data) for a_name, a_data in other_actions)
                )
        else:
            # No rule matched: the output decision is "capture nothing", but the
            # release still happens. The session file grows for every command as soon as
            # the recorder is active, so tying the release to a matched output_capture
            # would leave the common case never freeing anything.
            self._release_session_region()

        # Signal completion for this mode
        if self.mode == ModeEnum.PRE_EXEC:
            self._signal_completion()
        else:
            # POST_EXEC: remove PRE_EXEC bookkeeping files, then the directory if now empty.
            for _f in (".pre_exec_pid", ".pre_exec_done"):
                (self.artifact_dir / _f).unlink(missing_ok=True)
            try:
                self.artifact_dir.rmdir()
            except OSError:
                pass  # non-empty means an action wrote real artifacts; keep it

    async def _execute_action(self, name: str, action: Dict):
        self.logger.debug(f"Executing action: {action}")
        if ActionTypeEnum.DUMP_ENV in action:
            self._action_dump_env(action[ActionTypeEnum.DUMP_ENV])
        elif ActionTypeEnum.NETWORK_CAPTURE in action:
            self._action_network_capture(action[ActionTypeEnum.NETWORK_CAPTURE])
        elif ActionTypeEnum.DUMP_KERBEROS in action:
            self._action_dump_kerberos(action[ActionTypeEnum.DUMP_KERBEROS])
        elif ActionTypeEnum.EXEC_COMMAND in action:
            await self._action_exec_command(name, action[ActionTypeEnum.EXEC_COMMAND])
        elif ActionTypeEnum.OUTPUT_CAPTURE in action:
            self._action_output_capture(name, action[ActionTypeEnum.OUTPUT_CAPTURE])

    def _action_dump_env(self, params: Dict):
        if self.mode != ModeEnum.POST_EXEC:
            return
        output_file = self.artifact_dir / "env_vars.json"

        # Load existing data if file exists (merge)
        current_data = {}
        if output_file.exists():
            try:
                with output_file.open("r", encoding="utf-8") as f:
                    current_data = json.load(f)
            except Exception:
                pass

        # Allowlist: keep env vars matching any glob; empty/absent => dump all.
        # fnmatchcase stays case-sensitive and OS-independent, like POSIX env names.
        filters = params.get("filters", [])
        if filters:
            data_to_save = {
                k: v for k, v in self.env.items()
                if any(fnmatch.fnmatchcase(k, pat) for pat in filters)
            }
        else:
            data_to_save = dict(self.env)  # defensive copy (avoid aliasing self.env)

        # Denylist: mask the value (keep the key) of selected vars matching env_redact.
        # Each hop is coalesced so a present-but-null node cannot raise AttributeError.
        env_redact = ((((self.config or {}).get("profile") or {}).get("config") or {}).get("env_redact")) or []
        if env_redact:
            data_to_save = {
                k: (REDACTED if any(fnmatch.fnmatchcase(k, pat) for pat in env_redact) else v)
                for k, v in data_to_save.items()
            }

        current_data.update(data_to_save)
        if len(current_data) == 0:
            # Dont save empty env vars file
            return

        try:
            with output_file.open("w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2)
            set_artifact_file_mode(output_file)
        except Exception:
            pass

    def _action_network_capture(self, params: Dict):
        interface = params.get("interface", "any")
        duration = params.get("duration") # in seconds

        # Use a safe name for the capture file based on parameters
        pcap_name = f"capture_{interface}"
        if duration:
            pcap_name += f"_{duration}"

        pid_file = self.artifact_dir / f".{pcap_name}.pid"
        pcap_file = self.artifact_dir / f"{pcap_name}.pcap"

        if self.mode == ModeEnum.PRE_EXEC:
            # Start tcpdump
            cmd = ["tcpdump", "-i", interface, "-w", str(pcap_file)]
            if duration:
                cmd.extend(["-G", str(duration), "-W", "1"])

            try:
                # Run in background
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with pid_file.open("w") as f:
                    f.write(str(proc.pid))
            except Exception:
                pass

        elif self.mode == ModeEnum.POST_EXEC:
            if not duration: # If duration was set, tcpdump might already be stopped
                if pid_file.exists():
                    try:
                        with pid_file.open("r") as f:
                            pid = int(f.read().strip())
                        os.kill(pid, signal.SIGTERM)
                        # Wait a bit for it to finish
                        for _ in range(10):
                            if not self._is_process_running(pid):
                                break
                            time.sleep(0.1)
                        pid_file.unlink()
                    except Exception:
                        pass
            # tcpdump created the pcap with its own umask: re-assert the artifact mode.
            if pcap_file.exists():
                set_artifact_file_mode(pcap_file)

    def _action_dump_kerberos(self, params: Dict):
        if self.mode != ModeEnum.POST_EXEC:
            return

        ccache_files: List[Path] = []
        # 1. Look for KRB5CCNAME in environment (already contains merged inline vars)
        krb5ccname = self.env.get("KRB5CCNAME")
        if krb5ccname:
            if krb5ccname.startswith("FILE:"):
                ccache_files.append(Path(krb5ccname[5:]))
            else:
                ccache_files.append(Path(krb5ccname))

        # 2. Fallback: Look for kerberos ccache files in /tmp
        if not ccache_files:
            ccache_pattern = re.compile(r"krb5cc_\d+")
            tmp_dir = Path("/tmp")
            try:
                for item in tmp_dir.iterdir():
                    if ccache_pattern.match(item.name):
                        ccache_files.append(item)
            except Exception:
                pass

        for item in ccache_files:
            if item.exists() and item.is_file():
                target = self.artifact_dir / item.name
                try:
                    with item.open("rb") as f_src, target.open("wb") as f_dst:
                        f_dst.write(f_src.read())
                    set_artifact_file_mode(target)
                except Exception:
                    pass

    def _build_scrubbed_env(self) -> Dict[str, str]:
        """Return self.env without sentinel plumbing (``LOG_*``, ``SENTINEL_*``, ``ARTIFACT_ID``)."""
        env = dict(self.env)
        for key in list(env.keys()):
            if key.startswith("LOG_") or key.startswith("SENTINEL_") or key == "ARTIFACT_ID":
                del env[key]
        return env

    async def _action_exec_command(self, name: str, params: Dict):
        """Run a profile-defined command through zsh and save a JSON manifest (POST_EXEC only).

        The command runs in its own session so the whole process group can be killed on timeout.
        zsh is non-interactive (``-i`` would load ZLE plugins that pollute stderr without a TTY);
        ``~/.zshrc`` is sourced explicitly and the command is ``eval``'d as ``$1`` afterwards so
        aliases expand. The command is a positional argument, never interpolated.
        """
        if self.mode != ModeEnum.POST_EXEC:
            return
        command = params.get("command", "")
        if not command:
            return

        # Both limits are coerced before the spawn: the runner re-validates none of
        # the deployed config (see DEFAULT_TEXT_CAPTURE_CAP), so a bad value must not
        # raise after the child exists — it would be misreported as a spawn_error, or
        # kill the runner and every other action of the command. bool is excluded
        # explicitly (it subclasses int, so `timeout: true` would mean a 1s cap).
        # timeout: absent/None/0 => unlimited; a positive value caps this action.
        raw_timeout = params.get("timeout")
        timeout = (raw_timeout if isinstance(raw_timeout, int)
                   and not isinstance(raw_timeout, bool) and raw_timeout > 0 else None)
        if raw_timeout is not None and timeout is None and raw_timeout != 0:
            self.logger.debug(
                f"exec_command: ignoring unusable timeout {raw_timeout!r}; running unlimited"
            )
        # max_output in bytes. An explicit 0 means unlimited (a choice); an unusable
        # value falls back to the default, never to "no cap", so a config we could not
        # read cannot make the manifest unbounded. Absent/None keeps meaning default.
        # The output is already in memory here, so unlimited only skips a slice.
        raw_max_out = params.get("max_output")
        if isinstance(raw_max_out, int) and not isinstance(raw_max_out, bool) and raw_max_out >= 0:
            max_out = raw_max_out or None  # 0 -> None == unlimited
        else:
            max_out = DEFAULT_EXEC_MAX_OUTPUT
            if raw_max_out is not None:
                self.logger.debug(
                    f"exec_command: ignoring unusable max_output {raw_max_out!r}; "
                    f"capping at {max_out} bytes"
                )

        child_env = self._build_scrubbed_env()
        home = os.path.expanduser("~") or "/root"
        shell = shutil.which("zsh") or "/usr/bin/zsh"

        timed_out = False
        exit_code: Optional[int] = None
        stdout_b = b""
        stderr_b = b""
        spawn_error: Optional[str] = None
        start = time.monotonic()

        proc = None
        try:
            # Source the rc, then eval the command ($1) so aliases expand.
            wrapper = 'zshrc="${ZDOTDIR:-$HOME}/.zshrc"; [ -f "$zshrc" ] && source "$zshrc"; eval "$1"'
            proc = await asyncio.create_subprocess_exec(
                shell, "-c", wrapper, "sentinel_exec_command", command,
                stdin=subprocess.DEVNULL,          # never block on input
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=home,
                env=child_env,
                start_new_session=True,            # own process group -> killpg reaps the tree
            )
            # Register so a stop signal can be forwarded to this group.
            self._active_children.add(proc)
            try:
                if timeout is not None and timeout > 0:
                    stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                else:
                    # Unlimited: run to completion (or until a stop signal).
                    stdout_b, stderr_b = await proc.communicate()
                exit_code = proc.returncode
            except asyncio.TimeoutError:
                timed_out = True
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
                # Bound the post-kill drain: a child that escaped the process group
                # can keep the pipe open forever.
                try:
                    stdout_b, stderr_b = await asyncio.wait_for(
                        proc.communicate(), timeout=DEFAULT_EXEC_DRAIN_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    stdout_b, stderr_b = b"", b""  # escaped child holds the pipe; give up
                exit_code = proc.returncode
            finally:
                self._active_children.discard(proc)
        except Exception as e:
            spawn_error = f"failed to spawn command: {e}"

        duration_ms = int((time.monotonic() - start) * 1000)
        # max_out is None when the action asked for no cap (max_output: 0).
        truncated = max_out is not None and (len(stdout_b) > max_out or len(stderr_b) > max_out)

        manifest: Dict[str, Any] = {
            "command": command,
            "stdout": (stdout_b if max_out is None else stdout_b[:max_out]).decode("utf-8", "replace"),
            "stderr": (stderr_b if max_out is None else stderr_b[:max_out]).decode("utf-8", "replace"),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "truncated": truncated,
            "duration_ms": duration_ms,
        }
        if spawn_error is not None:
            manifest["spawn_error"] = spawn_error

        # Sanitize the action name so it cannot escape artifact_dir (e.g. "../../evil").
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        output_file = self.artifact_dir / f"exec_{safe_name}.json"
        try:
            with output_file.open("w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            set_artifact_file_mode(output_file)
        except Exception:
            pass

    def _output_window(self) -> Optional[Tuple[str, int, int]]:
        """Return ``(session_path, start, end)`` for this command's window, or None.

        The offsets come from ``sentinel_logger``'s backward marker scan, passed in
        the runner's environment. They are the only source: a guessed offset
        produces a plausible artifact of the wrong bytes, so absent, empty or
        non-integer values mean "no window".

        Read from ``os.environ``, not ``self.env``: the latter merges the inline
        ``VAR=value cmd`` assignments off the user's own command line, which would
        let an operator pick their own window with ``SENTINEL_OUT_END=0 <command>``.
        """
        # The path decides which file is read and which one gets a hole punched, so
        # it is confined to the 0700 session directory by validated_session_path
        # whatever route the value arrived by.
        path = validated_session_path(get_env_safe("SENTINEL_SESSION_LOG"))
        raw_start = get_env_safe("SENTINEL_OUT_START")
        raw_end = get_env_safe("SENTINEL_OUT_END")
        if not path or not raw_start or not raw_end:
            return None
        try:
            start = int(raw_start)
            end = int(raw_end)
        except ValueError:
            return None
        if start < 0 or end < start:
            return None
        return path, start, end

    def _copy_window_raw(self, stream, data_file: Path, start: int,
                         cap: Optional[int], mode: str, total: int) -> Dict[str, Any]:
        """Copy the surviving byte ranges of the window verbatim (``format: raw``).

        ``plan_byte_cut`` decides which ranges survive and this only moves bytes, so
        the file on disk always agrees with the manifest offsets. Seeking to the
        planned ranges instead of slicing a buffer keeps the cost O(chunk).
        """
        plan = plan_byte_cut(total, cap, mode)
        written = 0
        with data_file.open("wb") as out:
            for begin, stop in plan.ranges:
                stream.seek(start + begin)
                remaining = stop - begin
                while remaining > 0:
                    chunk = stream.read(min(OUTPUT_COPY_CHUNK, remaining))
                    if not chunk:
                        # The stream ended before the offsets said it would: this is a
                        # PARTIAL capture. Returning it would publish bytes_written <
                        # bytes_total with truncated: false and status "ok", breaking
                        # the documented reconstruction identity. Raise instead, so the
                        # caller records status "error" and drops the partial file.
                        raise OSError(
                            f"session stream ended {remaining} bytes before the window did "
                            f"(wrote {written} of {plan.bytes_total})"
                        )
                    out.write(chunk)
                    written += len(chunk)
                    remaining -= len(chunk)
        return self._output_manifest_fields(plan.bytes_total, written, plan.truncated,
                                            plan.truncated_at_byte, plan.tail_from_byte, mode)

    def _copy_window_text(self, stream, data_file: Path, start: int,
                          cap: Optional[int], mode: str, total: int) -> Dict[str, Any]:
        """Write the CLEANED text of the window (``format: text``).

        Unlike the raw path this reads the window whole: cleaning is not chunk-safe
        (an escape sequence straddling a boundary would survive as visible text)
        and the cap counts cleaned bytes, which requires cleaning all of them.
        ``raw``, the default, keeps the bounded path.

        ``cap`` therefore bounds the artifact, not this read — peak memory is
        bounded only by WINDOW_SCAN_LIMIT.
        """
        stream.seek(start)
        cut = truncate_text_offsets(clean(stream.read(total)), cap, mode)
        payload = cut.text.encode("utf-8")
        with data_file.open("wb") as out:
            out.write(payload)
        return self._output_manifest_fields(cut.bytes_total, len(payload), cut.truncated,
                                            cut.truncated_at_byte, cut.tail_from_byte, mode)

    @staticmethod
    def _output_manifest_fields(bytes_total: int, bytes_written: int, truncated: bool,
                                truncated_at_byte: int, tail_from_byte: Optional[int],
                                mode: str) -> Dict[str, Any]:
        """The size/offset half of the manifest.

        ``tail_from_byte`` is emitted only when a tail was kept: the documented
        reconstruction identity reads an absent key as ``bytes_total``, and a null
        would make that ambiguous.
        """
        fields: Dict[str, Any] = {
            "bytes_total": bytes_total,
            "bytes_written": bytes_written,
            "truncated": truncated,
            "truncated_at_byte": truncated_at_byte,
        }
        if mode in ("tail", "both") and tail_from_byte is not None:
            fields["tail_from_byte"] = tail_from_byte
        return fields

    def _action_output_capture(self, name: str, params: Dict) -> None:
        """Copy this command's terminal output to an artifact, with a manifest.

        POST_EXEC only. Nothing here can touch the operator's command: it already
        ended, and ``max_size`` only slices a byte range of a file nobody waits on.

        The manifest is written on every path, failures included: an artifact
        directory that silently lacks an output file is indistinguishable from a
        command that printed nothing.
        """
        if self.mode != ModeEnum.POST_EXEC:
            return

        # Sanitize the action name before it reaches the filename: it is a config
        # dict key, and "../../evil" would resolve outside artifact_dir.
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        # Normalise the format once; the extension, the copier and the cap guard are
        # all derived from it. Tested separately, an unknown third value ("TEXT", a
        # typo) picked the raw copier and the `.txt` extension at the same time.
        # Reachable because the runner re-validates none of the deployed config.
        raw_fmt = params.get("format")
        fmt = "text" if raw_fmt == "text" else "raw"
        if raw_fmt is not None and raw_fmt != fmt:
            self.logger.debug(
                f"output_capture: unknown format {raw_fmt!r}, treating it as "
                f"{fmt!r} (the only recognised values are 'raw' and 'text')"
            )
        mode = params.get("truncation") or "head"
        # Not the `or DEFAULT` idiom used for max_output: a missing max_size means
        # unlimited, so cap only when the value is positive.
        raw_cap = params.get("max_size")
        cap = raw_cap if isinstance(raw_cap, int) and not isinstance(raw_cap, bool) and raw_cap > 0 else None
        # Defence in depth: the host validator refuses this combination at profile
        # load, but a config deployed before that rule, or edited after deployment,
        # still arrives here uncapped.
        runner_capped = False
        if fmt == "text" and cap is None:
            cap = DEFAULT_TEXT_CAPTURE_CAP
            runner_capped = True
            self.logger.debug(
                "output_capture: format: text with no max_size, capping at "
                f"{cap} bytes (the host validator refuses this combination; this "
                "config predates it or was edited after deployment)"
            )

        # Derived from the normalised fmt, so the extension and the copier cannot
        # disagree about what is in the file.
        data_file = self.artifact_dir / f"output_{safe_name}.{'txt' if fmt == 'text' else 'raw'}"
        manifest: Dict[str, Any] = {
            # A pty is one merged stream; the manifest says so rather than pretending
            # stdout and stderr were separated.
            "stream": "terminal",
            "format": fmt,
            "bytes_total": 0,
            "bytes_written": 0,
            "truncated": False,
            "truncated_at_byte": 0,
            "status": OUTPUT_STATUS_UNAVAILABLE,
        }
        # A proven floor, not the real start: set by the logger when the end marker
        # was found but the command was too loud to reach its start marker. The bytes
        # are ours, but everything before the floor is lost, so the manifest must not
        # read as a complete capture. Absent means the start is exact.
        window_start_is_floor = os.environ.get("SENTINEL_OUT_FLOOR") == "1"

        window = self._output_window()
        if window is not None:
            path, start, end = window
            if window_start_is_floor:
                manifest["start_source"] = "scan_floor"
            stream = None
            try:
                stream = open(path, "rb")
            except OSError as e:
                # Recorder inactive, file already released or unreadable: nothing to
                # copy, so the status stays `unavailable`.
                self.logger.debug(f"output_capture: session stream unavailable: {e}")
            if stream is not None:
                try:
                    with stream:
                        copy = self._copy_window_text if fmt == "text" else self._copy_window_raw
                        manifest.update(copy(stream, data_file, start, cap, mode, end - start))
                    if window_start_is_floor:
                        # Everything before the floor was dropped, cap or no cap, and
                        # `truncated` is the only field a consumer reads to learn the
                        # capture is partial. `truncated_at_byte` describes a cut at
                        # the end and is left alone; `start_source` names this one.
                        manifest["truncated"] = True
                    # Which cap cut this artifact: without it, a profile asking for
                    # `max_size: 1000` and a config that silently got the runner
                    # default produce the same manifest. Emitted only when that
                    # default applied — absence means the profile's cap, or none.
                    if runner_capped and manifest.get("truncated"):
                        manifest["cap_source"] = "runner_default"
                    manifest["status"] = OUTPUT_STATUS_OK
                    set_artifact_file_mode(data_file)
                except Exception as e:
                    # The stream was there and extraction failed: `error`, not
                    # `unavailable`. Drop the partial file rather than leave a
                    # truncated artifact claiming to be whole.
                    self.logger.debug(f"output_capture: extraction failed: {e}")
                    manifest["status"] = OUTPUT_STATUS_ERROR
                    try:
                        data_file.unlink(missing_ok=True)
                    except OSError:
                        pass

        # The manifest carries offsets and counts only. Unlike exec_command, the
        # payload is not embedded: manifests are ingested by the SIEM, payloads stay
        # on disk beside them at ARTIFACT_FILE_MODE.
        manifest_file = self.artifact_dir / f"output_{safe_name}.json"
        try:
            with manifest_file.open("w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            set_artifact_file_mode(manifest_file)
        except Exception as e:
            # A manifest we could not write must not cost the audit event or the
            # other actions of the same command.
            self.logger.debug(f"output_capture: manifest write failed: {e}")

    def _release_session_region(self) -> None:
        """Punch a hole over THIS COMMAND'S window in the session stream.

        ``script`` appends to one session file for the whole life of a shell, so without this
        a single command that printed a gigabyte keeps a gigabyte of the container's /tmp
        allocated until the operator logs out. Punching frees the blocks while leaving the
        apparent size alone, which keeps every offset the logger already handed out valid, and
        it cannot race ``script``'s appends because the released range is already written.

        The range is ``[start, end)``, this command's window, and nothing else. ``end`` grows
        monotonically and the file is shared by every command of the shell, so a ``[0, end]``
        punch let one command zero another's window — and a punched hole reads back as zeros of
        full length, so the copy completed normally and wrote a manifest claiming a faithful
        capture of NUL bytes. It also destroyed the earlier markers a still-pending command
        needs to find its own window.

        The punch is disjoint by construction for every shell the hooks see. A nested
        interactive shell is the case that used to break that: re-sourcing the hooks resolved
        the outer ``script``'s ``SENTINEL_SESSION_LOG`` and emitted the inner shell's markers
        into the same file, so an inner runner punched inside the still-open outer window.
        ``sentinel_nested_record`` now gives such a shell its own ``script`` and its own
        ``session_nested_<pid>.log``, or no stream at all where it cannot start one — never the
        enclosing one. "Nested" is decided by asking whether this shell's parent is the
        ``script`` writing the stream; the older ``$$ != sid`` proxy let ``setsid``,
        ``sudo -i`` and ``screen`` through.

        Not covered: a process reaching this pty without re-sourcing the hooks (``tmux``,
        ``ssh``, a hand-run ``script``) cannot be asked the question at all. Attribution breaks
        there but nothing punches. Both that and the reparented-shell case are published
        limitations.

        The enclosing command's window stays faithful: the outer ``script`` still records every
        byte the inner pty displays, so an ``output_capture`` on a command that is itself an
        interactive shell captures the whole inner session. The nested file is windowed,
        released and cleaned up by that shell's own ``script`` and ``sentinel_nested_cleanup``.

        The inter-window filler is released too — with ZLE redrawing (history search, a fuzzy
        finder repainting per keystroke) it is proportional to typing, not to the number of
        commands, and reached 5 GB in a measured session. See find_filler_start for why
        ``[previous end marker, our start)`` is disjoint from every window.

        Still not reclaimed: any command whose window was never located (over
        WINDOW_SCAN_LIMIT, or a missing marker). No offsets means no punch.

        Called once per runner invocation, as soon as the output decision is made.
        Never at exit: a POST_EXEC pass may still be running an unlimited
        ``exec_command``, and the finished command's bytes must not wait for it.
        """
        if self.mode != ModeEnum.POST_EXEC or self._session_released:
            return
        self._session_released = True

        window = self._output_window()
        if window is None:
            # No path, or no parseable offsets: the logger found no window. The file
            # is shared by every command of the session, so punching a guessed range
            # would zero bytes another window still needs.
            return
        path, start, end = window

        # The inter-window filler (prompt, echoed command line, ZLE redraws), released
        # alongside our own window: `[filler, start)` is provably nobody's window — see
        # find_filler_start — and the walk stops at the first marker, so FILLER_SCAN_LIMIT is a
        # ceiling, not a cost. Best effort and silent: reclamation, not audit, so a failure
        # here must not cost the command its own release below. It stops short of our own start
        # marker, in the 42 bytes just before `start`, because a zeroed marker reads back as
        # NUL and is indistinguishable from one never emitted.
        try:
            with open(path, "rb") as fh:
                filler = find_filler_start(fh, start)
        except OSError:
            filler = None
        if filler is not None:
            filler_end = start - MARKER_LEN
            if filler < filler_end:
                punch_hole(path, filler, filler_end - filler)

        if punch_hole(path, start, end - start):
            return

        # Degrade to grow-until-session-end. Logged once per invocation and never
        # retried: on a filesystem with no punch-hole support, a per-command warning
        # would grow a second unbounded file while trying to bound the first. The
        # residual growth is bounded by the session lifecycle spawn.sh owns.
        err = last_punch_errno()
        reason = os.strerror(err) if err else "unknown"
        self.logger.debug(
            f"output release: punch_hole failed on {path} (errno {err}: {reason}); "
            f"degrading to grow-until-session-end"
        )

    def _install_signal_handlers(self) -> None:
        """Forward SIGTERM/SIGINT to in-flight exec_command process groups, then SIGKILL after a grace.

        Silently skipped where the event loop cannot install signal handlers.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._on_termination_signal, sig)
            except (NotImplementedError, RuntimeError, ValueError):
                pass  # best-effort: not supported here

    def _on_termination_signal(self, sig) -> None:
        """Signal-handler callback: forward the stop signal to exec_command children."""
        self._terminating = True
        self.logger.info(
            f"Received signal {int(sig)}; forwarding to "
            f"{len(self._active_children)} exec_command child(ren)"
        )
        self._signal_children(sig)
        # Escalate to SIGKILL for any child that ignores the graceful signal.
        try:
            loop = asyncio.get_running_loop()
            loop.call_later(EXEC_TERMINATION_GRACE_SEC, self._kill_children)
        except RuntimeError:
            self._kill_children()

    def _signal_children(self, sig) -> None:
        """Send ``sig`` to the process group of every in-flight exec_command child."""
        for proc in list(self._active_children):
            try:
                os.killpg(os.getpgid(proc.pid), sig)
            except Exception:
                pass

    def _kill_children(self) -> None:
        """SIGKILL any exec_command child still alive after the grace period."""
        for proc in list(self._active_children):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

    def _has_pre_exec_action(self) -> bool:
        """Return True iff at least one configured action is PRE_EXEC-capable (else POST_EXEC need not wait)."""
        # Coalesce: "actions" may be present but null.
        actions_map = (self.config or {}).get("actions") or {}
        for a_data in actions_map.values():
            for a_type in ActionTypeEnum:
                if a_type in a_data and ModeEnum.PRE_EXEC in self.ACTION_MODE_MAP.get(a_type, []):
                    return True
        return False

    def _wait_for_pre_exec(self) -> None:
        """PID-based two-phase wait for the PRE_EXEC sibling process.

        Phase 1 (startup window): poll for ``.pre_exec_pid`` for ~250ms; if absent, return.
        Phase 2 (completion window): poll the PID every 50ms until it exits or 5s elapse.
        ``SENTINEL_SKIP_WAIT`` disables the wait (tests).
        """
        if os.environ.get("SENTINEL_SKIP_WAIT"):
            return

        pid_file = self.artifact_dir / ".pre_exec_pid"

        # Startup window: wait for the PID file to appear (~250ms).
        for _ in range(5):
            if pid_file.exists():
                self.logger.debug("PRE_EXEC process has started")
                break
            time.sleep(0.05)
        else:
            # PID file never appeared: PRE_EXEC crashed -> nothing to wait on.
            self.logger.debug("PRE_EXEC process wasn't found, did it crash ? Resuming execution")
            return

        self.logger.debug("Waiting for PRE_EXEC completion")

        try:
            pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            self.logger.debug("PRE_EXEC process cannot be checked. Resuming execution")
            return

        # Completion window: wait until the process exits, or 5s.
        deadline = time.time() + 5.0
        graceful_end = False
        while time.time() < deadline:
            if not self._is_process_running(pid):
                self.logger.debug("PRE_EXEC process has ended. Resuming execution")
                graceful_end = True
                break
            time.sleep(0.05)

        # Clean up the legacy completion signal if PRE_EXEC left one behind.
        (self.artifact_dir / ".pre_exec_done").unlink(missing_ok=True)
        if not graceful_end:
            self.logger.debug("Wait for PRE_EXEC has timed-out.")

    def _signal_completion(self):
        sig_file = self.artifact_dir / f".{self.mode.lower()}_done"
        try:
            sig_file.touch()
        except Exception:
            pass

    def _is_process_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True


def main():
    if len(sys.argv) < 3:
        return

    mode = sys.argv[1]
    artifact_id = sys.argv[2]

    # PRE_EXEC records its PID first (before config load) so POST_EXEC can track it.
    # Failures are ignored: without a PID file POST_EXEC just does not wait.
    if mode == ModeEnum.PRE_EXEC:
        try:
            ARTIFACTS_BASE_DIR.mkdir(parents=True, exist_ok=True, mode=ARTIFACT_DIR_MODE)
            art_dir = ARTIFACTS_BASE_DIR / artifact_id
            art_dir.mkdir(parents=True, exist_ok=True, mode=ARTIFACT_DIR_MODE)
            # Before any mode work: POST_EXEC observes liveness through this file, so
            # nothing best-effort may precede it. The chmods below sit on the same bind
            # mount and fail the same ways (EPERM/EROFS); ahead of the write, one raise
            # took the liveness signal with it.
            (art_dir / ".pre_exec_pid").write_text(str(os.getpid()))
            # PRE_EXEC is the first writer for an artifact id, so it sets the mode
            # unconditionally: mkdir(mode=...) is umask-masked, chmod is not.
            os.chmod(art_dir, ARTIFACT_DIR_CHMOD)
        except Exception:
            pass
        # Same explicit chmod as the per-command directory: `artifacts/` would
        # otherwise be born 0o700 under `umask 077` and freeze there, and an agent in
        # sentinel_gid cannot traverse it. In its own handler after the block above,
        # so a failure here cannot take the liveness signal with it.
        try:
            os.chmod(ARTIFACTS_BASE_DIR, ARTIFACT_DIR_CHMOD)
        except OSError:
            pass

    runner = SentinelActionRunner(mode, artifact_id)
    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
