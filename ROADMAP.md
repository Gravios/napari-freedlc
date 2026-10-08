# Roadmap

Planned work for napari-freedlc's integration with FreeDLC's workspace project
layout. Items here are not yet implemented; they record intent and the design
constraints that shape them.

## Standalone workspace annotation (native read/write of `project.toml`)

**Goal.** Let a FreeDLC workspace project be annotated by opening its `project.toml`
directly in napari, with no `fdlc` command in the loop -- napari loads the
video's original-resolution frames, and on save writes the workspace's
`sources/annotations/<id>/labels.parquet` itself.

**Current state.** Two things exist today and are deliberately narrower:

- **`fdlc annotate` (the supported path).** FreeDLC stages a legacy
  `labeled-data/<id>/` view of a video's original-resolution frames plus a
  synthesized `config.yaml`, launches napari on that, and on close ingests the saved
  coordinates into `labels.parquet` as they were placed, in original pixels, with a
  `labels.toml` recording that space. Conversion to the processed frames happens
  when FreeDLC trains or evaluates. This is complete.
- **`project.toml` schema reader (`core/workspace_config.py`).** napari can open a
  workspace `project.toml` for its keypoint *schema* (bodyparts, skeleton, scorer).
  It does not load workspace frames or save to workspace paths; frames and saving
  still flow through the staging `fdlc annotate` builds.

**Why it is not done yet.** napari's discovery and writer are wired to the
`labeled-data/<dataset>/` path convention (`core/project_paths.py`): the save target
and dataset name are resolved from the literal `labeled-data` token in a path. The
workspace's `sources/annotations/<id>/frames/original/` tree has no such token, so
native read/write means teaching that machinery a second path convention.

The coordinate scale is no longer an obstacle. Labels are stored in the pixels of
the frames they were placed on (original), and `labels.toml` says so, so a native
writer stores what napari shows and needs no transform. Scaling to the processed
frames has exactly one home, FreeDLC's `Project.labels_scale_to`, applied at
training and evaluation time. A native reader must still honour `labels.toml`:
labels written by older FreeDLC versions may be in processed pixels, with the
scale recorded, and have to be scaled *up* for display.

**What it would require.**

- A workspace-aware reader: locate a video's original frames from a `project.toml`
  (or from an annotations folder), load them, and load `labels.parquet` when it
  exists -- converting to original pixels when `labels.toml` says `space =
  "processed"`.
- A workspace-aware writer: on save, write `labels.parquet` (original pixels, image
  names as in `frames/original/`) and a `labels.toml` with `space = "original"`,
  rather than a `labeled-data` CollectedData.
- Proposed markers: `fdlc extract --from-run` currently places a model's
  predictions in the staged CollectedData; a native path would need its own place
  for them that is not mistaken for labels.

Until then, `fdlc annotate` is the supported path; opening `project.toml` in napari
is for schema-correct viewing and labeling that is then ingested by FreeDLC.
