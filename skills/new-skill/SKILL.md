---
name: new-skill
description: Author a new skill (SKILL.md + support files) from a natural-language description; lands autonomously on agent code-review LGTM + owner notification (high-privilege skills and protected paths always need owner approval)
model: claude-opus-4-7
effort: high
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 30
post_review:
  trigger: always
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: max
context_files: [".context/SKILLS_REGISTRY.md", "skills/README.md"]
tags: [meta, skill-creation]
isolation: workspace
subagents: [code-review]
---

# New Skill

You are authoring a brand-new skill for the assistant server. Your output is a
complete `skills/<slug>/SKILL.md` (plus any support files), a router rule if
the skill is user-triggerable, and an updated SKILLS_REGISTRY.

**Landing lane (owner decision 2026-07-31, INV-4):** your work merges to main
autonomously when (a) the gates below are green, (b) your in-session
`code-review` subagent returns LGTM on the diff, and (c) the owner is
**notified** in your final summary. Human pre-merge approval is not required —
EXCEPT for the two ceilings below, which always require a PR + explicit owner
approval:

1. **High-privilege skill ceiling**: the new skill's frontmatter declares
   `privilege_class: prod-operator` or `privilege_class: break-glass`, or
   `isolation: host`. Adding a high-privilege agent to the roster expands what
   the system can do to its host — that is ALWAYS an owner decision, never an
   autonomous one.
2. **Protected paths** (same list as `server-patch`): `.context/PROTOCOL.md`;
   auth config (`TELEGRAM_ALLOWED_CHAT_IDS`, `.env`/secrets, chat-ID/web-auth
   checks); deletion of any project or skill directory; `src/runner/guards.py`;
   `scripts/lint_docs.py`; `MISSION.md`; the safety-principle section of
   `.context/org/ORG.md`; and the lane's executor skills themselves
   (`skills/server-patch/SKILL.md`, `skills/server-deploy/SKILL.md`,
   `skills/new-skill/SKILL.md`). The system must not be able to relax its own
   restraints autonomously — for these, LGTM is necessary but never sufficient.

The runner's independent post-session review still runs after you finish
(INV-13, `post_review` frontmatter — never weaken it).

**Read `skills/TEMPLATE.md` first** — it defines the required sections
(Inputs, Procedure, Quality gate, Gotchas) and frontmatter conventions.

## When to use

Triggered when the user says "new skill: ..." or "add a skill ...". The job
description contains a natural-language explanation of what the new skill
should do.

## Inputs

Extract from the job description (and optionally `payload`):
- **what it does** (required): the natural-language description of the skill
- **scheduled_cron** (optional): a cron expression if the skill runs on a schedule
- **model_override** (optional): override the default model choice
- **effort_override** (optional): override the default effort level

## Procedure

1. **Analyze the description.** Determine:
   - **Skill slug**: kebab-case, lowercase, no special characters. Internal
     skills (spawned by runner, never user-triggered) get a leading underscore
     (`_name`).
   - **Trigger type**: ad-hoc (user invokes via router), scheduled (cron),
     event-triggered, or internal.
   - **Required tools**: what Claude tools the skill needs (Read, Write, Edit,
     Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion, etc.).
   - **Model / effort**: choose based on complexity. Simple read-only skills
     can use Sonnet 4.6 / low. Skills that write code or make complex
     decisions should use Opus 4.7 / high.
   - **Escalation rules**: if a cheaper model could handle most cases but
     should escalate on failure, declare `escalation.on_failure`.
   - **Permission mode**: `default` for read-only, `acceptEdits` for file
     mutations, `plan` for review-only analysis.
   - **Privilege**: if the skill needs `prod-operator`/`break-glass` privilege
     or `isolation: host`, note NOW that this run ends in the PR lane (ceiling
     1 above) — author it anyway, but plan for owner approval.

2. **Check for overlap.** Read `.context/SKILLS_REGISTRY.md`. If an existing
   skill already covers this use case:
   - Explain the overlap to the user.
   - Suggest extending the existing skill rather than creating a duplicate.
   - Only proceed with creation if the use case is genuinely new or the
     existing skill's scope is clearly different.

3. **Read structural examples.** Read at least 2 existing SKILL.md files to
   absorb the structural pattern:
   - `skills/research-report/SKILL.md` (thorough skill with escalation and
     write-back)
   - `skills/chat/SKILL.md` (minimal skill, no tools)
   - `skills/code-review/SKILL.md` (plan-mode, read-only skill)
   - `skills/app-patch/SKILL.md` if it exists (coding skill)

