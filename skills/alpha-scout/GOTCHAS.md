# alpha-scout — gotchas

- 2026-09-23 (birth): the fence is two files — FAMILIES.md `status: open`
  sections and LESSONS.md prunes. Everything else in the repo is context
  for MINING, not license to generate. When both give you nothing, zero
  files is the correct output.
- 2026-09-23: mined E-0006-class offers must quote the offering ledger
  entry verbatim in the idea_text (the A-0003 filing precedent) so triage
  can verify the provenance without a hunt.
- 2026-10-04 capacity-check Glob false-zero: the skill runs inside an
  ai-server workspace clone whose cwd is NOT the atlas repo. A bare
  `Glob("alpha-lab/ideas/*/state.json")` resolves relative to the
  workspace dir, finds nothing, and returns a false-zero active count —
  making the scout think the pipeline is empty when it is not. Always
  supply the explicit path parameter:
  `Glob(pattern="alpha-lab/ideas/*/state.json",
        path="/Users/alfredbot.ai.butler/Documents/repos/atlas")`.
  False-zero causes the scout to file new ideas past the capacity ceiling.
- 2026-10-04 capacity-check Glob, the REAL mechanism (supersedes the
  remedy in the 'capacity-check Glob false-zero' entry above): the
  `path=` parameter is IGNORED in this harness, and so is a single-`*`
  directory wildcard. Measured this run:
  Glob(pattern="alpha-lab/ideas/*/state.json", path="<atlas>") -> 0
  hits; Glob(pattern="<atlas-abs>/alpha-lab/ideas/*/state.json") -> 0
  hits TOO (single `*` across a directory level silently matches
  nothing); Glob(pattern="<atlas-abs>/alpha-lab/ideas/**/*.json") ->
  all 13 ideas. So `path=` does NOT fix the false zero. Use an
  ABSOLUTE pattern with `**`:
  `Glob(pattern="/Users/alfredbot.ai.butler/Documents/repos/atlas/alpha-lab/ideas/**/*.json")`
  then Read each A-####/state.json. Cross-check: Read on an absolute
  atlas path works fine even when Glob reports nothing, so if Glob
  says the pipeline is empty, verify with a Read of a known file
  before believing it. A false zero makes the scout file past
  max_active_ideas.
