"""Maps profile YAML fields to resolver options, and records what is not profilable.

* :data:`PROFILE_FIELD_MAP` — dotted YAML path -> :class:`OptionKey` (profile tier).
* :data:`PROFILE_PENDING_REGISTRATION` — profilable dests with no ``OptionKey`` yet (empty).
* :data:`PROFILE_USER_CONFIG_MAP` — dest-less ``config.yml`` settings a profile may override.
* :data:`PROFILE_EXCLUDED` — creation dests that are not profilable, with a written reason.
* :data:`PROFILE_TIER_DEAD` — registered options no profile may supply, with a written reason.

Every creation dest must appear in exactly one of the dest-bearing tables;
``tests/profile/test_field_coverage.py`` enforces it both ways. The dotted keys are the
public schema (renaming one breaks user files); the ``OptionKey`` values are internal.
"""

from typing import Dict

from exegol.config.OptionResolver import OptionKey

# ---------------------------------------------------------------------------
# 1. Dotted YAML path -> OptionKey. One path per member: the profile tier is single-valued.
# ---------------------------------------------------------------------------
PROFILE_FIELD_MAP: Dict[str, OptionKey] = {
    # -- display / GUI -------------------------------------------------------
    # Paths are public: never rename them, only repoint the OptionKey.
    "display.share_x11": OptionKey.GUI,
    "display.desktop.enabled": OptionKey.DESKTOP,
    # `listen_ip` and `port` have no entry: they are read with `proto` to compose the
    # "proto:host:port" value of DESKTOP_CONFIG.
    "display.desktop.proto": OptionKey.DESKTOP_CONFIG,
    # -- volumes and host sharing --------------------------------------------
    "volumes.mounts": OptionKey.VOLUMES,
    "customization.share_my_resources": OptionKey.MY_RESOURCES,
    "volumes.share_exegol_resources": OptionKey.EXEGOL_RESOURCES,
    "volumes.update_fs_perms": OptionKey.UPDATE_FS_PERMS,
    # -- network -------------------------------------------------------------
    "network.mode": OptionKey.NETWORK,
    "network.ports": OptionKey.PORTS,
    # -- system: host sharing and privileges ---------------------------------
    "system.share_timezone": OptionKey.SHARE_TIMEZONE,
    "system.privileged": OptionKey.PRIVILEGED,
    "system.devices": OptionKey.DEVICES,
    "system.capabilities": OptionKey.CAPABILITIES,
    # -- sentinel ------------------------------------------------------------
    "sentinel.enabled": OptionKey.SENTINEL,
    "sentinel.profile": OptionKey.SENTINEL_PROFILE,
    "sentinel.update_strategy": OptionKey.SENTINEL_STRATEGY,
    # -- shell ---------------------------------------------------------------
    "shell.default": OptionKey.SHELL,
    "shell.env": OptionKey.ENVS,
    # -- shell logging -------------------------------------------------------
    "logging.enabled": OptionKey.LOG,
    "logging.method": OptionKey.LOG_METHOD,
    "logging.compress": OptionKey.LOG_COMPRESS,
    # -- image, VPN, workspace, network identity, and metadata ---------------
    "image.tag": OptionKey.IMAGE_TAG,
    "vpn.config": OptionKey.VPN,
    "vpn.auth_file": OptionKey.VPN_AUTH,
    "volumes.workspace_path": OptionKey.WORKSPACE_PATH,
    "network.hostname": OptionKey.HOSTNAME,
    # Selects who supplies the hostname above, not what it is: true makes creation ask the
    # operator, offering `network.hostname` as the prompt default.
    "network.hostname_ask_user": OptionKey.HOSTNAME_ASK_USER,
    # `network.hosts` has no CLI flag. Inline hosts are merged after the hosts file in
    # `ContainerConfig.configFromUser()`, so they win on a colliding hostname.
    "network.hosts_file": OptionKey.HOSTS_FILE,
    "network.hosts": OptionKey.HOSTS,
    "metadata.comment": OptionKey.COMMENT,
    # Selects who supplies the comment above, not what it is. Same shape as
    # `network.hostname_ask_user`.
    "metadata.comment_ask_user": OptionKey.COMMENT_ASK_USER,
}


