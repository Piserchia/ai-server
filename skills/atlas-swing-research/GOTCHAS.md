# atlas-swing-research GOTCHAS

- trials.jsonl line goes in BEFORE the verdict (DSR denominator) — a
  forgotten line invalidates the promotion math forever after.
- The adoption gate greps setups files for a `card:` id present in
  LEDGER.md — seal the card first, then write the config.
- setups_v1.yaml is hash-sealed (test_adoption_gate) — NEVER edit it;
  supersede with setups_v2.yaml.
- 30-min SDK ceiling killed momo research runs historically — payload
  carries 3600s; still run the 45-min close-out timer.
