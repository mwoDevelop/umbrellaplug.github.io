from resources.lib.downstream.subtitle_policy import (
	first_subtitle,
	validated_subtitle_download,
)


def test_missing_opensubs_url_is_not_downloaded():
	assert validated_subtitle_download(None, 'Sintel.eng') is None
	assert validated_subtitle_download('', 'Sintel.eng') is None


def test_valid_opensubs_download_is_preserved():
	assert validated_subtitle_download(
		'https://example.invalid/Sintel.srt',
		'Sintel.eng',
	) == ('https://example.invalid/Sintel.srt', 'Sintel.eng')


def test_empty_download_directory_has_no_selected_subtitle():
	assert first_subtitle([]) is None
	assert first_subtitle(['/tmp/Sintel.srt']) == '/tmp/Sintel.srt'
