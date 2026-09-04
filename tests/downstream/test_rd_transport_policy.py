from resources.lib.downstream.rd_transport_policy import (
	RDTransportPolicy,
	classify_response,
)


class Response:
	def __init__(self, status=200, payload=None, headers=None):
		self.status_code = status
		self._payload = payload or {}
		self.headers = headers or {}

	def json(self):
		return self._payload


class Session:
	def __init__(self, responses):
		self.responses = iter(responses)
		self.calls = 0

	def request(self, method, url, **kwargs):
		self.calls += 1
		return next(self.responses)


def test_classifies_rd_error_and_retry_after():
	error = classify_response(
		Response(429, {'error': 'too_many_requests', 'error_code': 34}, {'Retry-After': '2'})
	)
	assert error.http_status == 429
	assert error.error_code == 34
	assert error.retry_after == 2


def test_successful_collection_response_has_no_rd_error():
	error = classify_response(Response(200, [{'id': 'torrent-1'}]))
	assert error.http_status == 200
	assert error.error_code == 0
	assert error.error == ''


def test_rate_limit_retries_once(monkeypatch):
	import resources.lib.downstream.rd_transport_policy as policy

	monkeypatch.setattr(policy, 'sleep', lambda seconds: None)
	session = Session(
		[
			Response(429, {'error': 'too_many_requests', 'error_code': 34}),
			Response(200, {'id': 'ok'}),
		]
	)
	transport = RDTransportPolicy(min_interval=0, fallback_backoff=0, jitter=(0, 0))
	assert transport.request(session, 'POST', 'https://example.invalid').status_code == 200
	assert session.calls == 2


def test_excessive_retry_after_is_not_slept_or_retried(monkeypatch):
	import resources.lib.downstream.rd_transport_policy as policy

	monkeypatch.setattr(policy, 'sleep', lambda seconds: (_ for _ in ()).throw(AssertionError()))
	session = Session(
		[
			Response(
				429,
				{'error': 'too_many_requests', 'error_code': 34},
				{'Retry-After': '120'},
			)
		]
	)
	transport = RDTransportPolicy(min_interval=0, max_retry_after=30)
	assert transport.request(session, 'GET', 'https://example.invalid').status_code == 429
	assert session.calls == 1
