# mwoDevelop downstream

This fork follows `umbrellaplug/umbrellaplug.github.io@master`.

The Open/Closed boundary is deliberate:

- new policy and tests live under `resources/lib/downstream/` and
  `tests/downstream/`;
- only `sources.py` and `realdebrid.py` contain functional integration hooks;
- external providers receive an allowlisted context without debrid credentials;
- `addon.xml` carries the downstream version and MwoScrapers dependency;
- upstream discovery is centralized in `mwoDevelop/kodi`; this repository does
  not rebase or push upstream changes directly.

## Validate

```bash
python3 -m venv .venv-downstream
. .venv-downstream/bin/activate
python -m pip install pytest
pytest
python tools/rebuild_downstream.py --check
python -m py_compile \
  omega/plugin.video.umbrella/resources/lib/modules/sources.py \
  omega/plugin.video.umbrella/resources/lib/debrid/realdebrid.py \
  omega/plugin.video.umbrella/resources/lib/downstream/*.py
```

See `downstream-patches.yml` for the pinned base and stable patch identities.
