"""Thread-safe request pacing and bounded retry for Real-Debrid."""

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from random import uniform
from threading import Lock
from time import monotonic, sleep


@dataclass(frozen=True)
class RDError:
	http_status: int = 0
	error_code: int = 0
	error: str = ''
	retry_after: float = 0.0


def _retry_after_seconds(value, now=None):
	if not value:
		return 0.0
	try:
		return max(0.0, float(value))
	except (TypeError, ValueError):
		try:
			now = now or parsedate_to_datetime('Thu, 01 Jan 1970 00:00:00 GMT')
			return max(0.0, (parsedate_to_datetime(value) - now).total_seconds())
		except (TypeError, ValueError, OverflowError):
			return 0.0


def classify_response(response):
	try:
		payload = response.json()
	except (TypeError, ValueError):
		payload = {}
	return RDError(
		http_status=int(getattr(response, 'status_code', 0) or 0),
		error_code=int(payload.get('error_code') or 0),
		error=str(payload.get('error') or ''),
		retry_after=_retry_after_seconds(getattr(response, 'headers', {}).get('Retry-After')),
	)


class RDTransportPolicy:
	def __init__(
		self,
		min_interval=1.0,
		max_retry_after=30.0,
		fallback_backoff=1.0,
		jitter=(0.25, 0.75),
	):
		self.min_interval = min_interval
		self.max_retry_after = max_retry_after
		self.fallback_backoff = fallback_backoff
		self.jitter = jitter
		self._request_lock = Lock()
		self._next_request = 0.0

	def _wait_for_slot(self):
		delay = self._next_request - monotonic()
		if delay > 0:
			sleep(delay)
		self._next_request = monotonic() + self.min_interval

	def request(self, session, method, url, **kwargs):
		"""Serialize authorized requests and retry error 34 at most once."""
		with self._request_lock:
			for attempt in range(2):
				self._wait_for_slot()
				response = session.request(method, url, **kwargs)
				error = classify_response(response)
				rate_limited = error.http_status == 429 or error.error_code == 34
				if not rate_limited or attempt:
					return response
				if error.retry_after > self.max_retry_after:
					return response
				delay = error.retry_after or self.fallback_backoff + uniform(*self.jitter)
				sleep(min(delay, self.max_retry_after))
			return response


rd_transport = RDTransportPolicy()
