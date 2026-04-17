---
name: chat
description: One-shot conversation. No tools, no project context, just a direct response.
model: claude-sonnet-4-6
effort: low
permission_mode: default
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
