# Route with bounded fallback

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A model router should fail over on transient outages while refusing to retry invalid requests.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

route(providers,prompt,prices): providers is an ordered list of (name,callable); call(prompt) returns {'text':str,'input_tokens':int,'output_tokens':int}. TransientError means append name to attempted and continue; any other Exception propagates immediately. Return {'provider':name,'text':text,'attempted':[names through success],'cost':input_tokens*prices[name][0]+output_tokens*prices[name][1]}. Prices are per token and valid; only successful-call usage is available in this exercise, so failed attempts have no cost estimate. No provider runs more than once. If all fail (including empty list) raise ExhaustedError(attempted); its provided attempted attribute records names. No sleeping, network, or random retries.

## Bonus contract

eligible(providers,requirements) returns names sorted by (price,name), retaining only providers whose capability set includes requirements. Each provider is {'name','capabilities':set,'price':number}.

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
