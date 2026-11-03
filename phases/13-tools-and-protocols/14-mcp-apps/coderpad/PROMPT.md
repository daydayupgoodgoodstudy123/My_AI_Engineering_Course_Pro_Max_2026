# Authorize an embedded app bridge

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

An embedded timeline app can ask its host to read or export notes. Finish the bridge policy before any action runs.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

bridge(origin,message,allowed_origin,permissions): reject a different origin first with {'ok':False,'error':'origin'}. message must then be a dict with exact keys id,method,params, where id is a nonempty string and params is dict; malformed returns error 'message'. Allowed methods notes/read and notes/export require permissions 'read' and 'export' respectively. Unknown method returns error 'method'; missing permission returns error 'permission'. On success return {'ok':True,'id':id,'method':method,'params':deep_copy_of_params}. Do not execute any operation.
timeline(titles) returns '<ul>'+one '<li>'+HTML-escaped title+'</li>' per title+'</ul>'; escape &, <, >, quotes and apostrophes with html.escape's defaults. Preserve title order.

## Bonus contract

resource(uri,enabled) returns {'uri':uri,'mimeType':'text/html'} only if enabled is True and uri is a string beginning ui:// with a nonempty suffix; otherwise raise ValueError.

## Commands

```bash
python3 run_tests.py --list
python3 run_tests.py --core
python3 run_tests.py --core -k keyword_from_test_name
python3 run_tests.py --bonus
python3 run_tests.py
```

Read the complete contract before starting. All fixture shapes not declared invalid are supplied valid.
There are no undisclosed external-service requirements. At minute 45, save and record the current result.
Use your own timer; the test runner does not enforce a deadline. Locally stored tests and solutions are readable,
so strict mode relies on your self-discipline or a separate interviewer. Do not read `solution/` or `INTERVIEWER.md` during the attempt.