4. **Draft SKILL.md.** Create `skills/<slug>/SKILL.md` with:

   **YAML frontmatter** (all fields that apply):
   ```yaml
   name: <slug>
   description: <one-line description>
   model: <model>
   effort: <low|medium|high>
   permission_mode: <default|acceptEdits|plan>
   required_tools: [<tool list>]
   max_turns: <number>
   # Include if the skill should be code-reviewed after every run:
   post_review:
     trigger: always
   # Include if a cheaper model should try first:
   escalation:
     on_failure:
       model: <model>
       effort: <effort>
   tags: [<tag list>]
   ```

   **Markdown body** (structured as instructions to Claude, not documentation):
   - `# <Skill Name>` -- opening paragraph explaining what this skill does
   - `## When to use` -- trigger conditions
   - `## Inputs` -- what data the skill receives from the job description/payload
   - `## Procedure` -- numbered steps, imperative voice, specific commands
   - `## Quality gate` -- checklist the skill must self-verify before finishing
   - `## Gotchas` -- living section; append when you learn something reusable
   - `## Files this skill updates` -- for write-back enforcement

   Write the body as a system prompt: imperative instructions to Claude, not
   documentation for a human reader. Be specific about file paths, commands,
   and formats. Include code blocks for any shell commands or file templates
   the skill should use.

5. **Create support files.** If the skill needs templates, example data, or
   configuration files, create them under `skills/<slug>/`. Common patterns:
   - `skills/<slug>/templates/` for output templates
   - `skills/<slug>/examples/` for few-shot examples
   - `skills/<slug>/data/` for static reference data

6. **Add router rule** (if applicable). If the skill is ad-hoc
   (user-triggerable), append a routing rule to `src/runner/router.py`:
   - Use a narrow regex that will not false-positive on other descriptions.
   - Place it in the correct position (first match wins):
     - Before research rules if it might conflict with "summary/report" keywords.
     - After coding rules if it's a coding-adjacent skill.
   - Add a comment above the rule explaining what it matches.
   - Test the rule:
     ```bash
     python3 -c "from src.runner.router import route; print(route('<test description>'))"
     ```
   - If you modify `router.py`, you MUST also update
     `.context/modules/runner/CHANGELOG.md` (the pre-commit hook enforces this).

7. **Update SKILLS_REGISTRY.** Append a row to the "Installed" table in
   `.context/SKILLS_REGISTRY.md`:
   ```
   | `<slug>` | <Model> / <effort> | <one-line purpose> | <phase> |
   ```
   If the skill was listed under "Planned", remove it from that table.

8. **Insert schedule** (if applicable). If the description implies a recurring
   schedule (or `scheduled_cron` is provided in the payload), insert a row:
   ```sql
   INSERT INTO schedules (id, skill_name, cron_expression, description, enabled, created_at)
   VALUES (gen_random_uuid(), '<slug>', '<cron>', '<description>', true, NOW());
   ```
   Run via: `psql "$DATABASE_URL" -c "<sql>"`.

9. **Gate.** Run the quality-gate checklist below, plus:
   ```bash
   python scripts/lint_docs.py        # registries/org/body checks must PASS
   # If you touched any src/ file (e.g. router.py):
   pipenv run pytest tests/ -v        # full gate, must be green
   ```

10. **Ceiling + protected-path check.** Commit on a branch first:
    ```bash
    git checkout -b new-skill/<slug>
    git add -A && git commit -m "Add <slug> skill"
    git diff main --name-only
    ```
    - The new skill declares `prod-operator`/`break-glass` privilege or
      `isolation: host` → **PR lane** (step 12), always.
    - Any changed/deleted path is on the protected list above → **PR lane**.
    - Otherwise → step 11.

11. **In-session review → autonomous landing.** Delegate the branch-vs-main
    diff (`git diff main`) to your `code-review` subagent via the Task tool,
    with a short statement of what the skill is for.
    - **LGTM** →
      ```bash
      git checkout main && git pull --ff-only
      git merge --no-ff new-skill/<slug>
      python scripts/lint_docs.py            # re-check on merged main
      git push origin main
      ```
      Rejected push → `git pull --rebase origin main`, re-run the gate,
      retry ONCE; still failing → PR lane. The canonical checkout
      fast-forwards automatically after your push.
    - **CHANGES / BLOCKER** → address what you can, re-run steps 9–11 ONCE;
      still not LGTM → PR lane.
    - **Review could not run** → PR lane. Fail closed: an unreviewed skill
      never lands itself.