- 2026-10-04 Bash is sandboxed to the ai-server dir, not atlas:
  `wc`/`head` on an atlas path are BLOCKED ('may only … from the
  allowed working directories'). This is why the skill's 'no shell'
  framing holds in practice — do the whole capacity/mining sweep with
  Glob+Read+Grep, which all reach atlas normally. Grep with an atlas
  `path=` DOES work (unlike Glob's `path=`), including `glob=`
  filters.
- 2026-10-04 the sealed-but-unrun blind spot (E-0098/E-0099): four
  consecutive scout runs re-filed the same F-08 NAV-discount candidate
  that had been idea A-0013 since the second of them, burning three of
  12 daily job slots. A `carded` idea has run nothing, so it is in NO
  trials registry (legitimately — a card evaluates nothing) and its
  INBOX line is already checked: both registries a dedup sweep
  naturally reads report it as 'never tried'. Mandatory extra dedup
  step before filing ANYTHING: list non-terminal ideas/*/state.json
  (stage != verdict), then Grep each one's card.md and
  research/triage.md for the candidate's family string and two
  mechanism keywords. A hit => do not file.
- 2026-10-04 refinement slots are currently ALL spent-or-declined:
  A-0006/A-0007/A-0008/A-0009/A-0010 each DECLINED refinement
  explicitly with numbers in their DECISION, and the F-05 (daily +
  quarterly VRP) and F-01 (both daily-bar month-turn) expression
  questions are CLOSED by lesson. Don't hunt for §2c candidates in
  these — read the DECISION's own 'refinement DECLINED' paragraph
  first and save the sweep.
- 2026-10-04 mining beats inventing, and the richest vein is a
  DECISION's 'What this verdict explicitly does NOT cover' section —
  E-0096 item 3 handed over small-cap PEAD ('where the documented
  drift actually lives') as explicitly uncovered ground inside an open
  family. Quote that item verbatim in idea_text (the A-0003/E-0006
  precedent) so triage can verify provenance without a hunt.
  Corollary: consensus-SUE PEAD is NOT free-data feasible — swing
  DR-0005's FINNHUB_TOKEN has been unprovisioned since 2026-08-30, so
  any consensus-surprise formulation is BLOCKED-ON-DATA and must not
  be filed; the consensus-FREE (EDGAR 8-K Item 2.02 abnormal-return)
  formulation is the only F-03 route that clears the free-data gate.
- 2026-10-05 Grep's `glob=` filter has the SAME directory-wildcard blind
  spot as Glob's pattern (companion to the two entries above):
  `Grep(pattern='"stage"', path="<atlas>/alpha-lab/ideas",
        glob="*/state.json")` returns **No matches found** even though all
  14 files contain the string. A single `*` crossing a directory level
  matches nothing in this harness, in Grep's `glob=` just as in Glob's
  pattern. (Grep's `path=` DOES work, unlike Glob's — that part of the
  2026-10-04 entry still holds.) So the capacity check cannot be done as
  one Grep: use the absolute `**` Glob to enumerate the A-#### dirs, then
  Read each `state.json` individually (14 parallel Reads is cheap). A
  silent zero here is the false-zero failure mode again, one layer down.
- 2026-10-05 three of the eight open families have NEVER had an idea
  filed: **F-04 cross-asset-lead-lag, F-06 liquidity-mean-reversion,
  F-07 momentum-decay-structure**. All 14 ideas to date sit in five
  families (F-01 x2, F-02 x1, F-03 x2, F-05 x4, F-08 x2, plus the two
  pre-family microstructure kills and A-0001). When mining comes up dry,
  the virgin families are generative ground that costs no lesson check
  beyond the family's own stated caveat — and F-06's caveat is concrete
  and discharge-able (differentiate from the RSI-2-class quant-desk
  rejects R-0003/R-0007/R-0011; R-0011 is `rsi2_meanrev` on SPY/QQQ/IWM,
  REJECT on worst-fold Sharpe -0.0919, at `quant/reports/R-0011/`).
- 2026-10-05 F-08 NAV-source, the working endpoints (supplements the
  scope entry below): A-0013 cycle-1 PROVED the keyless SSGA 6c-11 files
  fetch for SPY/XLF/FLRN —
  `https://www.ssga.com/library-content/products/fund-data/etfs/us/navhist-us-en-<ticker>.xlsx`
  and `.../pdhist-us-en-<ticker>.xlsx` (legal basis: Rule 6c-11(c)(1)).
  Cite these rather than inventing a NAV provider; the provenance is in
  `ideas/A-0013/research/probe_data.json`.
- 2026-10-17 free capacity ≠ license to generate when INBOX is non-empty:
  a slot opening up in the pipeline (active ideas < max_active_ideas) does
  NOT mean the scout should immediately generate and file a new idea. If the
  INBOX queue (ideas with stage `inbox`, awaiting triage) already holds one or
  more cards, the pipeline is effectively full from the triage team's
  perspective — filing another card just deepens the unreviewed backlog and
  wastes a job slot. Confirmed by 5 consecutive F-04 runs that each filed a
  new idea while prior INBOX cards sat unreviewed. Rule: count `stage ==
  "inbox"` separately and add it to the active non-terminal count before
  deciding to generate. If `inbox_count + active_non_terminal >=
  max_active_ideas`, treat the pipeline as full and exit without filing.
- 2026-10-19 the inbox count is UNCHECKED INBOX.md LINES, not `stage: "inbox"`
  (corrects the recipe in the 2026-10-17 "free capacity != license to generate"
  entry above; the RULE in that entry is right and was vindicated this run, only
  its measurement instruction was wrong). No idea has ever carried
  `stage == "inbox"` -- the stages seen on disk are submitted/triaged/carded/
  backtesting/verdict -- so `count(stage == "inbox")` returns 0 forever and the
  guard it was supposed to arm never fires. The real queue of
  offered-but-unfiled candidates is the unchecked checkboxes in
  `alpha-lab/evaluation/INBOX.md`: a scout that hits the capacity ceiling
  QUEUES its candidate as a `- [ ]` line with no A-#### id, no state.json, no
  card.md and no trials row -- so it is invisible to every dedup surface except
  that one grep, and invisible to a stage-based capacity count entirely. Measure
  it with
  `Grep(pattern="^- \\[ \\]", path="<atlas>/alpha-lab/evaluation/INBOX.md",
        output_mode="content")`
  and add that to the non-terminal state.json count BEFORE the generate branch.
  Measured 2026-10-19: 3 non-terminal ideas + **5 unchecked INBOX lines** = 8
  against `max_active_ideas: 4`. Those five lines are FIVE CONSECUTIVE FILE-mode
  scout dispatches (jobs 0236ae66, bf1fd342, 9e5ad071, c04795c2, 9d52f12e, all
  2026-10-17) that each queued at capacity and filed nothing -- and all five are
  family F-04, because F-04 is the last virgin family and five runs in a row
  independently reached for it. Read the queue before generating or you will
  write a sixth.
- 2026-10-19 when a slot frees up and the INBOX queue is non-empty, the
  slot belongs to the QUEUE, not to generation. Draining is not production: a
  queued `- [ ]` line is exactly the offered-but-unfiled E-0006 class that
  PROTOCOL section 2b lists as a scout source and that the skill body tells you
  to prefer over invention. So the 2026-10-17 "treat the pipeline as full and
  exit" rule means *generate* nothing -- it does NOT mean dispatch nothing,
  because a drain takes the backlog 5 -> 4 where a new file takes it 5 -> 6.
  Dispatch FIFO (oldest unchecked line), cite the INBOX line as the BINDING
  pre-registration text rather than re-quoting it lossily into the payload
  (`jobs.payload` is not append-only evidence -- the [E-0110] dark-job class),
  and carry the sibling lines' conditioners as mandatory scored comparators
  where a queue line itself recommends it: job 9e5ad071's line records that one
  GLD/GDX panel scored with both its own and job 0236ae66's conditioner would
  resolve TWO queue entries in ONE capacity slot. Never auto-drain two lines in
  a session -- the queue lines are mutually informative and must be sequenced,
  so a NO-GO on one is evidence about the next.
- 2026-10-19 the ceiling's cause has been OWNER-PARKED SLOTS, not scout
  over-production, for ~3 weeks, and saying so is the run's highest-value
  output. A-0011 (backtesting 1/6, undischarged DECISION-REQUEST [E-0087],
  2026-10-01) and A-0014 (backtesting 0/6, undischarged [E-0118], 2026-10-06)
  have occupied 2 of 4 slots for 18 and 13 days, so effective working width is
  2 and the generator queues behind decisions only the owner can make. All five
  queued lines flagged this as an "OWNER-VISIBLE FINDING" and it is still
  unanswered -- which means a scout summary that reports only
  candidates/filed/dropped is burying the one thing that would unblock the
  flywheel. Escalate the parked DECISION-REQUESTs by id in the Telegram
  summary, every run, until they clear.
- 2026-10-04 F-08 NAV-source scope: family F-08
  (etf-primary-market-frictions) requires that every candidate names the
  *exact free NAV source* in the idea_text, or triage blocks the card as
  BLOCKED-ON-DATA regardless of mechanism quality. Do not file an F-08
  candidate that mentions NAV without specifying the free source (e.g.,
  the issuer's public daily NAV CSV page, ETF.com download, or an Alpaca
  ETF spread proxy stated explicitly). The quality gate — mechanism +
  loser + free-data source — is satisfied only when the NAV provider is
  named, not implied.
- 2026-10-18 virgin-families update (supersedes the 2026-10-05 "three of
  the eight open families" entry): **F-04 cross-asset-lead-lag is now the
  ONLY remaining virgin family.** The other two have been entered and
  their first-round ideas have all reached verdicts:
  · F-06 (liquidity-mean-reversion) — entered 2026-10-07 by three ideas
    filed in one scout run: A-0016 (nav_discount_concession, NO-GO
    [E-0133/E-0134]), A-0017 (clv_reversal, NO-GO [E-0127]), A-0018
    (nonews_liquidity_reversal, NO-GO [E-0148]). The F-06 RSI-2
    caveat is now TIGHTENED by lesson [A-0018]: "differentiation from
    R-0003/R-0007/R-0011 must be measured in PAYOFF at card stage, not
    argued from a Jaccard overlap" — RSI-2 beat all three F-06 candidates
    in gross payoff. The "exclude scheduled-disclosure days" escape hatch
    is closed for the family (lesson [A-0018] §a). Future F-06 ideas
    must name a concrete mechanism by which a liquidity concession is
    paid and show at card stage that the proposed conditioner outperforms
    RSI-2 in gross payoff; a mechanism-difference argument alone is no
    longer sufficient.
  · F-07 (momentum-decay-structure) — entered 2026-10-17 by A-0019
    (momentum_decay_structure, intermediate-horizon "echo" momentum in
    nine sector-sleeve SPDR, NO-GO [E-0163]). Lesson [A-0019]: the
    family's premise survives (all signs were in the predicted direction)
    but the nine-sleeve monthly panel is dead on POWER before filing — a
    wider cross-section or longer hold is required. A-0020 (same family
    string, binding ruling [E-0159] item 1(i)) was in triage as of
    2026-10-18. Any new F-07 idea must prove its SE-against-DSR-bar
    arithmetic is satisfiable on a panel that is wider than nine names.
  · F-04 — no idea has ever been filed; the original caveat ("the other
    side is the slower venue's liquidity takers; sub-daily is
    lesson-pruned L-0002/L-0003") is still the only lesson gate.
  Pipeline as of 2026-10-18: 20 ideas (A-0001–A-0020) spanning seven
  FAMILIES.md families (F-01, F-02, F-03, F-05, F-06, F-07, F-08); only
  F-04 is virgin.
