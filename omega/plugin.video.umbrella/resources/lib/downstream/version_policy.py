"""Small, testable policy for legacy Umbrella version markers."""

import re


VERSION = re.compile(r"^\d+(?:\.\d+)*$")


def numeric_version(value, default=None):
	normalized = str(value or "").strip()
	if not VERSION.fullmatch(normalized):
		if default is not None:
			return default
		raise ValueError("invalid Umbrella version marker")
	return int(normalized.replace(".", ""))
