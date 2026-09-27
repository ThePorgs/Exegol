"""Schema of a Sentinel audit profile file.

Model docstrings and field descriptions are published in ``schemas/sentinel.schema.json``
and shown in editors: write them for the person editing the YAML.
"""
from typing import Callable, List, Dict, Optional, Union, Literal, Annotated, Any, Tuple, Set, get_args
from pydantic import (Field, ValidationError, Discriminator, Tag, TypeAdapter, field_validator,
                      model_validator, BeforeValidator, WithJsonSchema)

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.YamlConfigLoader import StrictYamlModel
# `logger`, not a raise, for the one advisory below: an oversized inline field is a
# legitimate choice, so it warns. No UserConfig import here — this module is the schema, and
# the machine defaults that back it are read by SentinelProfileManager.
from exegol.utils.ExeLog import logger
from exegol.utils.RegexUtils import is_valid_sentinel_entity_name
from exegol.utils.SizeUtils import SPLUNK_DEFAULT_TRUNCATE, parse_size_to_bytes

# A size in bytes, given as a byte count or a suffixed string; normalised to an integer
# host-side. WithJsonSchema lets the published schema accept the string form (`100MB`).
# Pair with Field(gt=0) at the field site.
SizeBytes = Annotated[
    int,
    BeforeValidator(parse_size_to_bytes),
    WithJsonSchema({
        "anyOf": [
            {"type": "integer", "exclusiveMinimum": 0},
            {"type": "string", "pattern": r"^\s*[0-9]+(\.[0-9]+)?\s*([KMGTkmgt]?[BbOo]?)\s*$"},
        ],
        "description": "A byte count (1048576) or a size string with a binary-unit suffix "
                       "(100MB, 512KB, 2GB). K/M/G/T are powers of 1024.",
    }),
]

# Which end of an over-cap capture survives. Declared once and read by all three surfaces
# that constrain it — `LogOutputConfig.truncation`, `OutputCaptureOptions.truncation` and the
# container profile's typo warner on `sentinel.log_output.truncation` — so a mode added here
# cannot be accepted by one surface and rejected by another.
TruncationMode = Literal["head", "tail", "both"]
#: The same choice set as a plain tuple, for the surfaces that test membership rather than
#: annotate a field. Derived from the type above, never re-typed.
TRUNCATION_MODES: Tuple[str, ...] = get_args(TruncationMode)


def key_discriminator(known: Tuple[str, ...], kind: str) -> Callable[[Any], str]:
    """Build a callable discriminator for a "tagged by which key is present" union.

    Both the trigger and the action unions distinguish their members by the single option key
    the author wrote (``command:``, ``output_capture:``, ...) rather than by a ``type:`` field,
    so pydantic's plain ``Field(discriminator=...)`` -- which reads a literal field -- does not
    apply, and a callable ``Discriminator`` is the supported mechanism.

    Without one the union is tried member by member and every member's failure is reported
    together: a single wrong ``truncation`` value produced eight errors, seven of them about
    action types the author never wrote, with the real one last.

    A miss deliberately returns a tag matching no member, so pydantic answers "Input tag
    '<...>' ... does not match any of the expected tags: ..." and lists the valid keys --
    better than either a member-by-member dump or a bare "unable to extract tag".
    """
    def discriminate(value: Any) -> str:
        if isinstance(value, dict):
            present = [k for k in known if k in value]
        else:
            # Re-validation of an already-built model: tag by the field it carries.
            present = [k for k in known if getattr(value, k, None) is not None]
        if len(present) == 1:
            return present[0]
        if not present:
            return f"<no {kind} key>"
        return f"<{len(present)} {kind} keys on one entry: {', '.join(present)}>"
    return discriminate


