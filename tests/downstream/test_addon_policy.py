from pathlib import Path
from xml.etree import ElementTree

from resources.lib.downstream.addon_policy import (
	OFFICIAL_RELEASE_INDEX,
	installed_repository,
	upstream_version_check,
)

ADDON_XML = (
	Path(__file__).parents[2] / 'omega' / 'plugin.video.umbrella' / 'addon.xml'
)


def test_downstream_addon_identity_is_visible_in_kodi():
	addon = ElementTree.parse(ADDON_XML).getroot()

	assert addon.attrib['id'] == 'plugin.video.umbrella'
	assert addon.attrib['name'] == 'Umbrella (mwoDevelop)'
	assert addon.attrib['version'] == '6.7.81.12'


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
