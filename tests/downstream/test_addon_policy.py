from pathlib import Path
from xml.etree import ElementTree

from resources.lib.downstream.addon_policy import (
	OFFICIAL_RELEASE_INDEX,
	external_provider_candidates,
	installed_repository,
	upstream_version_check,
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
	assert addon.attrib['version'] == '6.7.81.17'


def test_optional_youtube_feature_does_not_block_umbrella_installation():
	addon = ElementTree.parse(ADDON_XML).getroot()
	dependencies = {
		import_.attrib['addon']
		for import_ in addon.findall('./requires/import')
	}

	assert 'plugin.video.youtube' not in dependencies


def test_downstream_revision_compares_as_its_upstream_base():
	assert upstream_version_check('6.7.81.5') == ('6.7.81', OFFICIAL_RELEASE_INDEX)


def test_upstream_version_is_unchanged():
	assert upstream_version_check('6.7.81') == ('6.7.81', OFFICIAL_RELEASE_INDEX)


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
