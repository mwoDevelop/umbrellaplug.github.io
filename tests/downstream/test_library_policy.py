from resources.lib.downstream.library_policy import has_library_movies


def test_available_library_with_movies_is_detected():
	def jsonrpc(_query):
		return '{"result":{"movies":[{"movieid":1}]}}'

	assert has_library_movies(jsonrpc) is True


def test_unavailable_library_does_not_break_umbrella_navigation():
	assert has_library_movies(lambda _query: '{"error":{"code":-32603}}') is False


def test_malformed_or_failed_jsonrpc_is_treated_as_empty_library():
	assert has_library_movies(lambda _query: 'not-json') is False

	def failed(_query):
		raise RuntimeError('database unavailable')

	assert has_library_movies(failed) is False
