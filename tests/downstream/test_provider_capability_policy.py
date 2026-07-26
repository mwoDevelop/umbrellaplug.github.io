from resources.lib.downstream.provider_capability_policy import provider_pack_sources


class SingleOnlyProvider:
	def sources(self, data, hosters):
		return []


class PackProvider:
	def __init__(self):
		self.received = None

	def sources_packs(self, *args, **kwargs):
		self.received = (args, kwargs)
		return [{'url': 'magnet:test'}]


def test_provider_without_pack_capability_is_skipped():
	assert provider_pack_sources(SingleOnlyProvider(), {'title': 'Example'}, []) == []


def test_provider_pack_capability_preserves_arguments_and_result():
	provider = PackProvider()

	result = provider_pack_sources(
		provider,
		{'title': 'Example'},
		['host.example'],
		search_series=True,
	)

	assert result == [{'url': 'magnet:test'}]
	assert provider.received == (
		({'title': 'Example'}, ['host.example']),
		{'search_series': True},
	)
