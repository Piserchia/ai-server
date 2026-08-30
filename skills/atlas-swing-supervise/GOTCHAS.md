# atlas-swing-supervise GOTCHAS

- The executor exits 0 with a JSON report for HANDLED outcomes including
  halts and off_window — only crashes fail the job.
- `off_window` at ~09:40 ET means the dual-row DST cron fired on its
  off-season row: the sibling row covers today. Not a failure; say so in
  one line and stop.
- Sandbox tokens: TRADIER_SANDBOX_TOKEN / TRADIER_SANDBOX_ACCOUNT_ID in the
  clone's .env (owner-provisioned). Absent → report the provisioning gap
  (P0-A); never create credentials.
- The venv editable-install gotcha (UF_HIDDEN .pth) makes imports die with
  "No module named tradingcore" — run
  `bash scripts/install-venv-sitecustomize.sh` from the atlas root, do not
  debug pip.
- Schedule rows atlas-swing-supervise-edt/-est MUST carry
  '{"project_slug":"atlas"}' (else workspace clones the ai-server repo).
