from resources.lib.downstream.resolver_policy import (
	NegativeCache,
	ResolutionCoordinator,
	normalized_metadata,
	source_key,
	unique_source_queue,
)


def _item(hash_value, name='source'):
	return {
		'hash': hash_value,
		'url': 'magnet:?xt=urn:btih:%s' % hash_value,
		'name': name,
	}


def test_queue_deduplicates_first_source_and_preserves_order():
	first = _item('A' * 40, 'chosen')
	items = [first, _item('B' * 40), first, _item('C' * 40)]
	result = unique_source_queue(items, limit=8)
	assert [item['name'] for item in result] == ['chosen', 'source', 'source']
	assert len({source_key(item) for item in result}) == 3


def test_queue_has_bounded_attempt_count():
	items = [_item(('%040x' % index)) for index in range(20)]
	assert len(unique_source_queue(items)) == 8


def test_negative_cache_expires(monkeypatch):
	import resources.lib.downstream.resolver_policy as policy

	clock = iter((10.0, 10.0, 16.0))
	monkeypatch.setattr(policy, 'monotonic', lambda: next(clock))
	cache = NegativeCache(ttl=5)
	cache.add(('torrent', 'abc'))
	assert cache.contains(('torrent', 'abc'))
	assert not cache.contains(('torrent', 'abc'))


def test_stale_generation_cannot_publish():
	coordinator = ResolutionCoordinator()
	old = coordinator.begin()
	current = coordinator.begin()
	assert not coordinator.complete(old, 'stale.mp4')
	assert coordinator.complete(current, 'current.mp4')
	assert coordinator.result(current) == 'current.mp4'


def test_missing_metadata_is_normalized_without_copying_valid_mapping():
	meta = {'title': 'Big Buck Bunny'}
	assert normalized_metadata(meta) is meta
	assert normalized_metadata(None) == {}
	assert normalized_metadata('invalid') == {}
