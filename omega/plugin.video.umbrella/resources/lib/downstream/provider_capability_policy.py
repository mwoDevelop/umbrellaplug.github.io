"""Adapt optional provider capabilities at the downstream boundary."""


def provider_pack_sources(provider, *args, **kwargs):
	"""Call a provider pack scraper when supported, otherwise skip it."""
	handler = getattr(provider, 'sources_packs', None)
	if not callable(handler):
		return []
	return handler(*args, **kwargs)
