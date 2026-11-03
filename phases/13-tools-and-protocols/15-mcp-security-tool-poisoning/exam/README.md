# PoisonGuard pair session

PoisonGuard is the descriptor gate in front of an MCP gateway's merged tool catalog. It scans tool descriptors for injected instructions and pins every approved descriptor by a whole-descriptor digest (`poisonguard/scanner.py`), keeps the approved pins in a JSON manifest (`poisonguard/pins.py`), decides on every refresh which tools the model may see (`poisonguard/refresh.py`), judges a refresh that arrives page by page from many backends as an NDJSON event stream (`poisonguard/stream.py`), and redacts audit records before they are written (`poisonguard/audit.py`). `poisonguard/service.py` wires the gate together for the gateway.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_scan_and_pin`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the scanner fails.

## Pt 2 `test_pin_manifest`

Keep the approved pins.

## Pt 3 `test_refresh_decisions`

Decide what the model gets to see on every refresh.

## Pt 4 `test_decision_stream`

Judge a refresh as its pages come in.

## Pt 5 `test_audit_redaction`

Keep secrets out of the audit log.
