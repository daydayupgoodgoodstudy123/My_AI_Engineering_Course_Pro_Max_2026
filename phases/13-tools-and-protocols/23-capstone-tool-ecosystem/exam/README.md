# ResearchOps pair session

ResearchOps is the research-and-report system from the Phase 13 capstone, simulated in process for MCP `2026-07-28`. The agent (`researchops/agent.py`) discovers the research server, searches for papers through an authorization gateway (`researchops/gateway.py`), asks a writer agent for summaries over A2A, and gets the report back as a task that it polls with `tasks/get`. `researchops/server.py` simulates the research MCP server and `researchops/trace.py` keeps the spans. `researchops/catalog.py` holds the paper fixture the search reads, `researchops/job.py` runs a research job under hard limits, `researchops/report.py` streams the Markdown report, and `researchops/evidence.py` works out what a run actually proves.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_research_run`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why a research run goes wrong.

## Pt 2 `test_catalog_roundtrip`

Keep the paper catalog in a CSV file.

## Pt 3 `test_bounded_job`

Run a research job within its budget.

## Pt 4 `test_report_stream`

Stream the report in a fixed order while the summaries arrive.

## Pt 5 `test_evidence_claims`

Work out which claims a run proves, and what evidence each one still lacks.