def format_validation_error(exc: ValidationError) -> str:
    """Render a ValidationError as a message suffix: one ``loc: message`` per error.

    Returns the separator too, so a single error stays on the caller's own line (the common
    case, now that the unions are discriminated) and several are listed underneath it.

    ``str(ValidationError)`` appends a "For further information visit
    https://errors.pydantic.dev/..." line to every error, which on a profile file doubles the
    height of the diagnostic and pushes the actionable line off the top of the terminal. The
    location and the message are what the author needs; the URL documents pydantic.
    """
    lines = []
    for err in exc.errors():
        # Collapse the discriminator tag pydantic injects into the location of a tagged-union
        # error. Our tags are the option key (Tag("output_capture") on the member whose only
        # field is `output_capture`), so the tag always lands immediately before an identical
        # segment and the raw loc reads `actions.log.output_capture.output_capture.truncation`
        # -- a path that is in no YAML file. Dropping the repeat yields the author's real path.
        parts: List[str] = []
        for part in err.get("loc", ()):
            text = str(part)
            if parts and parts[-1] == text:
                continue
            parts.append(text)
        lines.append(f"{'.'.join(parts) or '<root>'}: {err.get('msg', '')}")
    if not lines:
        return " <no detail>"
    if len(lines) == 1:
        return f" {lines[0]}"
    return "\n" + "\n".join(f"  {line}" for line in lines)


# Trigger models

DEFAULT_TRIGGER_SYSTEM = ["always", "never"]

# Key of the official source namespace, where bare references fall back. Profiles must live
# inside a source directory, not directly under component_path.
DEFAULT_SOURCE_KEY = ConstantConfig.SENTINEL_CORE_SOURCE_KEY


def resolve_reference(ref: str, current_source: str, available: Dict[str, Set[str]]) -> Tuple[str, str]:
    """Resolve a trigger/action reference to a ``(sourcekey, name)`` pair.

    ``sourcekey.name`` forces that source; a bare ``name`` tries ``current_source`` then
    ``core``. ``available`` maps each sourcekey to its names. Raises ``KeyError`` if unresolved.
    """
    if "." in ref:
        source_key, _, name = ref.partition(".")
        names = available.get(source_key)
        if names is not None and name in names:
            return source_key, name
        raise KeyError(f"Unresolvable reference '{ref}': no '{name}' defined under source '{source_key}'")
    # Bare name: current source first, then the official core source.
    if ref in available.get(current_source, set()):
        return current_source, ref
    if ref in available.get(DEFAULT_SOURCE_KEY, set()):
        return DEFAULT_SOURCE_KEY, ref
    raise KeyError(f"Unresolvable reference '{ref}' from source '{current_source}'")

class CommandTriggerOptions(StrictYamlModel):
    """Options of a `command` trigger."""
    name: Union[str, List[str]] = Field(
        description="One executable name, or a list of names any one of which matches. Compared "
                    "against the executable name only, never the whole command line. Every command "
                    "in a pipeline is examined, and both the invoked path and its final component "
                    "are compared.")
    ignore_extension: bool = Field(
        default=False,
        description="Strip the file extension before comparing, so one entry `secretsdump` also "
                    "matches `secretsdump.py`.")

class RegexTriggerOptions(StrictYamlModel):
    """Options of a `regex` trigger."""
    pattern: str = Field(
        description="Python regular expression, SEARCHED against the command line rather than "
                    "anchored to it — no `.*` padding is needed at either end. Quote it in YAML: a "
                    "bare pattern containing ':', '#' or a leading '*' is not the string it looks "
                    "like. Both the command as typed and its alias-resolved, variable-expanded "
                    "spelling are tested, and a match on either one fires.")
    ignore_case: bool = Field(
        default=False,
        description="Apply the case-insensitive flag to the search.")

class ParameterTriggerOptions(StrictYamlModel):
    """Options of a `parameter` trigger."""
    argument: str = Field(
        description="A single argument, matched exactly against the command's parsed arguments. "
                    "Values are never inspected, so `-k` matches that flag wherever it appears. "
                    "When the argument is not a standalone token, a plain substring test against "
                    "the command as typed is used as a fallback.")

