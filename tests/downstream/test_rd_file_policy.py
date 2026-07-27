from resources.lib.downstream.rd_file_policy import link_for_selected_path


VIDEO_EXTENSIONS = ('.mkv', '.mp4')


def test_maps_link_by_full_selected_file_order():
	files = [
		{'path': '/movie.mkv', 'selected': 1},
		{'path': '/movie.nfo', 'selected': 1},
	]
	assert link_for_selected_path(
		files,
		['movie-link', 'nfo-link'],
		'/movie.mkv',
		VIDEO_EXTENSIONS,
	) == 'movie-link'


def test_maps_video_only_links_after_omitted_sidecar():
	files = [
		{'path': '/movie.nfo', 'selected': 1},
		{'path': '/movie.mkv', 'selected': 1},
	]
	assert link_for_selected_path(
		files,
		['movie-link'],
		'/movie.mkv',
		VIDEO_EXTENSIONS,
	) == 'movie-link'


def test_rejects_ambiguous_shorter_link_list():
	files = [
		{'path': '/movie-a.mkv', 'selected': 1},
		{'path': '/movie-b.mkv', 'selected': 1},
	]
	assert link_for_selected_path(
		files,
		['one-link'],
		'/movie-b.mkv',
		VIDEO_EXTENSIONS,
	) is None


def test_rejects_missing_or_unselected_path():
	files = [{'path': '/movie.mkv', 'selected': 0}]
	assert link_for_selected_path(
		files,
		['movie-link'],
		'/movie.mkv',
		VIDEO_EXTENSIONS,
	) is None
