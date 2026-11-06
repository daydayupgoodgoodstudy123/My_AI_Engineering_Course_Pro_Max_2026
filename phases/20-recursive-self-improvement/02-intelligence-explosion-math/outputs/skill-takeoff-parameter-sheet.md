---
name: takeoff-parameter-sheet
description: Turn any takeoff or intelligence-explosion claim into a five-parameter sheet (returns r, feedback a, ceiling, cycle duration, initial speed-up) and classify it as a claim about speed, acceleration or criticality.
version: 1.0.0
phase: 20
lesson: 2
tags: [takeoff, intelligence-explosion, returns-to-rnd, reproduction-number, forecasting, forethought, burtsev]
---

Given a claim about AI takeoff (a forecast post, a paper abstract, a lab safety case, a talk transcript, a tweet thread), produce a one-page parameter sheet that makes the claim disagreeable: every number it leans on, where that number came from, and what evidence would move it. The sheet uses the vocabulary of Phase 20 Lesson 02: Forethought's returns to software R&D r (Eth & Davidson 2025; Davidson & Houlden 2025) and Burtsev's recursive reproduction number R_AI (arXiv:2609.00137).

Produce:

1. **Claim type.** Classify the claim as about one or more of:
   - speed: progress is or will be fast (years of progress per year);
   - acceleration: progress is getting faster (the rate itself grows);
   - criticality: each cycle's gains compound into the next (R_AI > 1).
   Quote the sentence that shows which. A claim can be about speed without acceleration (high baseline productivity) and about criticality without visible acceleration (Burtsev's lag). Say which combinations the claim conflates, if any.

2. **Parameter table.** One row per parameter. Columns: implied value or range; the evidence the claim offers; the evidence that would move it; the simulator flag in `code/main.py` that tests it.
   - r, returns to software R&D (doublings of efficiency per doubling of cumulative research). Reference points: Davidson & Houlden median 1.2, range 0.4–3.6; Eth & Davidson by domain (image recognition 1.4, chess 0.8, RL data efficiency 1.6, SAT 3.5, LP 1.1).
   - a, feedback strength (what fraction of research input scales with the system itself) and b, the baseline that does not. Reference: the threshold is a · r > 1 in the fully recursive toy; partial automation with a = 0.5 makes r = 1.2 subcritical.
   - ceiling, OOMs of efficiency headroom before effective limits. Reference: 6–16 OOMs; 10 years-in-1 requires more than 10 OOMs of room.
   - cycle duration, the time from an improvement to its use in the next research cycle (training-run length is a floor).
   - initial speed-up, the jump in research speed at the moment of automation, kept separate from the compounding.

3. **Unit check.** State what the claim means by "a year of progress" (an OOM of effective compute, a benchmark delta, a time-horizon doubling) and whether the comparison baseline is 2024-rate progress. Flag any claim that mixes units.

4. **Sensitivity.** Name the two or three parameters the claim's conclusion is most sensitive to, with the flag combination that reproduces the claim's shape in the toy and the flag combination that breaks it. Report the toy's numbers for both, labelled as toy numbers.

5. **Indicators to watch.** Map the claim onto Burtsev's four measurables: feedback strength, carry-over into successor systems, cycle duration, growth of research difficulty. For each, say what observation in the next twelve months would raise or lower the claim's parameters.

Hard rejects:
- Any claim that says "explosion" or "takeoff" without saying what quantity grows (efficiency, capability score, revenue, headcount-equivalents). Ask for the quantity.
- Any use of a benchmark score as a criticality threshold. Criticality is a property of the loop's structure; a score is a level.
- Any claim that treats a fast baseline (many AI researchers, large compute) as evidence of compounding. Speed and criticality are separate rows.
- Any "years of progress" figure with no unit and no baseline year.

Refusal rules:
- If none of the five parameters can be inferred or bounded from the claim, do not fabricate a sheet. Return the five questions the claimant must answer.
- If the claim is primarily about compute growth rather than software feedback, say so and hand off to the two-factor framing of Lesson 03 of this phase rather than forcing it into this sheet.
- If the claim is a forecast with explicit scenario dates (AI 2027 style), produce the sheet but also hand off to Lesson 22 of this phase for the forecast-comparison method; do not adjudicate the dates here.

Output format (one page):
- **Claim and type** (two lines, with the quoted sentence)
- **Parameter table** (five rows, four columns)
- **Unit check** (two lines)
- **Sensitivity** (three bullets, each with a toy flag combination and its toy result)
- **Indicators to watch** (four bullets)
- **What would change my mind** (one line per parameter)
- **Sources** (the claim; Davidson & Houlden 2025; Burtsev 2026; and the toy, labelled as a toy)
