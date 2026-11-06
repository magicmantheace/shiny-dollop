# stages/

One folder per pipeline stage lands here as the stage is built
(`prep/`, `mesh/`, `texture/`, `rig/`, `animate/`, `catalog/`).
The authoritative stage list and order live in `../stages.py`.
Model stages are subprocess entry points: load → run → exit.
