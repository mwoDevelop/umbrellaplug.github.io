from resources.lib.downstream.addon_policy import (
	OFFICIAL_RELEASE_INDEX,
	upstream_version_check,
)


def test_downstream_revision_compares_as_its_upstream_base():
	assert upstream_version_check('6.7.81.5') == ('6.7.81', OFFICIAL_RELEASE_INDEX)


def test_upstream_version_is_unchanged():
	assert upstream_version_check('6.7.81') == ('6.7.81', OFFICIAL_RELEASE_INDEX)
