# atlas-firm-rollup — gotchas

- 2026-09-01 (build): firm venvs in ~/Documents lose editable installs to
  the UF_HIDDEN/.pth daemon — ALWAYS run
  `bash scripts/install-venv-sitecustomize.sh` after creating the venv;
  symptom is `ModuleNotFoundError: No module named 'firm'` under pytest.
- 2026-09-01 (build): `firm check` reads limits from firm/config/limits.yaml
  in YOUR clone — a rebase that touched limits is owner action, not yours;
  never edit it to make a breach go away.
- 2026-09-01 (build): swing/value books legitimately show zero positions
  (no open lots/theses) — book_coverage may warn; report it as the designed
  signal, not an error to fix.
