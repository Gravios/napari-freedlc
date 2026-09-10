"""Read a FreeDLC workspace ``project.toml`` as a DeepLabCut config dict.

napari-deeplabcut is built around the legacy DLC project: a ``config.yaml`` whose keys
(``bodyparts``, ``skeleton``, ``scorer`` ...) drive the keypoint layer, and a
``labeled-data/<dataset>/`` tree of frames to annotate. FreeDLC's workspace layout
stores the same *schema* differently -- a flat ``project.toml`` -- so without help
napari cannot open a workspace project to set up its keypoint layer.

This module is the schema seam, and it is deliberately only that. It translates a
workspace ``project.toml`` into the exact dict :func:`napari_deeplabcut.core.io.read_config`
already consumes; ``io.load_config`` dispatches to it by file name, and the config
reader accepts ``project.toml`` alongside ``config.yaml``.

It does *not* teach napari the workspace's frame layout or saving. That is on purpose.
napari's discovery and writer are wired to the ``labeled-data/<dataset>/`` convention
(see :mod:`napari_deeplabcut.core.project_paths`), which the workspace's
``sources/annotations/<id>/frames/`` tree does not use, and the FreeDLC side already
bridges this: ``dlc-ws annotate`` stages a ``labeled-data`` view of a video's frames
plus a synthesized config, launches napari on that, and on close scales the saved
coordinates from the original-resolution frames into the processed space the model
trains on. Keeping napari purely legacy-shaped -- reading project.toml only for the
schema -- means the original/processed split and the annotation scale stay entirely on
the FreeDLC side, with a single home for the coordinate transform. Reproducing the
scale here would either duplicate that logic or, because annotation happens on
original-resolution frames, write processed-space coordinates into a CollectedData that
references those frames -- an internally inconsistent artifact.

The mapping is total on the keys the reader touches and conservative elsewhere:

* ``bodyparts``/``skeleton``/``multianimalproject``/``individuals`` come from the
  manifest (``multi_animal`` is spelled with an underscore there). A multi-animal DLC
  config carries its markers under ``multianimalbodyparts``, the key the reader's
  multi-animal branch uses, so both keys are populated.
* ``scorer`` has no workspace equivalent -- the workspace records *experimenters*, a
  list -- so the first experimenter is used, falling back to ``"labeler"``.
* ``dotsize``/``pcutoff``/``colormap`` are display preferences the manifest does not
  carry; defaults are supplied and may be overridden from an optional ``[napari]`` table.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # the package supports 3.10, where tomllib is not in the stdlib
    import tomli as tomllib

__all__ = [
    "WORKSPACE_MANIFEST_NAME",
    "DEFAULT_SCORER",
    "DEFAULT_DOTSIZE",
    "DEFAULT_PCUTOFF",
    "DEFAULT_COLORMAP",
    "is_workspace_manifest",
    "read_workspace_manifest",
    "workspace_config_as_dict",
]

WORKSPACE_MANIFEST_NAME = "project.toml"

DEFAULT_SCORER = "labeler"
DEFAULT_DOTSIZE = 6
DEFAULT_PCUTOFF = 0.6
DEFAULT_COLORMAP = "viridis"


def is_workspace_manifest(path: str | Path) -> bool:
    """True if ``path`` is a FreeDLC workspace ``project.toml``.

    Recognition is by name plus a cheap content probe: a top-level ``bodyparts`` list
    and no ``[project]`` table (which would make it a pyproject, or a mufasa manifest
    that nests everything under ``[project]``/``[pose]``). The probe keeps napari from
    reading an unrelated ``project.toml`` as a DLC config.
    """
    p = Path(path)
    if p.name.lower() != WORKSPACE_MANIFEST_NAME or not p.is_file():
        return False
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return isinstance(data, dict) and "bodyparts" in data and "project" not in data


def read_workspace_manifest(path: str | Path) -> dict[str, Any]:
    """Load and lightly validate a workspace ``project.toml``.

    Raises:
        ValueError: if the file is not a readable workspace manifest.
    """
    p = Path(path)
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as err:
        raise ValueError(f"could not read workspace manifest {p}: {err}") from err
    if not isinstance(data, dict) or "bodyparts" not in data:
        raise ValueError(f"{p} is not a FreeDLC workspace project.toml (no top-level bodyparts)")
    return data


def _scorer(manifest: dict[str, Any]) -> str:
    for name in manifest.get("experimenters") or []:
        if str(name).strip():
            return str(name).strip()
    return DEFAULT_SCORER


def workspace_config_as_dict(path: str | Path) -> dict[str, Any]:
    """Return the DLC config dict for the workspace project at ``path``.

    Carries exactly the keys :func:`napari_deeplabcut.core.io.read_config` reads. The
    bodypart key depends on the mode, matching how DLC writes a config: single-animal
    projects read ``bodyparts``; multi-animal projects read ``multianimalbodyparts``
    (the same marker list) plus ``individuals`` and ``uniquebodyparts``. Both are
    populated so either branch of ``DLCHeaderModel.from_config`` is satisfied.
    """
    manifest = read_workspace_manifest(path)
    napari_prefs = manifest.get("napari") if isinstance(manifest.get("napari"), dict) else {}
    bodyparts = [str(b) for b in (manifest.get("bodyparts") or [])]

    return {
        "Task": manifest.get("task", ""),
        "scorer": _scorer(manifest),
        "bodyparts": bodyparts,
        "multianimalbodyparts": bodyparts,
        "skeleton": [list(edge) for edge in (manifest.get("skeleton") or [])],
        "multianimalproject": bool(manifest.get("multi_animal", False)),
        "individuals": [str(i) for i in (manifest.get("individuals") or [])],
        "uniquebodyparts": [str(u) for u in (manifest.get("unique_bodyparts") or [])],
        "dotsize": napari_prefs.get("dotsize", DEFAULT_DOTSIZE),
        "pcutoff": napari_prefs.get("pcutoff", DEFAULT_PCUTOFF),
        "colormap": napari_prefs.get("colormap", DEFAULT_COLORMAP),
    }
