---
name: new-skill
description: Author a new skill (SKILL.md + support files) from a natural-language description
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
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
---

# New Skill

You are authoring a brand-new skill for the assistant server. Your output is a
complete `skills/<slug>/SKILL.md` (plus any support files), a router rule if
the skill is user-triggerable, and an updated SKILLS_REGISTRY. The code-review
sub-agent will run automatically after you finish.

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

9. **Commit.** Stage all new and modified files and commit to the ai-server
   repo. Do NOT push -- the code-review sub-agent runs after this session.
   If it returns LGTM, the runner handles the merge.
   ```bash
   git add skills/<slug>/ .context/SKILLS_REGISTRY.md
   # Include router.py and runner CHANGELOG only if you modified them:
   # git add src/runner/router.py .context/modules/runner/CHANGELOG.md
   git commit -m "Add <slug> skill (Phase <N>)"
   ```

10. **Summary.** Your final text message must report:
    - What was created (skill slug, files)
    - How to trigger it (router pattern, cron, or internal-only)
    - Any router rule added or modified
    - Any open questions or limitations

## Quality gate

Run these checks before your final text message:

- [ ] SKILL.md has valid YAML frontmatter:
  ```bash
  python3 -c "import yaml; yaml.safe_load(open('skills/<slug>/SKILL.md').read().split('---')[1])"
  ```
- [ ] Router rule (if added) uses a narrow regex that does not match unrelated
  descriptions. Test with 3 positive and 3 negative examples.
- [ ] No duplicate or overlapping skill in SKILLS_REGISTRY.
- [ ] SKILLS_REGISTRY updated (moved from Planned to Installed, or new row added).
- [ ] Internal skills use a leading underscore in the directory name.
- [ ] The skill body is written as instructions to Claude (imperative), not as
  documentation for a human.
- [ ] If `router.py` was modified, `.context/modules/runner/CHANGELOG.md` was
  also updated.

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

## Files this skill updates

- `skills/<slug>/SKILL.md` (the new skill definition)
- `skills/<slug>/` (any support files: templates, examples, data)
- `src/runner/router.py` (only if adding a router rule for a user-triggerable skill)
- `.context/SKILLS_REGISTRY.md` (append to Installed table)
- `.context/modules/runner/CHANGELOG.md` (only if `router.py` was modified)