12. **PR lane (owner approval).** Push the branch and open a PR; never merge
    it yourself; stop with status awaiting the owner:
    ```bash
    git push -u origin new-skill/<slug>
    gh pr create --title "Add <slug> skill" \
      --body "<what it does; why owner approval is needed (ceiling/protected
      path/review verdict); review findings; gate output>"
    ```

13. **Summary — MANDATORY owner notification.** Your final text message must
    report:
    - What was created (skill slug, files) and how to trigger it (router
      pattern, cron, or internal-only)
    - Landing lane taken: autonomous (include `git diff --stat`, the
      subagent's LGTM, gates run, pushed sha) or PR (URL + why)
    - Any router rule added or modified
    - Any open questions or limitations

## Quality gate

Run these checks before your final text message:

- [ ] SKILL.md has valid YAML frontmatter:
  ```bash
  python3 -c "import yaml; yaml.safe_load(open('skills/<slug>/SKILL.md').read().split('---')[1])"
  ```
- [ ] `python scripts/lint_docs.py` passes (registry row, body sections,
  `## Gotchas`, division charter claim, isolation values).
- [ ] Router rule (if added) uses a narrow regex that does not match unrelated
  descriptions. Test with 3 positive and 3 negative examples.
- [ ] No duplicate or overlapping skill in SKILLS_REGISTRY.
- [ ] SKILLS_REGISTRY updated (moved from Planned to Installed, or new row added).
- [ ] The new skill is claimed by exactly one division CHARTER.md roster
  (`.context/org/divisions/<div>/CHARTER.md`) — lint enforces this.
- [ ] Internal skills use a leading underscore in the directory name.
- [ ] The skill body is written as instructions to Claude (imperative), not as
  documentation for a human.
- [ ] If `router.py` was modified, `.context/modules/runner/CHANGELOG.md` was
  also updated and the full pytest gate is green.
- [ ] Ceiling check done: privilege class / isolation of the NEW skill checked,
  protected-path scan of the diff done, lane recorded for the summary.

## Gotchas

- **Leading underscore convention**: internal skills (spawned by the runner,
  not user-triggerable) use `_<name>` as the directory name. User-triggerable
  skills use `<name>` without underscore.
- **Skill name resolution**: `kind.replace("_", "-")` converts underscores to
  dashes in skill name resolution. Leading underscores are preserved. So
  `new_skill` becomes `new-skill` but `_writeback` stays `_writeback`.
- **Router rule order**: first match wins. Order matters. Place new rules
  carefully to avoid shadowing or being shadowed by existing rules.
- **Pre-commit hook**: commits touching `src/` are blocked unless you also
  update the relevant module's CHANGELOG. If you modify `router.py`, update
  `.context/modules/runner/CHANGELOG.md`.
- **Post-review opt-in**: code-touching skills should include
  `post_review: { trigger: always }` in frontmatter so the code-review
  sub-agent runs after every session.
- **Write-back enforcement**: if the skill creates or modifies files in
  `projects/` or `src/`, include CHANGELOG update instructions in the
  Procedure. Otherwise the `_writeback` skill will be spawned automatically
  as a follow-up.
- **The high-privilege ceiling is about the AUTHORED skill, not this one**:
  you (new-skill) are a guarded writer; the skill you are creating is what's
  checked for `prod-operator`/`break-glass`/`isolation: host`. Don't talk
  yourself into "it's just frontmatter" — privilege frontmatter IS the
  authority grant, which is why it's owner-approval-only.
- **You work in a workspace clone** (`isolation: workspace`): your cwd is a
  per-job clone whose `origin` is the real remote; guard hooks contain your
  writes to the clone. The autonomous landing pushes `origin main` from
  there; the canonical is ff-synced after. If a generic runner directive says
  "never push to main from here", the 2026-07-31 lane supersedes it ONLY when
  the full lane (green gates + LGTM + no ceiling/protected path) holds.
- **A new skill without a charter claim fails lint** — add the roster row in
  the owning division's CHARTER.md in the same diff (which division proposed
  it tells you where it belongs).

## Files this skill updates

- `skills/<slug>/SKILL.md` (the new skill definition)
- `skills/<slug>/` (any support files: templates, examples, data)
- `src/runner/router.py` (only if adding a router rule for a user-triggerable skill)
- `.context/SKILLS_REGISTRY.md` (append to Installed table)
- `.context/org/divisions/<div>/CHARTER.md` (roster row for the new skill)
- `.context/modules/runner/CHANGELOG.md` (only if `router.py` was modified)
