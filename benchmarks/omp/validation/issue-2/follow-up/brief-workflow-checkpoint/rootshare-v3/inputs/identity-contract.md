# 0001: A concept is a 2D motif plus a 3D treatment

Status: accepted, 2026-11-10

## Context

A logo has to work as a flat favicon at 16 px and as a lit 3D object at 2000 px, and every export must
show the same mark. Free-form 3D modeling per concept gives each render its own geometry, so the flat
exports drift from the hero and agents spend their effort on Blender code instead of the idea.

## Decision

Every concept is a **motif**, one 2D master in a fixed SVG contract (`motif.svg` -> `motif.json`),
plus a **treatment**, a 3D recipe composed from shared, parameterized components in `scene.toml`.
Flat exports come straight from the motif; every 3D component reads the same contours. The agent
authors motifs with
a small Python API and edits scene parameters; raw `bpy` (`scene.py`) remains a fallback for concepts
the components cannot express.

## Consequences

- Flat and 3D always match, and the QA loop can fix a concept by editing parameters (framing, heights,
  lighting) rather than code.
- Concept pools scale combinatorially (metaphor x treatment x material) and stay judgeable in text before
  any render exists.
- Looks that need bespoke geometry cost the agent a `scene.py`; the component catalog grows when a fallback
  pattern repeats.
