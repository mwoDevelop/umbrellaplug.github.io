"""Pure resolver queue, negative-cache, and generation policies."""

from threading import Lock
from time import monotonic


AUTOPLAY_RESOLVE_TIMEOUT_MS = 20000


def normalized_metadata(value):
	"""Return mapping-like resolver metadata without leaking None downstream."""
	return value if isinstance(value, dict) else {}


def source_key(item, season=None, episode=None):
	hash_value = str(item.get('hash') or '').lower()
	url = str(item.get('url') or '')
	if hash_value:
		return ('torrent', hash_value, str(season or ''), str(episode or ''))
	return ('url', url)


def unique_source_queue(items, season=None, episode=None, limit=8):
	result, seen = [], set()
	for item in items:
		key = source_key(item, season, episode)
		if key in seen:
			continue
		seen.add(key)
		result.append(item)
		if len(result) >= limit:
			break
	return result


def autoplay_source_queue(items, use_only_one=False, limit=12):
	"""Bound autoplay attempts while sampling every available quality tier."""
	if use_only_one:
		return unique_source_queue(items, limit=1)
	buckets, quality_order = {}, []
	for item in unique_source_queue(items, limit=len(items)):
		quality = str(item.get('quality') or 'unknown')
		if quality not in buckets:
			buckets[quality] = []
			quality_order.append(quality)
		buckets[quality].append(item)
	result = []
	while len(result) < limit:
		added = False
		for quality in quality_order:
			if buckets[quality]:
				result.append(buckets[quality].pop(0))
				added = True
				if len(result) >= limit:
					break
		if not added:
			break
	return result


class NegativeCache:
	def __init__(self, ttl=3600):
		self.ttl = ttl
		self._items = {}
		self._lock = Lock()

	def contains(self, key):
		now = monotonic()
		with self._lock:
			expiry = self._items.get(key, 0)
			if expiry <= now:
				self._items.pop(key, None)
				return False
			return True

	def add(self, key):
		with self._lock:
			self._items[key] = monotonic() + self.ttl


class ResolutionCoordinator:
	"""Accept only results belonging to the latest timed attempt."""

	def __init__(self):
		self._generation = 0
		self._results = {}
		self._lock = Lock()

	def begin(self):
		with self._lock:
			self._generation += 1
			return self._generation

	def complete(self, generation, value):
		with self._lock:
			if generation != self._generation:
				return False
			self._results[generation] = value
			return True

	def result(self, generation):
		with self._lock:
			if generation != self._generation:
				return None
			return self._results.pop(generation, None)

	def invalidate(self, generation):
		with self._lock:
			if generation == self._generation:
				self._generation += 1
			self._results.pop(generation, None)


def bounded_resolve(
	resolve,
	coordinator,
	thread_factory,
	sleep,
	timeout_ms=AUTOPLAY_RESOLVE_TIMEOUT_MS,
	poll_ms=200,
):
	"""Resolve off-thread and reject results that arrive after the deadline."""
	generation = coordinator.begin()
	failure = []

	def _run():
		try:
			value = resolve()
		except Exception as error:
			failure.append(error)
			value = None
		coordinator.complete(generation, value)

	worker = thread_factory(target=_run)
	# Kodi waits for non-daemon Python workers before releasing a plug-in
	# invocation.  A bounded resolver therefore also needs a daemon worker;
	# otherwise the UI can remain stuck long after this policy returns timeout.
	try:
		worker.daemon = True
	except (AttributeError, RuntimeError):
		pass
	worker.start()
	polls = max(1, int(timeout_ms / poll_ms))
	for _index in range(polls):
		if not worker.is_alive():
			status = 'error' if failure else 'complete'
			return coordinator.result(generation), status
		sleep(poll_ms)
	if not worker.is_alive():
		status = 'error' if failure else 'complete'
		return coordinator.result(generation), status
	coordinator.invalidate(generation)
	return None, 'timeout'


infringing_cache = NegativeCache()


def resolve_real_debrid_source(
	item,
	season,
	episode,
	title,
	client_factory,
	negative_cache=infringing_cache,
	failure_callback=None,
):
	"""Resolve one RD source while enforcing the session negative cache."""
	cache_key = source_key(item, season, episode)
	if negative_cache.contains(cache_key):
		if failure_callback:
			failure_callback(35, 'infringing_file_cached')
		return None
	client = client_factory()
	resolved = client.resolve_magnet(
		item['url'],
		item['hash'],
		season,
		episode,
		title,
	)
	last_error = getattr(client, 'last_error', None)
	error_code = int(getattr(last_error, 'error_code', 0) or 0)
	error = str(getattr(last_error, 'error', '') or '')
	if error_code == 35:
		negative_cache.add(cache_key)
	if not resolved and failure_callback:
		failure_callback(error_code, error or 'no_playable_url')
	return resolved
