"""Validation helpers for optional subtitle downloads."""


def validated_subtitle_download(download_url, filename):
	"""Return safe download inputs or None when the provider omitted them."""
	if not isinstance(download_url, str):
		return None
	if not download_url.startswith(('https://', 'http://')):
		return None
	if not isinstance(filename, str) or not filename.strip():
		return None
	return download_url, filename


def first_subtitle(paths):
	"""Return the first generated subtitle without indexing an empty result."""
	return paths[0] if paths else None
