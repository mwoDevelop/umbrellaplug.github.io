"""Sanitize metadata before it crosses into an external provider."""

from copy import deepcopy


PUBLIC_PROVIDER_KEYS = frozenset(
	(
		'aliases',
		'episode',
		'imdb',
		'premiered',
		'season',
		'title',
		'tvdb',
		'tvshowtitle',
		'year',
	)
)


def provider_context(metadata, debrid_service=None):
	"""Return an allowlisted copy that never contains debrid credentials."""
	if not isinstance(metadata, dict):
		metadata = {}
	result = {
		key: deepcopy(value)
		for key, value in metadata.items()
		if key in PUBLIC_PROVIDER_KEYS
	}
	if debrid_service:
		result['debrid_service'] = str(debrid_service)
	return result
