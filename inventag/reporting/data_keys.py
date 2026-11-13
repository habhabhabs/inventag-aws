"""Maps whose keys are data, not field names.

Report writers turn nested ``raw_data`` into one column per key path. Some API
fields are maps keyed by an ID, for example Secrets Manager's
``SecretVersionsToStages`` (keyed by version UUID). Flattening those gives one
column per resource, so such a map is written as one JSON cell instead.
"""

import json
import re
from typing import Any, Mapping

_DATA_KEY = re.compile(
    r"""^(?:
        [0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}
        |[0-9a-fA-F]{16,}
        |[0-9].*
        |.*[:/].*
    )$""",
    re.VERBOSE,
)


def is_data_keyed(value: Mapping[Any, Any]) -> bool:
    """True when any key of ``value`` is an ID, ARN, path or number."""
    return any(not isinstance(k, str) or _DATA_KEY.match(k) for k in value)


def as_cell(value: Mapping[Any, Any]) -> str:
    """One cell for a data-keyed map: compact JSON, keys sorted."""
    return json.dumps(value, sort_keys=True, default=str)
