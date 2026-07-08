# Behavioural skill evals

A regression net for skills. `review-and-improve` (and humans) mutate skill system
prompts and frontmatter over time; the runtime metrics (fail rate, ratings) lag by
days, so a prompt edit can quietly degrade quality. These evals catch that **before**
merge by scoring a skill's real output against a rubric with an LLM judge.

## Layout

```
evals/
  harness.py          Pure logic: load cases, build judge prompt, parse verdict,
                      decide regression, format report. Unit-tested (tests/test_evals.py).
  run.py              Orchestrator CLI (enqueue → wait → judge → compare → report).
  cases/<skill>.yml   Eval cases per skill: input + rubric + baseline_score.
  results/<date>-<skill>.md   Generated reports.
```

## How a run works

For each case in `evals/cases/<skill>.yml`, `run.py`:

1. enqueues the skill as a real job (`enqueue_job(input, kind=<skill>)`),
2. waits for the runner to finish it,
3. reads the job's summary,
4. asks an Opus judge (via the subscription-auth `claude` CLI) to score the output
   1–5 against the case's rubric,
5. flags a **regression** if the score dropped ≥1 vs the case's `baseline_score`.

`run.py` exits non-zero if any case regressed, so it can gate a change.

> **Not a CI test.** It needs the full stack up (runner consuming the queue, Postgres,
> Redis) and the same subscription auth the runner uses. Run it locally/on-box. The
> *pure* logic is covered by `tests/test_evals.py` in the normal pytest suite.

## Usage

```bash
python -m evals.run --skill chat                 # one skill
python -m evals.run --all                        # every skill with a case file
python -m evals.run --skill chat --update-baseline   # accept current scores as new baselines
python -m evals.run --skill research-report --timeout 1200
```

## Writing a case file

```yaml
skill: chat
cases:
  - name: factual-answer
    input: "What is the capital of France? Answer in one word."
    rubric:
      - "Identifies Paris as the capital of France"
      - "Is concise"
    baseline_score: 5     # omit / null until you've measured a stable score
```

Judge on **substance vs the rubric**, not exact wording — keep rubric bullets about
what a good answer must contain, not phrasing. Leave `baseline_score` null for new or
environment-dependent cases (e.g. `code-review`, which reviews the current branch
diff) so they never false-flag a regression until a human sets a baseline.

## Wiring

`review-and-improve` runs `python -m evals.run --skill <skill>` to baseline before a
skill change and has the dispatched `server-patch` re-run it after, blocking merge on a
regression. See `skills/review-and-improve/SKILL.md` → "Skill-behaviour regression guard".
