# Agent Protocol

This protocol is mandatory. Every agent session that modifies code must follow these steps.

---

## Phase 1: Orient (before any code changes)

### 1.1 Read system context
```bash
cat .context/SYSTEM.md
```
Understand the module graph, conventions, and active workstreams.

### 1.2 Identify affected modules
Based on the task, determine which modules will be touched. For each:
```bash
cat .context/modules/<name>/CONTEXT.md
cat .context/modules/<name>/CHANGELOG.md
```

### 1.3 Read relevant skills
```bash
ls .context/modules/<name>/skills/
cat .context/modules/<name>/skills/DEBUG.md    # if debugging
cat .context/modules/<name>/skills/PATTERNS.md # if adding features
cat .context/modules/<name>/skills/GOTCHAS.md  # always read this if it exists
```

### 1.4 Check cross-module impact
Consult the module graph in SYSTEM.md. If your target module is depended on by others, read those dependents' CONTEXT.md files too — your change may break them.

---

## Phase 2: Execute (make changes)

Work normally. Fix bugs, add features, refactor — whatever the task requires.

**While working, keep a mental (or scratch) log of:**
- What files you modified and why
- Any surprising behavior you encountered
- Any assumptions that turned out to be wrong
- Patterns you discovered that would help future agents
- Upstream/downstream effects of your changes

---

## Phase 3: Write-back (after changes, before finishing)

This is the critical phase. You are building the knowledge base for every future agent.

### 3.1 Update module CHANGELOG.md

Append an entry to `.context/modules/<name>/CHANGELOG.md` for every module you touched:

```markdown
## YYYY-MM-DD — <short summary>

**Agent task**: <what you were asked to do>
**Files changed**:
- `path/to/file.py` — <what changed and why>

**Why**: <the reasoning behind the approach taken>

**Side effects**: <any impact on other modules, breaking changes, or behavioral shifts>

**Gotchas discovered**: <anything surprising that future agents should know>
```

### 3.2 Update module CONTEXT.md (if needed)

Update `.context/modules/<name>/CONTEXT.md` if any of these changed:
- The module's public API or interface
- Its dependencies (new imports, removed dependencies)
- Its configuration or environment requirements
- Its core behavioral contract (what callers expect from it)

Do NOT update CONTEXT.md for minor internal refactors that don't change the module's external behavior.

### 3.3 Evolve module skills (if you learned something)

This is where the system gets smarter over time. Update or create skill files when:

**DEBUG.md** — You found and fixed a bug:
- Document the symptom, root cause, and fix
- Add diagnostic commands or checks that would have found it faster
- Note what the error messages actually mean vs what they seem to mean

**PATTERNS.md** — You discovered or used a non-obvious pattern:
- How to correctly extend this module
- The "right way" to add a new endpoint / model / handler / etc.
- Integration patterns with other modules

**GOTCHAS.md** — You hit a trap:
- Things that look like they should work but don't
- Implicit dependencies or ordering requirements
- Environment-specific behavior
- Race conditions, timing issues, state assumptions

**Skill file format:**
```markdown
# <Skill Name>

## When to use this
<One sentence: what situation triggers this skill>

## The pattern / The fix / The trap
<Concise, actionable content. Code examples where helpful.>

## Why this works (or why the naive approach fails)
<Brief explanation so the agent understands, not just follows instructions>
```

### 3.4 Update SYSTEM.md (if needed)

Update `.context/SYSTEM.md` if:
- You added or removed a module
- You changed the dependency graph between modules
- You changed a repo-wide convention
- You discovered or resolved technical debt

### 3.5 Propagate cross-module context

If your change affects another module's contract (changed an API signature, altered return types, modified shared state), go to that module's CONTEXT.md and add a note:

```markdown
> ⚠️ **Upstream change (YYYY-MM-DD)**: `<source-module>` changed `<what>`. 
> See `<source-module>` changelog entry for details. This module may need updates.
```

---

## Bootstrapping a New Module

When you encounter a module with no `.context/modules/<name>/` directory:

### Step 1: Create the context directory
```bash
mkdir -p .context/modules/<name>/skills
```

### Step 2: Analyze the module
Read the actual source code. Understand:
- What this module does (purpose, scope)
- Its public interface (what other modules call)
- Its dependencies (what it imports/calls)
- Its configuration needs
- Its test coverage and how to run tests

### Step 3: Write CONTEXT.md
```bash
cat > .context/modules/<name>/CONTEXT.md << 'EOF'
# <Module Name>

## Purpose
<What this module does in 2-3 sentences>

## Public interface
<Key functions/classes/endpoints that other modules use>

## Dependencies
<What this module depends on — both internal modules and external packages>

## Configuration
<Environment variables, config files, or setup this module needs>

## Testing
<How to run tests for this module. Key test files.>

## Internal structure
<Brief tour of the files and their roles>
EOF
```

### Step 4: Initialize CHANGELOG.md
```bash
cat > .context/modules/<name>/CHANGELOG.md << 'EOF'
# Changelog: <Module Name>

<!-- Reverse chronological. Newest entries at the top. -->

## YYYY-MM-DD — Initial context bootstrapped

**Agent task**: Module discovery and documentation
**Files changed**: None (context creation only)
**Why**: First agent to work with this module. Context bootstrapped from source analysis.
EOF
```

### Step 5: Seed skills from what you observe
If you notice debug patterns, gotchas, or non-obvious patterns during your analysis, create the relevant skill files immediately. Don't wait until something goes wrong.

### Step 6: Register in SYSTEM.md
Add the module to the module graph table in `.context/SYSTEM.md`.

---

## Quality Standards

### CHANGELOG entries must include:
- ✅ What changed (files and specific modifications)
- ✅ Why it changed (the reasoning, not just "fixed bug")
- ✅ Side effects (what else might be affected)
- ✅ Gotchas (things that surprised you)

### CONTEXT.md must stay:
- ✅ Accurate (update it whenever the module's interface changes)
- ✅ Concise (this is a reference, not a novel)
- ✅ Actionable (an agent should be able to work with this module after reading it)

### Skills must be:
- ✅ Specific (one skill per problem/pattern, not a grab-bag)
- ✅ Actionable (include commands, code examples, exact steps)
- ✅ Explained (say why, not just what)

---

## Anti-patterns

- ❌ **Skipping the write-back** because "the change was small" — small changes cause the worst bugs when undocumented
- ❌ **Writing vague changelogs** like "fixed stuff" — be specific or don't bother
- ❌ **Duplicating info** between CONTEXT.md and skills — CONTEXT.md is "what is this", skills are "how to work with this"
- ❌ **Updating CONTEXT.md for internal changes** — only update when the external contract changes
- ❌ **Ignoring cross-module impact** — if you changed module A's API, module B's context needs a warning