# ---------------------------------------------------------------------------
# 2. Profilable dests that are defined in the schema but not registered yet (dest -> dest).
#
# Kept (empty) so such a field is recorded rather than looking undecided. Promoting one
# to `_REGISTRY` intentionally breaks the registry drift counters, flips its
# `CREATION_ONLY_WARNING_SURFACE` entry to an `OptionKey` with a `None` override, and
# requires deleting its `RESOLVER_EXCLUDED` reason.
# ---------------------------------------------------------------------------
PROFILE_PENDING_REGISTRATION: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# 3. Dest-less `UserConfig` settings a profile may override (no CLI flag).
#
# Settings deliberately absent have their reasons in `PROFILE_TIER_DEAD`.
# `network_fallback_mode` is also absent: the fallback when `network.mode` cannot be
# honoured is the host operator's policy, not the profile author's.
#
# The host path entries are bind-mounted read-write (`my_resources_path` is also chmod'ed
# recursively). Unlike `-cwd` they name a directory, and `UserConfig.__resolveProfilePath()`
# refuses relative paths, `/` and the home directory or its ancestors.
#
# The `sentinel.log_rotation.*` entries control audit trail retention; they stay profilable
# because retention is part of an engagement's setup. Profiles are operator-selected input,
# so every override is announced at verbose level only.
#
# All three `sentinel.log_output.*` entries are profilable, `enabled` included, because what
# this family sets is a default and not a control:
# `SentinelProfileManager.get_consolidated_config()` backfills `profile.config.log_output`
# from these values only when the selected Sentinel audit profile declares no `log_output`
# block of its own, and replaces them wholesale when it does. An audit profile has therefore
# always been able to turn inline capture on or off over the top of `~/.exegol/config.yml`, so
# withholding `enabled` here would not have closed the capability, only made the family
# inconsistent and blocked an org-wide profile from enabling auditing by default. `enabled` is
# still the one key whose direction matters, so the tier builder resolves an unreadable value
# to capture off rather than to the default.
#
# Values are OptionKey members; the UserConfig attribute lives on the registry:
# `_REGISTRY[PROFILE_USER_CONFIG_MAP[dotted]].user_config_attr`.
# ---------------------------------------------------------------------------
PROFILE_USER_CONFIG_MAP: Dict[str, OptionKey] = {
    # -- image ---------------------------------------------------------------
    "image.custom_images": OptionKey.CUSTOM_IMAGES,
    # -- network -------------------------------------------------------------
    "network.dedicated_range": OptionKey.NETWORK_DEDICATED_RANGE,
    "network.default_netmask": OptionKey.NETWORK_DEFAULT_NETMASK,
    # -- host paths ----------------------------------------------------------
    "customization.my_resources_path": OptionKey.MY_RESOURCES_PATH,
    "volumes.exegol_resources_path": OptionKey.EXEGOL_RESOURCES_PATH,
    "volumes.private_workspace_path": OptionKey.PRIVATE_WORKSPACE_PATH,
    # -- sentinel ------------------------------------------------------------
    "sentinel.gid": OptionKey.SENTINEL_GID,
    "sentinel.sentinel_logs_host_path": OptionKey.SENTINEL_LOGS_HOST_PATH,
    "sentinel.log_rotation.enabled": OptionKey.SENTINEL_LOG_ROTATION_ENABLED,
    "sentinel.log_rotation.max_size": OptionKey.SENTINEL_LOG_ROTATION_MAX_SIZE,
    "sentinel.log_rotation.max_files": OptionKey.SENTINEL_LOG_ROTATION_MAX_FILES,
    "sentinel.log_rotation.compress": OptionKey.SENTINEL_LOG_ROTATION_COMPRESS,
    "sentinel.log_output.enabled": OptionKey.SENTINEL_LOG_OUTPUT_ENABLED,
    "sentinel.log_output.max_size": OptionKey.SENTINEL_LOG_OUTPUT_MAX_SIZE,
    "sentinel.log_output.truncation": OptionKey.SENTINEL_LOG_OUTPUT_TRUNCATION,
}