class EnvVarTriggerOptions(StrictYamlModel):
    """Options of an `env_var` trigger."""
    variable: Union[str, List[str]] = Field(
        description="One environment-variable name, or a list any one of which matches. This is a "
                    "PRESENCE test: the value is never compared and an empty value still counts as "
                    "set. No globbing on the name.")

class CompositeTriggerOptions(StrictYamlModel):
    """Options of a composite trigger (the `trigger` key)."""
    operator: Literal["AND", "OR"] = Field(
        default="AND",
        description="How the entries combine. AND requires every entry to match, OR requires one. "
                    "Uppercase only.")
    triggers: List[Union[str, Dict[str, str], "Trigger"]] = Field(
        description="Names of triggers defined elsewhere, or inline anonymous triggers written in "
                    "place — including a nested composite. An inline trigger has no name and cannot "
                    "be referenced from anywhere else.")

class TriggerBase(StrictYamlModel):
    """Base class for all triggers to allow isinstance checks"""

class CommandTrigger(TriggerBase):
    """Matches on the executable name of the command."""
    command: CommandTriggerOptions

class RegexTrigger(TriggerBase):
    """Matches a regular expression anywhere in the command line."""
    regex: RegexTriggerOptions

class ParameterTrigger(TriggerBase):
    """Matches when a given argument is present on the command line."""
    parameter: ParameterTriggerOptions

class EnvVarTrigger(TriggerBase):
    """Matches when a given environment variable is set for the command."""
    env_var: EnvVarTriggerOptions

class CompositeTrigger(TriggerBase):
    """Combines other triggers with AND or OR.

    The YAML key is `trigger`, not `composite`: every other type is named after the thing
    it inspects, and this one inspects other triggers. Writing `composite:` is an unknown
    key, which is a hard validation error.
    """
    trigger: CompositeTriggerOptions

# Discriminated on the single option key present, so a malformed trigger reports
# only its own errors instead of all five members'. See key_discriminator.
TRIGGER_KEYS: Tuple[str, ...] = ("command", "regex", "parameter", "env_var", "trigger")
Trigger = Annotated[
    Union[
        Annotated[CommandTrigger, Tag("command")],
        Annotated[RegexTrigger, Tag("regex")],
        Annotated[ParameterTrigger, Tag("parameter")],
        Annotated[EnvVarTrigger, Tag("env_var")],
        Annotated[CompositeTrigger, Tag("trigger")],
    ],
    Discriminator(key_discriminator(TRIGGER_KEYS, "trigger")),
]

# Action models

class DumpEnvOptions(StrictYamlModel):
    """Options of a `dump_env` action."""
    filters: Optional[List[str]] = Field(
        default_factory=list,
        description="ALLOWLIST of variable NAMES, matched with case-sensitive globs (`AWS_*`, "
                    "`*_TOKEN`) and never against values. Quote any pattern beginning with '*': "
                    "unquoted it is a YAML alias node, not a string. Absent or empty, this action "
                    "captures EVERY environment variable in the command's environment, exported "
                    "credentials and session tokens included.")

class NetworkCaptureOptions(StrictYamlModel):
    """Options of a `network_capture` action."""
    interface: str = Field(
        default="any",
        description="Interface passed straight to `tcpdump -i`. `any` captures on every interface "
                    "at once.")
    duration: Optional[int] = Field(
        default=None,
        description="Fixed capture window in seconds. Omit it to capture for as long as the "
                    "matching command runs.")

class DumpKerberosOptions(StrictYamlModel):
    """Options of a `dump_kerberos` action: it takes none."""

