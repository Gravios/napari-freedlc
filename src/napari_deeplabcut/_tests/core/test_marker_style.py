"""Per-bodypart marker colors and sizes, the palette rule, and the hold-to-show-names key.

The colors and sizes come from the annotator's config (``bodypart_colors``,
``bodypart_sizes``), which FreeDLC writes from a project's ``[display]`` table, or
from that table directly when a workspace ``project.toml`` is opened.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from napari.layers import Points

import napari_deeplabcut.config.keybinds as keybinds
from napari_deeplabcut.config.models import DLCHeaderModel
from napari_deeplabcut.core import workspace_config as wc
from napari_deeplabcut.core.keypoints import PALETTE_MAX, build_color_cycle, build_color_cycles
from napari_deeplabcut.core.layers import (
    apply_bodypart_sizes,
    keep_bodypart_sizes,
    populate_keypoint_layer_properties,
    set_uniform_point_size,
)

BODYPARTS = ["nose", "head", "tail"]


def _header():
    return DLCHeaderModel.from_config({"scorer": "me", "bodyparts": BODYPARTS, "multianimalproject": False})


def _layer(labels, size=6.0):
    header = _header()
    props = populate_keypoint_layer_properties(
        header, labels=labels, ids=[""] * len(labels), likelihood=np.ones(len(labels)),
        bodypart_colors={"nose": "red"}, bodypart_sizes={"nose": 12},
    )
    data = np.array([[0, i, i] for i in range(len(labels))], dtype=float)
    layer = Points(data, properties=props["properties"], metadata=props["metadata"], size=size)
    layer.metadata["dotsize"] = size
    return layer


def test_gradients_are_sampled_not_truncated():
    # viridis lists 256 colors: taking the first 15 would give 15 near-identical purples
    colors = build_color_cycle(15, "viridis")
    assert np.abs(colors[0] - colors[-1]).max() > 0.5
    # a palette keeps its listed colors, in order
    tab10 = build_color_cycle(3, "tab10")
    np.testing.assert_allclose(tab10[0][:3], [0.12156863, 0.46666667, 0.70588235], atol=1e-6)
    assert PALETTE_MAX >= 20  # tab20 is still a palette


def test_overrides_replace_the_colormap_color():
    cycles = build_color_cycles(_header(), "tab10", overrides={"nose": "#ff0000", "paw": "blue", "tail": "nope"})
    np.testing.assert_allclose(cycles["label"]["nose"], [1, 0, 0, 1])
    assert "paw" not in cycles["label"]                                   # not a bodypart: ignored
    plain = build_color_cycles(_header(), "tab10")
    np.testing.assert_allclose(cycles["label"]["tail"], plain["label"]["tail"])   # unreadable: ignored


def test_bodypart_sizes_survive_resizing_and_apply_to_new_points():
    layer = _layer(["nose", "head", "tail"])
    assert apply_bodypart_sizes(layer)
    np.testing.assert_allclose(layer.size, [12, 6, 6])

    set_uniform_point_size(layer, 9)                                      # the size control
    np.testing.assert_allclose(layer.size, [12, 9, 9])
    assert layer.metadata["dotsize"] == 9

    keep_bodypart_sizes(layer)
    layer.current_properties = {"label": np.array(["nose"]), "id": np.array([""]),
                                "likelihood": np.array([1.0])}
    layer.add([[0, 5, 5]])
    np.testing.assert_allclose(layer.size, [12, 9, 9, 12])

    plain = Points(np.zeros((2, 3)), properties={"label": ["nose", "head"]}, size=4)
    assert not apply_bodypart_sizes(plain)                                 # nothing configured
    set_uniform_point_size(plain, 7)
    np.testing.assert_allclose(plain.size, [7, 7])


def test_project_toml_display_table_reaches_the_config(tmp_path: Path):
    p = tmp_path / "project.toml"
    p.write_text(
        'task = "t"\nbodyparts = ["nose", "head", "tail"]\nschema_version = 1\n'
        '[display]\ndotsize = 5\ncolormap = "tab20"\n'
        '[display.bodyparts]\nnose = { color = "red", size = 9 }\ntail = { color = "#00ff00" }\n'
        '[napari]\npcutoff = 0.4\ncolormap = "Set3"\n'
    )
    cfg = wc.workspace_config_as_dict(p)
    assert cfg["dotsize"] == 5 and cfg["colormap"] == "tab20"             # [display] wins over [napari]
    assert cfg["pcutoff"] == 0.4
    assert cfg["bodypart_colors"] == {"nose": "red", "tail": "#00ff00"}
    assert cfg["bodypart_sizes"] == {"nose": 9}


def test_names_show_only_while_the_key_is_held():
    class Viewer:
        def __init__(self, layers):
            self.layers = layers

    shown = _layer(["nose"])
    hidden = _layer(["head"])
    shown.text.visible = True
    hidden.text.visible = False
    other = Points(np.zeros((1, 3)))                                      # not a keypoint layer
    other.text.visible = False
    viewer = Viewer([shown, hidden, other])

    callback = keybinds._show_names_while_held(keybinds.BindingContext(controls=None, store=None, viewer=viewer))
    held = callback(viewer)
    next(held)                                                            # key pressed
    assert shown.text.visible and hidden.text.visible and not other.text.visible
    try:
        next(held)                                                        # key released
    except StopIteration:
        pass
    assert shown.text.visible and not hidden.text.visible                  # back as they were

    spec = next(s for s in keybinds.SHORTCUTS if s.action is keybinds.ShortcutAction.SHOW_NAMES_WHILE_HELD)
    assert spec.keys == ("N",) and spec.scope == "viewer"
