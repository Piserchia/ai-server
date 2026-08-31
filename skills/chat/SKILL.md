---
name: chat
description: One-shot conversation. No tools, no project context, just a direct response.
model: claude-sonnet-4-6
effort: low
permission_mode: plan
required_tools: []
max_turns: 3
tags: [conversational]
---

# Chat

## When to use
Triggered by `/chat <message>` or when the user sends a message that is clearly
conversational rather than a task ("what do you think about X", "how are you", etc).

## Procedure
1. Respond directly to the user's message.
2. Keep it short and natural — 1-5 sentences typical, more only if the question warrants.
3. Do not invoke tools. Do not read the context system. Do not touch files.
4. Do not do write-back; there's nothing to write back.
5. If the user's message would be better served by a task (they asked you to actually
   *do* something, not just chat about it), say so in one sentence and suggest they
   use `/task <their request>`.

## Gotchas
- Don't confuse "chat about X" with "research X" — if they want a factual answer with
  sources, redirect to research-report rather than improvising.
- `permission_mode: plan` (2026-08-20): under the previous `default` mode the model
  would still attempt Bash despite `required_tools: []`, each call hit the interactive
  approval gate (headless sessions can't answer), and `max_turns: 3` was exhausted →
  `error_max_turns`. See incident job 267dd425. Plan mode blocks tool USE at the SDK
  layer, forcing the text-only response this skill actually wants. If the router sends
  a diagnostic/action question to chat (e.g. "Is the server down? Can you fix"), plan
  mode will let the model gracefully say "use /task ..." per step 5 rather than looping
  on blocked tools.