class ExecCommandOptions(StrictYamlModel):
    """Options of an `exec_command` action."""
    command: str = Field(
        description="Shell command executed inside the container after the matched command "
                    "finishes, in the operator's own zsh with `~/.zshrc` sourced, so aliases and "
                    "shell functions resolve as they do at the prompt. It is not filtered and not "
                    "confined.")
    timeout: Optional[int] = Field(
        default=None, ge=0,
        description="Seconds to wait before the command's whole process group is killed and the "
                    "artifact records that it was cut short. Omit it, or write 0, for no limit. "
                    "Negative values are refused.")
    max_output: Optional[SizeBytes] = Field(
        default=None, ge=0,
        description="Output cap applied to standard output and standard error SEPARATELY. Beyond "
                    "it, output is dropped and the artifact is flagged as truncated. Omit it for "
                    "the 1 MB default, or write 0 to keep everything. Negative values are refused.")

    @field_validator("timeout", mode="after")
    @classmethod
    def normalise_zero_timeout_to_unlimited(cls, value: Optional[int]) -> Optional[int]:
        """0 and None are the same posture for timeout; ship one of them.

        `max_output` is deliberately not normalised the same way: its absent value is the
        runner's 1 MB default rather than unlimited, so a written 0 has to survive to the
        container to stay distinguishable from an omission. The runner tells the two apart.
        """
        return None if value == 0 else value

class OutputCaptureOptions(StrictYamlModel):
    """Options of an `output_capture` action: a command's terminal output kept as an artifact."""
    format: Literal["raw", "text"] = Field(
        default="raw",
        description="Which bytes land on disk. `raw` is the pty stream verbatim — replayable, "
                    "with colours and control sequences kept. `text` is the same cleaning the "
                    "inline event field applies. There is no combined value: capturing one "
                    "command both ways is two actions on the rule, each with its own file pair "
                    "and manifest.")
    max_size: Optional[SizeBytes] = Field(
        default=None, ge=0,
        description="Cap on the captured payload. Omit it, or write 0, for UNLIMITED — the author "
                    "targeted this command and wants all of it. To keep nothing, do not declare "
                    "the action at all. Negative values are refused.")
    truncation: TruncationMode = Field(
        default="head",
        description="Which end of an over-cap capture survives. Only meaningful alongside "
                    "`max_size`: declaring it without one is refused, because a truncation mode "
                    "that can never fire is a setting the operator believes is protecting them.")

    @field_validator("max_size", mode="after")
    @classmethod
    def normalise_zero_to_unlimited(cls, value: Optional[int]) -> Optional[int]:
        """Collapse ``max_size: 0`` onto the single unlimited representation (None).

        Done once, here, rather than at every read site: the two rules below test
        ``is None`` and so catch a written zero for free, and the container is
        never handed a 0 it would have to know how to reinterpret.
        """
        return None if value == 0 else value

    @model_validator(mode="after")
    def validate_truncation_needs_a_limit(self) -> "OutputCaptureOptions":
        """Refuse ``truncation`` without ``max_size``.

        ``model_fields_set`` is what makes it detectable: it is true only for a key the author
        actually wrote, so a profile spelling out the default is still caught. Testing the
        value would let "truncation: head" pass as absent, and a truncation mode that can
        never fire is a setting the operator believes is protecting them.

        ``max_size is None`` covers a written ``max_size: 0``, already collapsed by
        ``normalise_zero_to_unlimited``: truncating at "unlimited" is exactly the
        never-firing setting this refuses.
        """
        if "truncation" in self.model_fields_set and self.max_size is None:
            raise ValueError(
                "Action option [green]truncation[/green] requires a [green]max_size[/green] limit: "
                "a truncation mode has no meaning without a limit to truncate at, and "
                "[green]max_size: 0[/green] means unlimited just as an absent one does. "
                "Set [green]max_size[/green] to a positive size, or remove [green]truncation[/green] "
                "to capture everything."
            )
        return self

    @model_validator(mode="after")
    def validate_text_format_needs_a_limit(self) -> "OutputCaptureOptions":
        """Refuse ``format: text`` without ``max_size``.

        ``raw`` is chunk-safe: the runner seeks the planned ranges and copies a chunk at a
        time, so an unlimited raw capture never materialises on the heap. ``text`` cannot be --
        cleaning is not chunk-safe (an escape sequence straddling a boundary would survive as
        visible text) and the cap counts cleaned bytes, which requires cleaning all of them --
        so the text path reads the window whole and then multiplies it, for a peak several
        times its size.

        ``max_size`` therefore bounds the artifact, not the read: that cost is what text costs
        at any setting. The rule is kept on its true reason -- text is the one format whose
        cost is not proportional to what it writes, so the author must choose its bound rather
        than inherit a default and have the artifact cut at a size nobody asked for.

        Refused host-side, at profile load, so the operator is told at the one moment they can
        still fix it. ``raw`` is unaffected.
        """
        if self.format == "text" and self.max_size is None:
            raise ValueError(
                "Action option [green]format: text[/green] requires a positive [green]max_size[/green] "
                "([green]max_size: 0[/green] means unlimited, so it does not satisfy this): "
                "cleaning is not chunk-safe, so a text capture is read and cleaned whole "
                "whatever its limit, and the limit is what bounds the artifact it leaves "
                "behind. Choose it explicitly. Set [green]max_size[/green], or use "
                "[green]format: raw[/green], which is copied in bounded chunks and needs no "
                "limit."
            )
        return self

