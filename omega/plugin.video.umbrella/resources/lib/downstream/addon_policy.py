"""Downstream add-on metadata policies.

Keep fork-specific release semantics out of the upstream service code.  The
public helpers intentionally accept plain values so they can be tested without
Kodi.
"""

OFFICIAL_RELEASE_INDEX = (
	'https://raw.githubusercontent.com/umbrellaplug/'
	'umbrellaplug.github.io/master/matrix/plugin.video.umbrella/addon.xml'
)
REPOSITORY_IDS = (
	'repository.mwodevelop',
	'repository.umbrellakodi',
	'repository.umbrella',
)


def upstream_version_check(local_version):
	"""Return the upstream version used for comparison and its release index.

	A fourth numeric component is the downstream build revision.  Upstream
	Umbrella treats any version string longer than six characters as a private
	test build and switches to its test repository.  Comparing only the first
	three components preserves upstream release notifications without leaking
	the downstream revision into that heuristic.
	"""
	parts = str(local_version).split('.')
	return '.'.join(parts[:3]), OFFICIAL_RELEASE_INDEX


def installed_repository(addon_factory):
	"""Return the first installed downstream/upstream Umbrella repository."""
	for addon_id in REPOSITORY_IDS:
		try:
			version = addon_factory(addon_id).getAddonInfo('version')
			if version:
				return addon_id, version
		except Exception:
			continue
	return 'Unknown Repo', 'unknown'


def external_provider_candidates(addons, own_addon_id):
	"""Exclude the host plug-in from its external-provider selection list."""
	return [
		addon for addon in addons
		if addon.get('addonid') and addon.get('addonid') != own_addon_id
	]
