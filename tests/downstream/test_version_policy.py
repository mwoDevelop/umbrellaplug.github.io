import pytest

from resources.lib.downstream.version_policy import numeric_version


def test_empty_fresh_install_marker_is_treated_as_zero():
	assert numeric_version("", default=0) == 0
	assert numeric_version("  ", default=0) == 0


def test_version_numbers_preserve_existing_comparison_semantics():
	assert numeric_version("6.7.68") == 6768
	assert numeric_version("6.7.81.14") == 678114


def test_invalid_required_version_is_rejected():
	with pytest.raises(ValueError, match="invalid Umbrella version"):
		numeric_version("6.7.x")
