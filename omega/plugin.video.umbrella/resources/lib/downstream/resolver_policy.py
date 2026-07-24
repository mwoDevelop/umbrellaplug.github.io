"""Pure resolver queue, negative-cache, and generation policies."""

from threading import Lock
from time import monotonic


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


infringing_cache = NegativeCache()


def resolve_real_debrid_source(
	item,
	season,
	episode,
	title,
	client_factory,
	negative_cache=infringing_cache,
):
	"""Resolve one RD source while enforcing the session negative cache."""
	cache_key = source_key(item, season, episode)
	if negative_cache.contains(cache_key):
		return None
	client = client_factory()
	resolved = client.resolve_magnet(
		item['url'],
		item['hash'],
		season,
		episode,
		title,
	)
	if getattr(getattr(client, 'last_error', None), 'error_code', 0) == 35:
		negative_cache.add(cache_key)
	return resolved