class ActionBase(StrictYamlModel):
    """Base class for all actions to allow isinstance checks"""

class DumpEnvAction(ActionBase):
    """Writes the environment of the matched command into the artifact directory."""
    dump_env: DumpEnvOptions

class NetworkCaptureAction(ActionBase):
    """Runs a packet capture spanning the matched command's execution."""
    network_capture: NetworkCaptureOptions

class DumpKerberosAction(ActionBase):
    """Copies the Kerberos credential cache the matched command used.

    Takes no parameters, but the empty mapping is mandatory: write `dump_kerberos: {}`. A
    bare `dump_kerberos:` is YAML null, which fails validation and drops the whole source.

    The cache comes from `KRB5CCNAME` in the command's environment; when that is unset,
    `/tmp` is scanned for `krb5cc_<digits>` instead.
    """
    dump_kerberos: DumpKerberosOptions = Field(default_factory=DumpKerberosOptions)

class ExecCommandAction(ActionBase):
    """Runs a shell command on the operator's behalf and stores its output.

    This is remote code execution by design: the command runs inside the container every
    time its rule fires, unfiltered and unconfined. Trusting a profile source is trusting
    it to run code in your container.
    """
    exec_command: ExecCommandOptions

class OutputCaptureAction(ActionBase):
    output_capture: OutputCaptureOptions

# Same treatment as Trigger above, and the union the reported noise came from: a
# single bad `truncation` value used to emit eight errors across five action types.
ACTION_KEYS: Tuple[str, ...] = ("dump_env", "network_capture", "dump_kerberos", "exec_command", "output_capture")
Action = Annotated[
    Union[
        Annotated[DumpEnvAction, Tag("dump_env")],
        Annotated[NetworkCaptureAction, Tag("network_capture")],
        Annotated[DumpKerberosAction, Tag("dump_kerberos")],
        Annotated[ExecCommandAction, Tag("exec_command")],
        Annotated[OutputCaptureAction, Tag("output_capture")],
    ],
    Discriminator(key_discriminator(ACTION_KEYS, "action")),
]

TriggerAdapter: TypeAdapter[Trigger] = TypeAdapter(Trigger)
ActionAdapter: TypeAdapter[Action] = TypeAdapter(Action)

# Config models

class LogRotationConfig(StrictYamlModel):
    """Rotation of the event stream, overriding `sentinel.log_rotation` from `~/.exegol/config.yml`.

    These four keys are the whole block. The interval that debounces two consecutive
    rotations is fixed product behaviour, not a tunable: declaring a fifth key fails
    validation and drops the whole source.
    """
    enabled: bool = Field(
        default=True,
        description="Turn rotation of the event stream on or off.")
    max_size: SizeBytes = Field(
        default=100 * 1024 * 1024, ge=0,
        description="Rotate once the event stream grows past this. Defaults to 100MB. 0 means "
                    "NEVER rotate, matching `max_files` below — and rotation is the only bound "
                    "on the event stream, so at 0 it grows until the disk does. Negative values "
                    "are refused.")
    max_files: int = Field(
        default=0, ge=0,
        description="How many rotated generations to keep. 0 keeps all of them; nothing is ever "
                    "deleted.")
    compress: bool = Field(
        default=True,
        description="Gzip each rotated generation.")

