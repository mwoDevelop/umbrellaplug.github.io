"""Downstream add-on metadata and release-status policies.

Keep fork-specific release semantics out of the upstream service code.  The
public helpers intentionally accept plain values so they can be tested without
Kodi.
"""

import json
import re
from datetime import datetime, timezone
from xml.etree import ElementTree

OFFICIAL_RELEASE_INDEX = (
	'https://raw.githubusercontent.com/umbrellaplug/'
	'umbrellaplug.github.io/master/omega/plugin.video.umbrella/addon.xml'
)
PUBLIC_RELEASE_STATUS = (
	'https://mwodevelop.github.io/kodi/status/umbrella.json'
)
STATUS_SCHEMA = 1
STATUS_MAX_BYTES = 64 * 1024
STATUS_REMINDER_SECONDS = 72 * 60 * 60
REQUEST_TIMEOUT = (3.05, 8)
PIPELINE_STATES = frozenset(('in_sync', 'detected', 'qualifying', 'blocked'))
RELEASE_HEALTH = frozenset(('healthy', 'incident', 'unknown'))
SAFE_FAILURE = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,63}$')
HEX40 = re.compile(r'^[0-9a-f]{40}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
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


def version_tuple(value):
	"""Return a strict numeric Kodi version tuple."""
	parts = str(value).split('.')
	if not parts or any(not part.isdigit() for part in parts):
		raise ValueError('release version must contain numeric components')
	return tuple(int(part) for part in parts)


def version_is_newer(candidate, current):
	"""Compare numeric Kodi versions without string-ordering ambiguity."""
	candidate_parts = version_tuple(candidate)
	current_parts = version_tuple(current)
	width = max(len(candidate_parts), len(current_parts))
	return candidate_parts + (0,) * (width - len(candidate_parts)) > (
		current_parts + (0,) * (width - len(current_parts))
	)


def parse_addon_version(payload, addon_id='plugin.video.umbrella'):
	"""Read an add-on version from XML using a real parser."""
	if isinstance(payload, str):
		payload = payload.encode('utf-8')
	root = ElementTree.fromstring(payload)
	candidates = [root] if root.tag == 'addon' else root.findall('.//addon')
	for addon in candidates:
		if addon.attrib.get('id') == addon_id:
			version = addon.attrib.get('version', '')
			version_tuple(version)
			return version
	raise ValueError('Umbrella add-on descriptor is missing')


def _timestamp(value):
	if not isinstance(value, str) or not value.endswith('Z'):
		raise ValueError('status timestamp must use UTC Z form')
	try:
		return datetime.fromisoformat(value[:-1] + '+00:00').timestamp()
	except ValueError as error:
		raise ValueError('status timestamp is invalid') from error


def validate_release_status(document, now=None):
	"""Validate the public, notification-only release status document."""
	if not isinstance(document, dict) or document.get('schema') != STATUS_SCHEMA:
		raise ValueError('unsupported Umbrella status schema')
	if document.get('component') != 'plugin.video.umbrella':
		raise ValueError('unexpected Umbrella status component')
	pipeline = document.get('pipeline')
	release = document.get('release')
	versions = document.get('versions')
	upstream = document.get('upstream')
	if not isinstance(pipeline, dict) or pipeline.get('state') not in PIPELINE_STATES:
		raise ValueError('invalid Umbrella pipeline state')
	if not isinstance(release, dict) or release.get('health') not in RELEASE_HEALTH:
		raise ValueError('invalid Umbrella release health')
	if not isinstance(versions, dict):
		raise ValueError('missing Umbrella status versions')
	for field in ('upstream', 'stable', 'stable_upstream_base'):
		version_tuple(versions.get(field, ''))
	if not isinstance(upstream, dict) or not HEX40.fullmatch(
		str(upstream.get('commit', ''))
	):
		raise ValueError('invalid Umbrella upstream commit')
	candidate_id = pipeline.get('candidate_id')
	if candidate_id is not None and not HEX64.fullmatch(str(candidate_id)):
		raise ValueError('invalid Umbrella candidate id')
	failure = pipeline.get('failure_code')
	if failure is not None and not SAFE_FAILURE.fullmatch(str(failure)):
		raise ValueError('invalid Umbrella failure code')
	generated = _timestamp(document.get('generated_at'))
	expires = _timestamp(document.get('expires_at'))
	if generated >= expires:
		raise ValueError('Umbrella status validity window is empty')
	now = datetime.now(timezone.utc).timestamp() if now is None else float(now)
	if expires <= now:
		raise ValueError('Umbrella status expired')
	return document


def fallback_release_status(installed_version, upstream_version, now=None):
	"""Build a bounded fallback when the public pipeline status is unavailable."""
	now = datetime.now(timezone.utc).timestamp() if now is None else float(now)
	base, _index = upstream_version_check(installed_version)
	state = 'detected' if version_is_newer(upstream_version, base) else 'in_sync'
	def stamp(value):
		return datetime.fromtimestamp(value, timezone.utc).isoformat().replace(
			'+00:00', 'Z'
		)
	return {
		'schema': STATUS_SCHEMA,
		'component': 'plugin.video.umbrella',
		'pipeline': {
			'state': state,
			'candidate_id': None,
			'failure_code': 'status_unavailable',
		},
		'release': {'health': 'unknown'},
		'versions': {
			'upstream': upstream_version,
			'stable': installed_version,
			'stable_upstream_base': base,
		},
		'upstream': {'commit': '0' * 40},
		'generated_at': stamp(now),
		'expires_at': stamp(now + 6 * 60 * 60),
	}


def fetch_release_status(get, installed_version, now=None):
	"""Fetch validated public status, falling back to the official Omega XML."""
	try:
		response = get(PUBLIC_RELEASE_STATUS, timeout=REQUEST_TIMEOUT)
		if response.status_code != 200 or len(response.content) > STATUS_MAX_BYTES:
			raise ValueError('status response rejected')
		document = json.loads(response.content.decode('utf-8'))
		return validate_release_status(document, now=now)
	except Exception:
		response = get(OFFICIAL_RELEASE_INDEX, timeout=REQUEST_TIMEOUT)
		if response.status_code != 200 or len(response.content) > STATUS_MAX_BYTES:
			raise ValueError('official release response rejected')
		upstream_version = parse_addon_version(response.content)
		return fallback_release_status(installed_version, upstream_version, now=now)


def notification_decision(document, installed_version, last_key='', last_at=0, now=None):
	"""Return a deduplicated notification description or ``None``."""
	validate_release_status(document, now=now)
	now = datetime.now(timezone.utc).timestamp() if now is None else float(now)
	pipeline = document['pipeline']
	release = document['release']
	versions = document['versions']
	if release['health'] == 'incident':
		kind = 'incident'
		values = (versions['stable'],)
	elif version_is_newer(versions['stable'], installed_version):
		kind = 'stable_available'
		values = (versions['stable'],)
	elif pipeline['state'] == 'blocked':
		kind = 'blocked'
		values = (versions['upstream'], pipeline.get('failure_code') or 'unknown')
	elif version_is_newer(versions['upstream'], versions['stable_upstream_base']):
		kind = 'upstream_pending'
		values = (versions['upstream'], versions['stable'])
	else:
		return None
	key = '|'.join((kind, versions['upstream'], versions['stable'], str(
		pipeline.get('failure_code') or ''
	)))
	persistent = kind in ('incident', 'blocked')
	try:
		last_at = float(last_at or 0)
	except (TypeError, ValueError):
		last_at = 0
	if key == last_key and (not persistent or now - last_at < STATUS_REMINDER_SECONDS):
		return None
	return {'kind': kind, 'values': values, 'key': key, 'at': str(int(now))}


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
