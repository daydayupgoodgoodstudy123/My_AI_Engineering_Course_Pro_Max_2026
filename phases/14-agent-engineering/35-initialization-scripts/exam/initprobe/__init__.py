"""InitProbe: the init script an agent runs before it starts.

The repo's paths are pinned once against the repo root, probes check the workbench, a prereqs
lock lets a later run skip them, every run goes into a history, a TAP stream reports the run
while it happens, and the last-known-good check holds HEAD to a drift budget.
"""
