"""Reading a FreeDLC workspace ``project.toml`` as a DLC config dict.

These tests avoid importing the package root (which pulls in napari); they import
``core.workspace_config`` and ``config.models`` directly. ``config.models`` is the real
consumer of the translated dict, so feeding the output through
``DLCHeaderModel.from_config`` is the load-bearing check that the translation is
actually accepted, not merely well-shaped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from napari_deeplabcut.config.models import DLCHeaderModel
from napari_deeplabcut.core import workspace_config as wc

SINGLE = """\
task = "rodent"
bodyparts = ["head_nose", "head_mid", "hip_left", "hip_right", "tail_V6"]
created = "2026-08-28T00:00:00+00:00"
experimenters = ["gravio"]
multi_animal = false
individuals = []
unique_bodyparts = []
skeleton = [["head_nose", "head_mid"], ["hip_left", "hip_right"]]
notes = ""
schema_version = 1
"""

MULTI = """\
task = "socialmice"
bodyparts = ["snout", "tailbase"]
experimenters = ["gravio"]
multi_animal = true
individuals = ["mouse1", "mouse2"]
unique_bodyparts = ["corner"]
skeleton = [["snout", "tailbase"]]
schema_version = 1
"""


def _write(tmp_path: Path, text: str, name: str = "project.toml") -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


def test_recognises_workspace_manifest(tmp_path):
    assert wc.is_workspace_manifest(_write(tmp_path, SINGLE))


def test_config_yaml_is_not_a_workspace_manifest(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("bodyparts:\n  - a\n")
    assert not wc.is_workspace_manifest(p)


def test_pyproject_toml_is_not_a_workspace_manifest(tmp_path):
    assert not wc.is_workspace_manifest(_write(tmp_path, '[project]\nname = "x"\nbodyparts = ["a"]\n'))


def test_mufasa_manifest_is_not_a_workspace_manifest(tmp_path):
    assert not wc.is_workspace_manifest(_write(tmp_path, '[project]\nproject_name = "x"\n[pose]\nbody_parts = ["a"]\n'))


def test_missing_and_garbage_are_not_manifests(tmp_path):
    assert not wc.is_workspace_manifest(tmp_path / "nope.toml")
    assert not wc.is_workspace_manifest(_write(tmp_path, "this is = = not toml"))


def test_single_animal_translation(tmp_path):
    cfg = wc.workspace_config_as_dict(_write(tmp_path, SINGLE))
    assert cfg["Task"] == "rodent" and cfg["scorer"] == "gravio"
    assert cfg["bodyparts"] == ["head_nose", "head_mid", "hip_left", "hip_right", "tail_V6"]
    assert cfg["skeleton"] == [["head_nose", "head_mid"], ["hip_left", "hip_right"]]
    assert cfg["multianimalproject"] is False and cfg["individuals"] == []


def test_multi_animal_translation(tmp_path):
    cfg = wc.workspace_config_as_dict(_write(tmp_path, MULTI))
    assert cfg["multianimalproject"] is True
    assert cfg["individuals"] == ["mouse1", "mouse2"]
    assert cfg["uniquebodyparts"] == ["corner"]
    assert cfg["multianimalbodyparts"] == ["snout", "tailbase"]


def test_scorer_falls_back_when_no_experimenter(tmp_path):
    text = SINGLE.replace('experimenters = ["gravio"]', "experimenters = []")
    assert wc.workspace_config_as_dict(_write(tmp_path, text))["scorer"] == wc.DEFAULT_SCORER


def test_display_defaults_and_napari_override(tmp_path):
    cfg = wc.workspace_config_as_dict(_write(tmp_path, SINGLE))
    assert (cfg["dotsize"], cfg["pcutoff"], cfg["colormap"]) == (
        wc.DEFAULT_DOTSIZE, wc.DEFAULT_PCUTOFF, wc.DEFAULT_COLORMAP
    )
    over = wc.workspace_config_as_dict(
        _write(tmp_path, SINGLE + "\n[napari]\ndotsize = 12\npcutoff = 0.1\ncolormap = 'plasma'\n")
    )
    assert (over["dotsize"], over["pcutoff"], over["colormap"]) == (12, 0.1, "plasma")


def test_read_manifest_rejects_non_manifest(tmp_path):
    with pytest.raises(ValueError, match="not a FreeDLC workspace"):
        wc.read_workspace_manifest(_write(tmp_path, '[project]\nname = "x"\n'))


def test_translated_single_animal_is_accepted_by_header_model(tmp_path):
    header = DLCHeaderModel.from_config(wc.workspace_config_as_dict(_write(tmp_path, SINGLE)))
    assert header.is_single_animal and header.scorer == "gravio"
    assert header.bodyparts == ["head_nose", "head_mid", "hip_left", "hip_right", "tail_V6"]


def test_translated_multi_animal_is_accepted_by_header_model(tmp_path):
    header = DLCHeaderModel.from_config(wc.workspace_config_as_dict(_write(tmp_path, MULTI)))
    assert not header.is_single_animal
    assert header.individuals[:2] == ["mouse1", "mouse2"]
    assert set(header.bodyparts) >= {"snout", "tailbase"}