class LogOutputConfig(StrictYamlModel):
    """Inline terminal-output capture, overriding `sentinel.log_output` from `~/.exegol/config.yml`.

    These three keys are the whole block, and a profile block replaces the machine default
    WHOLESALE rather than being merged key by key. Note that `enabled` is settable here and
    in `~/.exegol/config.yml` only — a CONTAINER profile can never supply it.
    """
    enabled: bool = Field(
        default=True,
        description="Embed the command's terminal output in every audit event. On by default: "
                    "the event field is the primary destination, the `output_capture` artifact "
                    "action being opt-in.")
    max_size: SizeBytes = Field(
        default=4 * 1024, gt=0,
        description="Cap on the CLEANED UTF-8 text embedded in the event, cut on a character "
                    "boundary. Defaults to 4KB, which keeps the output plus the event metadata "
                    "under the 10000-byte default a stock Splunk truncates at. Must be strictly "
                    "positive: this is the ONE knob here where 0 does not mean unlimited, because "
                    "the field rides on EVERY event — switch the field off with `enabled: false`, "
                    "and use an `output_capture` action to keep a whole window.")
    truncation: TruncationMode = Field(
        default="both",
        description="Which end of an oversized capture to keep. `both` spends half the budget on "
                    "each end and names the dropped byte count in between.")

    @model_validator(mode="after")
    def warn_when_the_inline_field_outgrows_a_default_siem(self) -> "LogOutputConfig":
        """Warn (never refuse) when max_size is large enough to break ingestion.

        Raising this is legitimate -- it is a knob, and an operator who has set `TRUNCATE = 0`
        is entitled to a big inline field. But the failure mode when they have not is silent
        and total: Splunk cuts the event mid-JSON, so the record is destroyed rather than
        shortened, and nothing on the Exegol side reports it. A warning at the moment the value
        is written is the only place that is cheap to act on.

        Guarded on ``model_fields_set`` so it fires only for a value someone actually wrote:
        the shipped 4 KB default, and every internal construction of this model for defaults,
        stay silent.
        """
        if "max_size" in self.model_fields_set and self.max_size >= SPLUNK_DEFAULT_TRUNCATE:
            logger.warning(
                f"sentinel log_output.max_size is {self.max_size} bytes, at or above Splunk's "
                f"default TRUNCATE of {SPLUNK_DEFAULT_TRUNCATE}: this inline field is embedded in "
                f"EVERY audit event, and an indexer left on that default cuts the event mid-JSON "
                f"rather than shortening it. Set [green]TRUNCATE = 0[/green] on the source type, "
                f"or lower this value. To keep a whole command's output instead, use an "
                f"[green]output_capture[/green] action, which writes a separate artifact."
            )
        return self

class ProfileConfig(StrictYamlModel):
    """Optional per-profile settings, alongside `rules:`. Exactly three keys."""
    log_rotation: Optional[LogRotationConfig] = None
    log_output: Optional[LogOutputConfig] = Field(
        default=None,
        description="Inline terminal-output capture for this profile. Omitted, the machine "
                    "default from `sentinel.log_output` in `~/.exegol/config.yml` is backfilled "
                    "host-side, exactly as `log_rotation` is; a block here replaces that default "
                    "WHOLESALE rather than being merged key by key.")
    env_redact: Optional[List[str]] = Field(
        default=None,
        description="DENYLIST of environment-variable NAMES whose VALUES are masked to the literal "
                    "`<REDACTED>` wherever they would be logged — the dump_env artifact and the "
                    "captured environment of the command alike. Matching is case-sensitive and the "
                    "whole name must match, so `KRBTGT*` covers `KRBTGT_SECRET` but a bare `TOKEN` "
                    "covers only the variable named exactly `TOKEN`. Quote any pattern beginning "
                    "with '*'. There is no default: a profile that omits it redacts NOTHING. "
                    "Distinct from dump_env's `filters`, which is an allowlist deciding what is "
                    "collected at all.")

