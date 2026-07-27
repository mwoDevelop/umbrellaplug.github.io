"""Pure Real-Debrid file/link mapping policy."""


def _selected(files):
	return [
		item for item in files
		if isinstance(item, dict) and item.get('selected') == 1
	]


def link_for_selected_path(files, links, path, extensions):
	"""Return the link corresponding to ``path`` without guessing ambiguity.

	Real-Debrid normally returns one link per selected file. Some torrents omit
	links for non-video sidecar files, so the shorter list instead aligns with
	the selected video files. Any other cardinality is ambiguous and is rejected
	instead of indexing past the response.
	"""
	if not isinstance(files, list) or not isinstance(links, list):
		return None
	if not path or not links:
		return None
	selected = _selected(files)
	video = [
		item for item in selected
		if str(item.get('path') or '').lower().endswith(tuple(extensions))
	]
	if len(links) == len(selected):
		mapped = selected
	elif len(links) == len(video):
		mapped = video
	else:
		return None
	for index, item in enumerate(mapped):
		if item.get('path') == path:
			return links[index] if index < len(links) else None
	return None
