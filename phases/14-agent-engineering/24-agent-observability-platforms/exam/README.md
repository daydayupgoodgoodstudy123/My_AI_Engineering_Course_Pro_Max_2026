# TraceJudge pair session

TraceJudge is a small agent-observability backend, the kind of thing Langfuse, Phoenix and Opik do with a richer UI. Exporters send GenAI-shaped spans (`tracejudge/spans.py`), a scripted LLM judge scores each trace against a rubric (`tracejudge/judge.py`), and `tracejudge/summary.py` turns the spans into one dashboard row per session. Around that sit a human annotation queue (`tracejudge/annotations.py`), prompt-version regression hunting (`tracejudge/regress.py`), live batch ingestion (`tracejudge/ingest.py`) and trace clustering (`tracejudge/clusters.py`). Nothing calls a real model or the network.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_session_dashboard`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the dashboard numbers are wrong.

## Pt 2 `test_annotation_queue`

Keep the review queue and people's annotations in SQLite.

## Pt 3 `test_bisect_prompt_versions`

Quality dropped in production. Find the prompt version that did it.

## Pt 4 `test_ingest_stream`

Ingest span events as they arrive in batches, and push dashboard updates to the browser.

## Pt 5 `test_trace_clusters`

Group traces by the shape of their span tree, and flag the rare shapes.
