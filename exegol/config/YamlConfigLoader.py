"""Shared YAML loading for every Exegol configuration schema.

Holds only what is common to all YAML schemas: the strict base model, a duplicate-key
aware safe loader and a never-raising single-file loader. Source enumeration, merging
and ``source.name`` resolution differ per domain and stay in ``exegol.sentinel`` /
``exegol.profile``.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError
from rich.markup import escape

from exegol.utils.ExeLog import logger


class StrictSafeLoader(yaml.SafeLoader):
    """``yaml.SafeLoader`` that rejects a key repeated inside the same mapping.

    Plain ``safe_load`` keeps the last duplicate silently, before pydantic can see it.
    Must derive from ``SafeLoader``: ``yaml.Loader`` can construct arbitrary objects.
    """

    def construct_mapping(self, node: yaml.nodes.MappingNode, deep: bool = False) -> Dict[Any, Any]:
        seen: Set[Any] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                already_seen = key in seen
            except TypeError:
                # Unhashable key: let super() report it with a better message.
                continue
            if already_seen:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    f"found duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


class StrictYamlModel(BaseModel):
    """Base model for every YAML-backed Exegol config schema: unknown keys are errors.

    Set on the base so new section models cannot fall back to pydantic's ``ignore``,
    where a typo parses clean. A reflection test checks subclasses do not override it.
    """

    model_config = ConfigDict(extra='forbid')

    @classmethod
    def generate_json_schema(cls) -> str:
        """Serialize this model's JSON Schema, shared by the generator and the drift test.

        The trailing newline matches what the ``end-of-file-fixer`` hook commits.
        """
        return json.dumps(cls.model_json_schema(), indent=2) + "\n"


M = TypeVar("M", bound=StrictYamlModel)


def load_yaml_file(path: Path, model: Type[M], errors: Optional[List[Path]] = None) -> Optional[M]:
    """Load and strictly validate ONE YAML file into ``model``. Never raises.

    Returns ``None`` on any failure, each logged distinctly: unreadable/unparseable,
    non-mapping root and one line per schema error (``"{path}: '{loc}': {msg}"``). An
    empty file is only a debug message. Uses ``logger.error``, never ``critical``
    (which exits), since this runs from ``exegol info`` and tab-completion.

    ``errors``, when given, receives ``path`` on a real failure but not for an empty
    file, so callers can tell empty from broken.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=StrictSafeLoader)
    except (yaml.YAMLError, OSError) as e:
        # Escape both: an unmatched markup tag would make the log call itself raise.
        logger.error(f"Failed to read YAML file {escape(str(path))}: {escape(str(e))}")
        if errors is not None:
            errors.append(path)
        return None

    if data is None:
        logger.debug(f"{escape(str(path))}: file is empty; skipping.")
        return None

    if not isinstance(data, dict):
        logger.error(f"{escape(str(path))}: expected a top-level mapping, got {type(data).__name__}.")
        if errors is not None:
            errors.append(path)
        return None

    try:
        return model.model_validate(data)
    except ValidationError as e:
        for err in e.errors():
            # The location is an operator-authored key: escape it.
            location = ".".join(str(part) for part in err["loc"]) or "<root>"
            logger.error(f"{escape(str(path))}: '{escape(location)}': {escape(str(err['msg']))}")
        if errors is not None:
            errors.append(path)
        return None