# Profile models

class ProfileRuleTriggers(StrictYamlModel):
    """The long form of a rule's `triggers`, and the only way to get an OR at rule level."""
    operator: Literal["AND", "OR"] = Field(
        default="AND",
        description="How the referenced triggers combine. Uppercase only.")
    refs: List[str] = Field(
        description="Trigger names. A bare name resolves in this profile's own source first, then "
                    "falls back to the official `core` source; an explicit `sourcekey.name` forces "
                    "that source and never searches elsewhere.")

class ProfileRule(StrictYamlModel):
    """One rule: run these actions when these triggers match.

    Rules are evaluated independently against every command, so adding one never changes
    what an existing one collects. Both keys are REQUIRED — misspelling either (`action:`
    for `actions:`) is a missing-required-field error that drops the whole source.
    """
    triggers: Union[List[str], ProfileRuleTriggers] = Field(
        description="A plain list of trigger names (combined with AND), or the long form with an "
                    "explicit `operator` and `refs`.")
    actions: List[str] = Field(
        description="Action names to run when the triggers match. Same resolution rule as triggers: "
                    "own source first, then `core`.")

class Profile(StrictYamlModel):
    """A named audit profile: a list of rules, and optional per-profile settings.

    An unknown EXTRA key at this level is silently ignored, so a stray `confg:` beside a
    valid `rules:` loads a healthy-looking profile that collects nothing. When a profile
    validates but never fires, re-read its own keys first.
    """
    rules: List[ProfileRule] = Field(
        description="Rules, evaluated independently against every command.")
    config: Optional[ProfileConfig] = None

class SentinelConfig(StrictYamlModel):
    """A Sentinel profile file: the triggers, actions and profiles one source declares.

    Each of the three blocks maps a NAME to a definition. Names may contain letters,
    digits, '_' and '-' only, because '.' is the source separator in a `sourcekey.name`
    reference.

    One invalid file takes its ENTIRE source namespace down with it: every profile,
    trigger and action declared by that source disappears and `-S` reports the profile as
    not found, even though the file is visible on disk.
    """

    @field_validator("triggers", mode="after")
    @classmethod
    def validate_trigger_names(cls, v: Dict[str, Trigger]) -> Dict[str, Trigger]:
        for name in v.keys():
            if name.lower() in DEFAULT_TRIGGER_SYSTEM:
                raise ValueError(f"Trigger name [green]{name}[/green] is reserved and cannot be used in config. Use a different name for your trigger.")
        return v

    @field_validator("triggers", "actions", "profiles", mode="after")
    @classmethod
    def validate_entity_names(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Reject entity names that would be mis-parsed as a ``sourcekey.name`` reference.

        A name like ``web.v2`` would be read as source ``web``, giving a silent "profile not
        found"; fail at load time instead."""
        for name in v.keys():
            if not is_valid_sentinel_entity_name(name):
                raise ValueError(f"Invalid name [green]{name}[/green]: only letters, digits, '_' and '-' "
                                 f"are allowed ('.' is the source separator).")
        return v

    triggers: Dict[str, Trigger] = Field(
        default_factory=dict,
        description="Named conditions. The single key under a trigger's name IS its type: "
                    "`command`, `regex`, `parameter`, `env_var`, or `trigger` for a composite.")
    actions: Dict[str, Action] = Field(
        default_factory=dict,
        description="Named collectors. The single key under an action's name IS its type: "
                    "`dump_env`, `network_capture`, `dump_kerberos`, or `exec_command`.")
    profiles: Dict[str, Profile] = Field(
        default_factory=dict,
        description="Named profiles, each selectable with `exegol start -S <name>`.")
