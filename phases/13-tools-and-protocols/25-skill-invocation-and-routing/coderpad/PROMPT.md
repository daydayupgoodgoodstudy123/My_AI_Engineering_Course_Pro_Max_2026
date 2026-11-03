# Route or abstain

Original interview simulation · 45 minutes · Python 3.10+ · standard library only.
This is independent practice, not an Edison Scientific question or scoring policy.

## Scenario

A router activates skills too aggressively. Separate actor eligibility from selection and abstain on ambiguous matches.

## Candidate work

Edit only `starter/main.py`. Keep public signatures and supplied helpers intact.
`tests/test_exam.py` and fixtures are provided. You may add your own tests in a new `tests/test_candidate.py`.
Explain your plan briefly, then implement the core before attempting the bonus.

## Core contract

route(skills,query,actor,explicit=None): skills are dicts {'name':unique str,'human':bool,'model':bool,'keywords':set of lowercase tokens}. actor must be 'human' or 'model', otherwise ValueError. Eligibility is the skill's boolean for that actor. If explicit is non-None, return {'name':explicit,'reason':'explicit'} only for an eligible exact name; otherwise {'name':None,'reason':'ineligible'} (includes unknown name). Do not fall back to keyword routing after explicit rejection. For implicit routing, tokenize query with regex [a-z0-9]+ after casefolding and score each eligible skill by count of intersecting keyword tokens. Unique maximum >0 returns reason 'matched'. Tied positive maxima return name None/reason 'ambiguous'. No positive score returns name None/reason 'no_match'. Input order must not resolve ties.

## Bonus contract

matrix(skills) returns {'human':sorted eligible names,'model':sorted eligible names}, preserving the independence of the two actor policies.

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
