from pathlib import Path
from xml.etree import ElementTree

from resources.lib.downstream.addon_policy import (
	OFFICIAL_RELEASE_INDEX,
	PUBLIC_RELEASE_STATUS,
	external_provider_candidates,
	fallback_release_status,
	fetch_release_status,
	installed_repository,
	notification_decision,
	parse_addon_version,
	upstream_version_check,
	validate_release_status,
	version_is_newer,
)

ADDON_XML = (
	Path(__file__).parents[2] / 'omega' / 'plugin.video.umbrella' / 'addon.xml'
)
REAL_DEBRID = (
	Path(__file__).parents[2]
	/ 'omega'
	/ 'plugin.video.umbrella'
	/ 'resources'
	/ 'lib'
	/ 'debrid'
	/ 'realdebrid.py'
)


def test_downstream_addon_identity_is_visible_in_kodi():
	addon = ElementTree.parse(ADDON_XML).getroot()

	assert addon.attrib['id'] == 'plugin.video.umbrella'
	assert addon.attrib['name'] == 'Umbrella (mwoDevelop)'
	assert addon.attrib['version'] == '6.7.81.20'


def test_optional_youtube_feature_does_not_block_umbrella_installation():
	addon = ElementTree.parse(ADDON_XML).getroot()
	dependencies = {
		import_.attrib['addon']
		for import_ in addon.findall('./requires/import')
	}

	assert 'plugin.video.youtube' not in dependencies


def test_downstream_revision_compares_as_its_upstream_base():
	assert upstream_version_check('6.7.81.5') == ('6.7.81', OFFICIAL_RELEASE_INDEX)
	assert '/omega/' in OFFICIAL_RELEASE_INDEX


def test_upstream_version_is_unchanged():
	assert upstream_version_check('6.7.81') == ('6.7.81', OFFICIAL_RELEASE_INDEX)


def status(state='qualifying', health='healthy', upstream='6.7.84', stable='6.7.81.20'):
	return {
		'schema': 1,
		'component': 'plugin.video.umbrella',
		'pipeline': {
			'state': state,
			'candidate_id': 'a' * 64 if state != 'in_sync' else None,
			'failure_code': 'patch_conflict' if state == 'blocked' else None,
		},
		'release': {'health': health},
		'versions': {
			'upstream': upstream,
			'stable': stable,
			'stable_upstream_base': '.'.join(stable.split('.')[:3]),
		},
		'upstream': {'commit': 'b' * 40, 'stable_base_commit': 'c' * 40},
		'generated_at': '2026-08-19T10:00:00Z',
		'expires_at': '2026-08-21T10:00:00Z',
	}


def test_release_status_uses_strict_xml_and_numeric_versions():
	assert parse_addon_version(
		'<addon id="plugin.video.umbrella" version="6.7.84" />'
	) == '6.7.84'
	assert version_is_newer('6.7.84.1', '6.7.84')
	assert not version_is_newer('6.7.81.20', '6.7.84')


def test_release_status_is_strict_and_expires():
	assert validate_release_status(status(), now=1787133600)['schema'] == 1
	try:
		validate_release_status(status(), now=1787306401)
	except ValueError as error:
		assert 'expired' in str(error)
	else:
		raise AssertionError('expired status was accepted')


def test_status_fetch_falls_back_to_official_omega_index():
	class Response:
		def __init__(self, code, content):
			self.status_code = code
			self.content = content

	calls = []
	def get(url, timeout):
		calls.append((url, timeout))
		if url == PUBLIC_RELEASE_STATUS:
			return Response(503, b'')
		return Response(200, b'<addon id="plugin.video.umbrella" version="6.7.84"/>')

	result = fetch_release_status(get, '6.7.81.20', now=1787133600)
	assert result['pipeline']['state'] == 'detected'
	assert result['release']['health'] == 'unknown'
	assert calls[1][0] == OFFICIAL_RELEASE_INDEX


def test_notifications_distinguish_pending_stable_blocked_and_incident():
	pending = notification_decision(status(), '6.7.81.20', now=1787133600)
	assert pending['kind'] == 'upstream_pending'
	assert notification_decision(
		status(), '6.7.81.20', last_key=pending['key'],
		last_at=pending['at'], now=1787133601,
	) is None

	available = status(state='in_sync', upstream='6.7.84', stable='6.7.84.1')
	assert notification_decision(
		available, '6.7.81.20', now=1787133600
	)['kind'] == 'stable_available'
	assert notification_decision(
		status(state='blocked'), '6.7.81.20', now=1787133600
	)['kind'] == 'blocked'
	assert notification_decision(
		status(health='incident'), '6.7.81.20', now=1787133600
	)['kind'] == 'incident'


def test_forward_rollback_base_is_not_inferred_from_release_version():
	document = status(state='in_sync', upstream='6.7.84', stable='6.7.84.2')
	document['versions']['stable_upstream_base'] = '6.7.81'
	assert validate_release_status(document, now=1787133600)[
		'versions'
	]['stable_upstream_base'] == '6.7.81'


def test_downstream_repository_is_preferred_without_upstream_test_heuristic():
	class Addon:
		def __init__(self, version):
			self.version = version

		def getAddonInfo(self, key):
			return self.version if key == 'version' else ''

	def addon_factory(addon_id):
		versions = {
			'repository.mwodevelop': '1.0.0',
			'repository.umbrellakodi': '2.2.6',
		}
		if addon_id not in versions:
			raise RuntimeError('not installed')
		return Addon(versions[addon_id])

	assert installed_repository(addon_factory) == (
		'repository.mwodevelop',
		'1.0.0',
	)


def test_missing_repository_has_stable_fallback():
	def missing(_addon_id):
		raise RuntimeError('not installed')

	assert installed_repository(missing) == ('Unknown Repo', 'unknown')


def test_external_provider_candidates_exclude_umbrella_itself():
	addons = [
		{'addonid': 'plugin.video.umbrella', 'name': 'Umbrella (mwoDevelop)'},
		{'addonid': 'script.module.mwoscrapers', 'name': 'MwoScrapers'},
		{'name': 'Malformed module'},
	]

	assert external_provider_candidates(
		addons, 'plugin.video.umbrella'
	) == [
		{'addonid': 'script.module.mwoscrapers', 'name': 'MwoScrapers'},
	]


def test_real_debrid_torrent_cleanup_uses_bounded_transport():
	source = REAL_DEBRID.read_text(encoding='utf-8')
	delete_method = source.split('def delete_torrent', 1)[1].split(
		'def get_link',
		1,
	)[0]

	assert 'rd_transport.request(' in delete_method
	assert "'DELETE'" in delete_method
	assert 'timeout=15' in delete_method
	assert 'session.delete(' not in delete_method


def test_real_debrid_failed_resolution_does_not_delete_torrent_twice():
	source = REAL_DEBRID.read_text(encoding='utf-8')
	resolve_method = source.split('def resolve_magnet', 1)[1].split(
		'def display_magnet_pack',
		1,
	)[0]

	assert 'torrent_deleted = False' in resolve_method
	assert 'if not torrent_deleted:' in resolve_method
