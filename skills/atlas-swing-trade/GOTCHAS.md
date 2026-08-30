# atlas-swing-trade GOTCHAS

- The screen file must be from TODAY — --submit refuses stale screens.
  Always regenerate; never reuse yesterday's /tmp files.
- S2 suppressed with calendar_status ABSENT means FINNHUB_TOKEN is not
  provisioned (owner P0). Report the gap once, don't work around it.
- IV gates in warm-up run on the tagged proxy (ivr_proxy in gates) — S4/S5
  candidates carry it; mention it when entering one.
- Kernel rejections are ledgered as decisions — they are honest evidence,
  not embarrassments to retry away.
- Dual-row DST crons: an off_window result means the sibling row owns today.
- Payload must carry '{"project_slug":"atlas"}'.
