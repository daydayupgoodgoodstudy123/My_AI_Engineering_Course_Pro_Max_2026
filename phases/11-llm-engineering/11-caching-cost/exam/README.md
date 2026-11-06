# QuotaFlow

Work on the supplied token-aware admission and usage service. Use Python 3.10+,
the standard library and pytest. All requests, clocks and prices are local fixtures.

1. Repair the legacy admission path while preserving exact quota state.
2. Persist complete SQLite bucket state and atomically append through the supplied usage journal.
3. Implement atomic joint token/RPM admission with exact retry times.
4. Publish cumulative Prometheus text snapshots after completed batches, including identities with only denied decisions.
5. Build the nested user/model usage and cost report; denied work has zero token usage at every level.

Start with `tests/test_parts.py`; unlock one `Part N` test at a time. Keep its
assertions unchanged. The exercise lasts 60 minutes including a 2-minute opening.
