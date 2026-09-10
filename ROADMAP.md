# Roadmap

Planned work for napari-freedlc's integration with FreeDLC's workspace project
layout. Items here are not yet implemented; they record intent and the design
constraints that shape them.

## Standalone workspace annotation (native read/write of `project.toml`)

**Goal.** Let a FreeDLC workspace project be annotated by opening its `project.toml`
directly in napari, with no `dlc-ws` command in the loop -- napari loads the
video's original-resolution frames, and on save writes the workspace's
`sources/annotations/<id>/labels.parquet` itself, already in the processed
coordinate space the model trains on.

**Current state.** Two things exist today and are deliberately narrower:

- **`dlc-ws annotate` (the supported path).** FreeDLC stages a legacy
  `labeled-data/<id>/` view of a video's original-resolution frames plus a
  synthesized `config.yaml`, launches napari on that, and on close scales the saved
  coordinates from original into processed space when ingesting to `labels.parquet`.
  This is complete and scale-correct.
- **`project.toml` schema reader (`core/workspace_config.py`).** napari can open a
  workspace `project.toml` for its keypoint *schema* (bodyparts, skeleton, scorer).
  It does not load workspace frames or save to workspace paths; frames and saving
  still flow through the staging `dlc-ws annotate` builds.

**Why it is not done yet.** napari's discovery and writer are wired to the
`labeled-data/<dataset>/` path convention (`core/project_paths.py`): the save target
and dataset name are resolved from the literal `labeled-data` token in a path. The
workspace's `sources/annotations/<id>/frames/` tree has no such token, so native
read/write means teaching that machinery a second path convention.

The harder half is the coordinate scale. It currently lives in exactly one place --
FreeDLC's ingest step -- and annotation happens on original-resolution frames. A
naive "save at processed scale" inside napari would write processed-space
coordinates into an artifact that references original-resolution frames, which is
internally inconsistent (a marker at x=96 on a 1920px frame). Any standalone writer
must therefore keep the frame references and the coordinate space in the same scale
-- e.g. write `labels.parquet` whose image column points at the processed frames and
whose coordinates are processed-space -- and must not become a second, divergent copy
of the scale transform.

**What it would require.**

- A workspace-aware reader: locate a video's original frames from a `project.toml`
  (or from an annotations folder), load them, and -- when a `labels.parquet` already
  exists -- scale its processed-space coordinates *up* to original space for display,
  so existing labels round-trip.
- A workspace-aware writer: on save, scale original-space coordinates *down* to
  processed space and write `labels.parquet` with processed frame references, rather
  than a `labeled-data` CollectedData.
- A single, shared definition of the per-video anisotropic scale
  (`scale_x`, `scale_y`), derived from the original/processed video dimensions, used
  by both the reader (up) and the writer (down), so the transform is not duplicated.

Until then, `dlc-ws annotate` is the path that produces correct processed-space
labels; opening `project.toml` in napari is for schema-correct viewing and labeling
that is then ingested by FreeDLC.