# ---------------------------------------------------------------------------
# 3b. Registered options whose profile tier is permanently empty, each with a reason.
#
# Unlike `PROFILE_EXCLUDED` (creation dests), none of these is declared on
# `ContainerCreation` / `ContainerSpawnShell`. Keys are config.yml keys and argparse dests,
# not dotted schema paths. A drift test pins the reasons, disjointness and entry count.
# ---------------------------------------------------------------------------
PROFILE_TIER_DEAD: Dict[OptionKey, str] = {
    # -- composition-sibling defaults: per-segment seeds, not the option value ----------
    OptionKey.DESKTOP_DEFAULT_PROTO:
        "A per-segment DEFAULT for `--desktop-config`, not a value of its own. "
        "`configureDesktop()` seeds the proto from UserConfig and THEN overwrites each "
        "non-empty segment of the passed 'proto:host:port' string, so a profile setting "
        "this would be setting the fallback for a field it already controls through "
        "`display.desktop.proto`. A container profile is one complete declarative "
        "invocation and has no separate 'persistent default' distinct from the value "
        "the container uses.",
    OptionKey.DESKTOP_DEFAULT_LOCALHOST:
        "Same as `desktop_default_proto`: the per-segment default for the desktop config's "
        "HOST segment, already reachable by a profile through `display.desktop.listen_ip`. "
        "Registering it removes the circularity in `configureDesktop()`; it does not make "
        "it a second, competing way for a profile to say the same thing.",
    # -- wrapper behaviour: out of the container-profile schema entirely ---------------
    OptionKey.EXEGOL_IMAGES_PATH:
        "Wrapper-behaviour-only: where the dockerfiles and image sources live on THIS "
        "host. Wrapper-behaviour settings are out of the container-profile schema "
        "entirely, so it has no field on the ContainerProfile tree for a dotted path to "
        "point at. It shapes how this machine builds and updates, not how a container is "
        "configured.",
    OptionKey.AUTO_REMOVE_IMAGES:
        "Wrapper-behaviour-only: whether this host prunes outdated images once they "
        "are unused. A lifecycle policy for the operator's own disk, not a container shape "
        "— and a shareable profile able to set it could delete images the operator still "
        "wants.",
    OptionKey.AUTO_CHECK_UPDATES:
        "Wrapper-behaviour-only: whether the wrapper checks for its own updates on "
        "startup. It governs this invocation's network behaviour before any container "
        "exists, so it is not a container-shape default in any sense.",
    OptionKey.ENABLE_EXEGOL_RESOURCES:
        "Read only to decide whether to WARN after a failed exegol-resources download, so "
        "folding it into "
        "`OptionKey.EXEGOL_RESOURCES` as that option's `user_config_attr` would let a "
        "download-consent flag out-rank a container-shape option. See the matching note in "
        "PROFILE_USER_CONFIG_MAP's comment block above, which is where that reasoning is "
        "recorded in full; this entry points at it rather than restating it differently.",
    # -- structurally circular: a profile setting these would choose which profile is read --
    OptionKey.SENTINEL_PROFILE_PATH:
        "Structurally circular, not a preference. This path is WHERE Sentinel audit "
        "profiles are discovered, so a container profile able to set it would decide which "
        "profiles exist to be read — the same circularity `RESOLVER_EXCLUDED['profile']` "
        "describes for the `--profile` selector: 'a profile able to set it would choose "
        "which profile is read'.",
    OptionKey.PROFILE_COMPONENT_PATH:
        "Structurally circular, and the sharpest case of it: this is where CONTAINER "
        "profiles themselves are discovered. A profile able to set it would choose which "
        "profiles are readable — including its own successor — which is exactly the "
        "circularity `RESOLVER_EXCLUDED['profile']` refuses for the selector flag.",
    OptionKey.SENTINEL_SOURCES:
        "Structurally circular: the declared git/path SOURCES that Sentinel audit profiles "
        "are cloned and scanned from. A container profile able to set it would point the "
        "wrapper at an arbitrary remote repository to fetch and execute profile content "
        "from — a shareable YAML file choosing what code the operator's machine pulls. "
        "Same circularity as the two paths above, with a supply-chain edge on top.",
    OptionKey.PROFILE_SOURCES:
        "Structurally circular, and SHARPER than `sentinel_sources` beside it: these are "
        "the declared git/path SOURCES that CONTAINER profiles themselves are cloned and "
        "scanned from. A container profile able to set it would point the wrapper at an "
        "arbitrary remote repository and fetch its own replacement — a profile choosing its "
        "successor, which is `profile_component_path`'s circularity plus a supply chain. "
        "And the payload differs in kind from the Sentinel case: a Sentinel audit profile "
        "fetched from an attacker-chosen remote configures logging, whereas a container "
        "profile fetched from one directly sets `privileged`, Linux capabilities, host "
        "bind-mounts and network mode on the operator's own machine.",
    # -- PROCESS CONTROL: governs THIS invocation, not the shape of a container ---------
    # These have an argparse dest but are not creation options, so they stay out of the
    # dest partition.
    OptionKey.QUIET:
        "Process-control, not container shape: it governs THIS invocation's console "
        "output. Registered so `get()` is the one way to read it, not so a profile can "
        "silence the wrapper — a shared profile able to set it could hide the very "
        "warnings that tell an operator what the profile changed.",
    OptionKey.VERBOSITY:
        "Process-control (`action='count'`): the log level for this invocation only. A "
        "profile able to set it would decide how much the operator is told about the "
        "profile itself, which is the same self-concealment `quiet` above describes.",
    OptionKey.ARCH:
        "Process-control: which image architecture to pull for this invocation. Its "
        "default is the HOST's own architecture, read from `platform.machine()` — a fact "
        "about the machine exegol is running on, not a preference anyone can hold. A "
        "profile written on an arm64 laptop would otherwise force arm64 images onto an "
        "amd64 host and fail at pull time for reasons the operator never chose.",
    OptionKey.OFFLINE_MODE:
        "Process-control: suppresses network access for this invocation. It is also the "
        "ONE parameter whitelisted for runtime write-back on ParametersManager — "
        "`WebRegistryUtils` sets it mid-process when a registry request fails — so its "
        "value is partly a fact about what has already happened during this run, which no "
        "declarative file could know. A profile able to set it could also silently put an "
        "engagement offline, disabling image and licence updates without saying so.",
    OptionKey.ACCEPT_EULA:
        "Process-control: a one-shot acknowledgement of the End-User License Agreement. An "
        "acknowledgement is an act by a PERSON, so a shareable YAML file able to supply it "
        "would let one operator accept a licence agreement on another's behalf — which is "
        "not container configuration under any reading.",
    OptionKey.SELECT_ALL:
        "Process-control: widens a multi-selector to every container or image on the host. "
        "It selects TARGETS rather than configuring one, and the targets it would select "
        "belong to the operator, not to the profile author — `exegol remove --all` is not "
        "a value a background default may supply.",
    OptionKey.FORCE_MODE:
        "Process-control: skips the interactive confirmations for this invocation. A "
        "profile able to set it would remove the confirmation step from operations that "
        "delete containers and images, so a shared profile could turn every later prompt "
        "into a silent yes. Consent is per-invocation by construction.",
    OptionKey.SENTINEL_REFRESH:
        "Process-control: forces a one-shot Sentinel audit-config regeneration from host "
        "sources at restart. It is an IMPERATIVE — a thing to do now — rather than a value "
        "a lower tier could supply a default for, and a tier that supplied it would make "
        "it happen on every restart rather than once.",
    OptionKey.DAEMON:
        "Process-control: decides whether THIS exec detaches into the background. It "
        "concerns the lifetime of one command the operator just typed, not how the "
        "container it runs in was built.",
    OptionKey.TMP:
        "Process-control: marks this invocation's container as throwaway, to be removed "
        "when the command finishes. It governs LIFECYCLE, and a profile able to set it "
        "could make a container the operator meant to keep vanish on exit.",
    OptionKey.EXEC:
        "Process-control: the command line to run inside the container, which is "
        "per-invocation by definition. A profile able to supply it would be a shareable "
        "text file that chooses what code runs on the operator's container — the sharpest "
        "form of the same supply-chain concern `sentinel_sources` above describes.",
    OptionKey.SELECTOR:
        "Process-control: the target expression naming which container or image THIS "
        "invocation acts on. A profile shapes a container; it does not select one. Letting "
        "a profile supply it would mean loading a profile could retarget the whole "
        "invocation at something other than what the operator typed — the same reason "
        "`PROFILE_EXCLUDED['containertag']` gives for the positional.",
    # -- ACTION-SPECIFIC: an argument of one command, not a container-shape value -------
    OptionKey.BUILD_LOG:
        "Action-specific to `exegol build`: where to write THIS build's logs. "
        "Per-invocation I/O, not container configuration — and a profile able to name a "
        "host file the wrapper then writes to is a host-write path with none of the "
        "constraints `UserConfig.__resolveProfilePath()` places on the profilable paths.",
    OptionKey.BUILD_PATH:
        "Action-specific to `exegol build`: where the dockerfiles and sources live on THIS "
        "host. Not a container-shape value, and a profile able to repoint it would choose "
        "which Dockerfiles the operator's machine builds from — the same circularity the "
        "discovery paths above refuse, with a build step on the end of it.",
    OptionKey.UPDATE_WRAPPER:
        "Action-specific to `exegol update`: asks THIS invocation to fetch and install a "
        "new version of the wrapper itself. A profile able to set it would decide, from a "
        "shareable YAML file, whether the operator's own exegol binary is replaced with "
        "whatever the source branch currently holds — an unrequested code update on the "
        "host, executed the next time the wrapper runs. That is a decision about the "
        "operator's machine, not about the shape of a container.",
    OptionKey.UPDATE_RESOURCES:
        "Action-specific to `exegol update`: asks THIS invocation to pull the Exegol "
        "resources repository. A profile able to set it would trigger a network fetch and "
        "a write into the host resources tree that every container bind-mounts, for an "
        "operator who asked only to start a container. Distinct from "
        "`OptionKey.EXEGOL_RESOURCES`, which is profilable and means 'mount the resources "
        "in this container': that one is container shape, this one is a fetch.",
    OptionKey.UPDATE_PROFILE:
        "Action-specific to `exegol update`: asks THIS invocation to fetch the container "
        "profile SOURCES configured on this host. A profile able to set it would make "
        "loading a profile pull new profile definitions — including, potentially, its own "
        "replacement — which is a self-updating configuration tier and exactly the "
        "circularity `RESOLVER_EXCLUDED['profile']` refuses, with a network fetch on the "
        "end of it. Distinct from the near-named `profile` dest, which is NOT this option: "
        "that one is the excluded, value-carrying selector naming WHICH profile supplies "
        "tier 2, while this one is a boolean naming a fetch target.",
    OptionKey.UPDATE_SENTINEL:
        "Action-specific to `exegol update`: asks THIS invocation to fetch the Sentinel "
        "audit-profile SOURCES configured on this host. A profile able to set it would "
        "pull new audit-profile definitions onto the host as a side effect of being "
        "loaded, which is how the code that decides what gets journalized during an "
        "engagement would change without anyone asking. Distinct from the near-named "
        "`sentinel` dest, which is NOT this option: that one is the registered "
        "container-shape toggle mapped to `sentinel.enabled` in PROFILE_FIELD_MAP and is "
        "legitimately profilable, while this one is a host-side fetch request.",
    OptionKey.NO_BACKUP:
        "Action-specific to `exegol upgrade`: decides what happens to the OUTDATED "
        "container after the upgrade — renamed and kept, or removed. That is lifecycle, "
        "not configuration, and it is a decision about DESTROYING an existing container, "
        "which no background tier may make on the operator's behalf.",
    OptionKey.UPGRADE_IMAGE_TAG:
        "Action-specific to `exegol upgrade`: names the image to upgrade TO. It selects an "
        "upgrade TARGET, and the image of an existing container is not a value a lower "
        "tier may silently change under the operator. Distinct from `image.tag` in "
        "PROFILE_FIELD_MAP, which is profilable precisely because it names the image a NEW "
        "container is built from — a container-shape choice made before anything exists.",
    OptionKey.INFO_CONFIG:
        "Action-specific to `exegol info`: asks THIS invocation to render the "
        "user-configuration section. It selects what the operator is shown, not how a "
        "container is built, and a profile able to set it would decide what a read-only "
        "report displays — so a profile could keep its own settings on screen, or off it, "
        "for an operator who never asked either way. Distinct from the settings the table "
        "REPORTS, which are `config.yml` values a profile may legitimately override "
        "through PROFILE_USER_CONFIG_MAP; this option is only the request to print them.",
    OptionKey.INFO_SOURCES:
        "Action-specific to `exegol info`: asks THIS invocation to render the git source "
        "status section. Same kind as `info_config` — it selects what a read-only report "
        "shows, not how a container is built — and a profile able to set it would decide "
        "whether an operator is shown the state of the wrapper, image-source, resource and "
        "Sentinel-core checkouts on their own machine. A profile that could keep that "
        "table off the screen could hide a stale or diverged source tree from the person "
        "who installed it, which is the one report that would reveal it.",
    OptionKey.INFO_ALL:
        "Action-specific to `exegol info`: the broad request for every section at once. A "
        "profile able to set it would make a bare `exegol info` print the whole picture — "
        "including the container-profile and Sentinel listings — for an operator who asked "
        "for none of it, turning a read-only summary into a disclosure decision made by a "
        "shared YAML file. Distinct from `select_all`, which shares the flag spelling "
        "`--all` but means 'act on every container/image' on `stop`/`remove`/`uninstall`: "
        "that one names TARGETS of a destructive action, this one names SECTIONS of a "
        "report, and neither may be supplied by a profile for entirely different reasons.",
    OptionKey.REVOKE:
        "Action-specific to `exegol activate`: an imperative licence REVOCATION. Not a "
        "value a default tier could supply — a profile able to set it would revoke the "
        "operator's licence as a side effect of being loaded.",
    OptionKey.API_KEY:
        "A CREDENTIAL for `exegol activate`. Secrets must never be resolvable from a "
        "shareable profile: a container profile is a YAML file operators pass to each "
        "other, commit to repositories and copy between engagements, so a profile able to "
        "supply this would make identity material travel with it — and the licence it "
        "activates would not be the reader's. The environment variable EXEGOL_API_KEY "
        "remains the only non-CLI source, and "
        "`test_no_profile_field_can_ever_supply_the_credential_options` asserts that no "
        "profile table ever names this option.",
    OptionKey.LICENSE_ID:
        "The licence identifier accompanying the API key for `exegol activate`. Same "
        "reason as `api_key` and the same assertion covers it: identity material, not "
        "container shape, reachable only from the CLI or EXEGOL_LICENSE_ID.",
    OptionKey.SHELL_TYPE:
        "Process-control: which shell dialect `exegol completion` writes its script for. "
        "It describes the operator's own terminal, not a container — the action prints "
        "text to stdout and creates nothing. A profile able to set it would emit a bash "
        "script into a zsh completion file, silently breaking tab completion on the host "
        "of every operator whose shell differs from the profile author's.",
}


