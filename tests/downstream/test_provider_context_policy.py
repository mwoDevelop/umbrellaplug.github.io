from pathlib import Path

from resources.lib.downstream.provider_context_policy import provider_context


def test_provider_context_is_allowlisted_and_does_not_mutate_input():
	metadata = {
		'title': 'Sintel',
		'year': 2010,
		'aliases': [{'title': 'Sintel', 'country': 'us'}],
		'debrid_token': 'rd-secret',
		'realdebridtoken': 'rd-secret-2',
		'authorization': 'Bearer secret',
		'resolved_url': 'https://secret.example/video',
	}

	result = provider_context(metadata, 'Real-Debrid')

	assert result == {
		'title': 'Sintel',
		'year': 2010,
		'aliases': [{'title': 'Sintel', 'country': 'us'}],
		'debrid_service': 'Real-Debrid',
	}
	result['aliases'][0]['title'] = 'changed'
	assert metadata['aliases'][0]['title'] == 'Sintel'


def test_provider_canary_never_observes_a_secret():
	observed = {}

	def canary(data):
		observed.update(data)
		assert 'debrid_token' not in data
		assert all('token' not in key.lower() for key in data)

	canary(provider_context({'title': 'Sintel', 'debrid_token': 'secret'}))
	assert observed == {'title': 'Sintel'}


def test_sources_use_policy_instead_of_forwarding_debrid_token():
	sources = (
		Path(__file__).parents[2]
		/ 'omega/plugin.video.umbrella/resources/lib/modules/sources.py'
	).read_text(encoding='utf-8')

	assert sources.count('data = provider_context(data, self.debrid_service)') == 3
	assert "'debrid_token': self.debrid_token" not in sources
