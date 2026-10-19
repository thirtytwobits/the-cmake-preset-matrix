#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Tests for preset group discovery and default metadata."""

from tcpm._data_model import get_preset_group_names, make_default_meta_presets


def test_default_meta_presets():
    """Initialize every preset group without relying on instance annotations."""
    meta_presets = make_default_meta_presets()

    assert meta_presets.source == {}
    assert meta_presets.version == 1
    assert meta_presets.static == {}
    assert meta_presets.word_separator == "-"
    assert meta_presets.onload == []

    for name in ("configure", "build", "test", "package", "workflow"):
        group = meta_presets.groups[name]
        assert group.name == name
        assert group.prefix == f"{name}-"
        assert group.common == []
        assert group.shape == {}
        assert group.parameters == {}
        assert group.shape_parameters == {}
        assert group.exclude == []


def test_preset_group_names():
    """Discover every preset group in declaration order."""
    assert get_preset_group_names() == [
        "configurePresets",
        "buildPresets",
        "testPresets",
        "packagePresets",
        "workflowPresets",
    ]
