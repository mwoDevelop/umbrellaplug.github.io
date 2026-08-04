# -*- coding: utf-8 -*-
"""Bound Kodi library failures at the downstream integration edge."""

from json import loads


MOVIE_PROBE = '{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "limits": { "start" : 0, "end": 1 }, "properties" : ["title", "genre", "uniqueid", "art", "rating", "thumbnail", "playcount", "file"] }, "id": "1"}'


def has_library_movies(jsonrpc):
	"""Return False when Kodi's optional video library is unavailable."""
	try:
		payload = loads(jsonrpc(MOVIE_PROBE))
		result = payload.get('result', {}) if isinstance(payload, dict) else {}
		movies = result.get('movies', []) if isinstance(result, dict) else []
		return bool(movies) if isinstance(movies, list) else False
	except Exception:
		return False