# ---------------------------------------------------------------------------
# 4. Creation dests deliberately NOT profilable, keyed by dest like `RESOLVER_EXCLUDED`.
# A reason (prose > 10 characters) is mandatory.
# ---------------------------------------------------------------------------
PROFILE_EXCLUDED: Dict[str, str] = {
    # -- security boundary: never profilable, under any refactor --------------
    "mount_current_dir": "A security boundary, not an oversight. `-cwd` / `--cwd-mount` "
                         "expands to the PROCESS WORKING DIRECTORY, so a shareable "
                         "profile able to set it would bind-mount whichever host tree "
                         "exegol happened to be launched from — a home directory, a "
                         "credentials tree, an unrelated engagement — into the container, "
                         "read-write, without the operator ever naming it. It is already "
                         "excluded from `_REGISTRY`, it has no field "
                         "anywhere on the `ContainerProfile` tree, and it must NEVER move "
                         "into PROFILE_FIELD_MAP or PROFILE_PENDING_REGISTRATION — not by "
                         "hand, not by a rename, not by a bulk-generation pass. If a "
                         "profile needs to select a workspace, that is `-w / --workspace` "
                         "(see `volumes.workspace_path` in PROFILE_FIELD_MAP) and its own "
                         "decision, which at least makes the operator NAME the directory.",
    # -- selects a target rather than configuring one -------------------------
    "containertag": "A positional naming WHICH existing container to act on, not how one "
                    "is configured. A profile shapes a container; it does not select one. "
                    "Letting a profile supply it would mean loading a profile could "
                    "retarget the whole invocation at a different container than the one "
                    "the operator typed.",
}
