from resources.lib.downstream.resolver_policy import (
	AUTOPLAY_RESOLVE_TIMEOUT_MS,
	NegativeCache,
	ResolutionCoordinator,
	autoplay_source_queue,
	bounded_resolve,
	normalized_metadata,
	resolve_real_debrid_source,
	source_key,
	unique_source_queue,
)
from resources.lib.downstream.rd_transport_policy import (
	RDError,
	RDTransportPolicy,
	classify_response,
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


def test_autoplay_queue_samples_quality_tiers_and_is_bounded():
	items = []
	for quality in ('1080p', '720p', 'SD', '4K'):
		for _index in range(5):
			item = _item(('%040x' % (len(items) + 1)))
			item['quality'] = quality
			items.append(item)
	result = autoplay_source_queue(items, limit=8)
	assert [item['quality'] for item in result] == [
		'1080p', '720p', 'SD', '4K',
		'1080p', '720p', 'SD', '4K',
	]


def test_autoplay_queue_honors_only_one_source():
	items = [_item('%040x' % index) for index in range(4)]
	assert autoplay_source_queue(items, use_only_one=True) == items[:1]


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


class ImmediateThread:
	def __init__(self, target):
		self.target = target
		self.alive = False

	def start(self):
		self.alive = True
		self.target()
		self.alive = False

	def is_alive(self):
		return self.alive


class StuckThread:
	instances = []

	def __init__(self, target):
		self.target = target
		self.daemon = False
		self.__class__.instances.append(self)

	def start(self):
		pass

	def is_alive(self):
		return True


def test_bounded_resolve_returns_immediate_result():
	result, status = bounded_resolve(
		lambda: 'https://example.invalid/sintel.mp4',
		ResolutionCoordinator(),
		ImmediateThread,
		lambda _milliseconds: None,
	)

	assert status == 'complete'
	assert result == 'https://example.invalid/sintel.mp4'


def test_default_resolve_timeout_allows_vpn_latency():
	assert AUTOPLAY_RESOLVE_TIMEOUT_MS == 45000


def test_bounded_resolve_invalidates_late_worker():
	StuckThread.instances.clear()
	coordinator = ResolutionCoordinator()
	result, status = bounded_resolve(
		lambda: 'late.mp4',
		coordinator,
		StuckThread,
		lambda _milliseconds: None,
		timeout_ms=400,
		poll_ms=200,
	)

	assert status == 'timeout'
	assert result is None
	assert coordinator.result(1) is None
	assert StuckThread.instances[-1].daemon is True


def test_missing_metadata_is_normalized_without_copying_valid_mapping():
	meta = {'title': 'Big Buck Bunny'}
	assert normalized_metadata(meta) is meta
	assert normalized_metadata(None) == {}
	assert normalized_metadata('invalid') == {}


class _Response:
	def __init__(self, status, payload):
		self.status_code = status
		self._payload = payload
		self.headers = {}

	def json(self):
		return self._payload


class _Session:
	def __init__(self, responses):
		self.responses = iter(responses)
		self.calls = 0

	def request(self, method, url, **kwargs):
		self.calls += 1
		return next(self.responses)


def test_source_to_transport_retries_34_and_returns_success(monkeypatch):
	import resources.lib.downstream.rd_transport_policy as transport_module

	monkeypatch.setattr(transport_module, 'sleep', lambda seconds: None)
	session = _Session(
		[
			_Response(429, {'error': 'too_many_requests', 'error_code': 34}),
			_Response(200, {'download': 'https://example.invalid/sintel.mp4'}),
		]
	)

	class Client:
		last_error = RDError()

		def resolve_magnet(self, url, info_hash, season, episode, title):
			response = RDTransportPolicy(
				min_interval=0, fallback_backoff=0, jitter=(0, 0)
			).request(session, 'POST', 'https://api.real-debrid.invalid')
			self.last_error = classify_response(response)
			return response.json().get('download')

	result = resolve_real_debrid_source(
		_item('D' * 40), None, None, 'Sintel', Client, NegativeCache()
	)
	assert result == 'https://example.invalid/sintel.mp4'
	assert session.calls == 2


def test_source_to_transport_caches_35_for_session():
	factory_calls = []
	failures = []

	class Client:
		last_error = RDError(error_code=35, error='infringing_file')

		def __init__(self):
			factory_calls.append(1)

		def resolve_magnet(self, url, info_hash, season, episode, title):
			return None

	cache = NegativeCache()
	item = _item('E' * 40)
	assert resolve_real_debrid_source(
		item, None, None, 'Sintel', Client, cache,
		failure_callback=lambda code, reason: failures.append((code, reason)),
	) is None
	assert resolve_real_debrid_source(
		item, None, None, 'Sintel', Client, cache,
		failure_callback=lambda code, reason: failures.append((code, reason)),
	) is None
	assert len(factory_calls) == 1
	assert failures == [
		(35, 'infringing_file'),
		(35, 'infringing_file_cached'),
	]
