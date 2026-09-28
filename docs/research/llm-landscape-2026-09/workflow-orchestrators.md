# Self-hosted workflow orchestrators as the run/visibility layer (n8n, Temporal, Prefect, Windmill, Trigger.dev, Hatchet, LangGraph Platform, Inngest, Dagster, Airflow) — research (as of 2026-09-24)

Scope: can one of these replace or wrap the bespoke Python job runner (Postgres `jobs` table + Redis queue + croniter scheduler + launchd, ~11k lines) on a 16 GB Mac Mini M4 with ~6 GB headroom, for ~30–60 agent jobs/day at 2 concurrent, where each job is a 5–90 min Claude Agent SDK subprocess that streams events? Research method: primary vendor docs/pricing/GitHub API fetched 2026-09-24; community sentiment from Hacker News via the Algolia API. The session's web-search budget was exhausted before this task started, so every fact below comes from a directly fetched URL (listed in §9); Reddit could not be fetched. Anything not directly confirmed is marked "(unverified)".

## 1. Snapshot

**The category.** "Durable run/visibility layers": a server that stores a run history, evaluates cron schedules, accepts HTTP/webhook triggers, dispatches work to workers with concurrency/priority rules, retries and cancels, and shows all of it in a UI. Three sub-families matter here: (a) **durable-execution engines** that replay code (Temporal, Hatchet, Inngest, Trigger.dev, LangGraph Platform); (b) **Python data-orchestrators** (Prefect, Dagster, Airflow); (c) **script/low-code platforms** with a job queue and UI (Windmill, n8n).

**Candidates and versions (GitHub `releases/latest`, fetched 2026-09-24):**

| Product | Latest tag | License (GitHub API) | Stars | Core language / Python posture |
|---|---|---|---|---|
| n8n | `n8n@2.40.6` (2026-09-24) [12] | Sustainable Use License 1.0 (fair-code; `.ee.` files need Enterprise) [1] | 205,873 [12] | Node.js; Python via the Code node's native Python task runner (stable in 2.0; Pyodide dropped; self-hosted imports work only for packages baked into the `n8nio/runners` image; Cloud allows no imports) or Execute Command [112] |
| Temporal (server) | `v1.32.0` (2026-09-11); Python SDK `1.33.0` (2026-09-15) [13][14] | MIT [13] | 23,277 [13] | Go server; first-class Python SDK |
| Prefect | `3.8.6` (2026-09-14) [40] | Apache-2.0 [40] | 23,920 [40] | Pure Python server + SDK |
| Windmill | `v1.817.0` (2026-09-22) [51] | AGPL-3.0 (GitHub shows NOASSERTION; pricing page says AGPL) [41][51] | 18,028 [51] | Rust server; Python scripts are a first-class runtime |
| Trigger.dev | `v4.6.4` (2026-09-22) [57] | Apache-2.0 [57] | 16,395 [57] | TypeScript; Python only via `@trigger.dev/python` extension |
| Hatchet | engine `v0.107.2` (2026-09-18); Python SDK `py/1.41.1` (2026-09-24) [74] | MIT [74] | 7,997 [74] | Go engine; Python/TS/Go/Ruby SDKs |
| LangGraph (OSS) / LangSmith Deployment | `langgraph` 1.2.12 / `langgraph-cli` 0.4.32 on PyPI (the repo's `releases/latest` is a CLI dev pre-tag `cli==0.4.32.dev0`, 2026-09-23) [81][113] | MIT (OSS library); Agent Server needs a LangSmith license key [79][81] | 42,231 [81] | Python-first, but tied to LangGraph graphs |
| Inngest | `v1.45.1` (2026-09-17) [89] | SSPL 1.0 with Apache-2.0 conversion after 3 years [84] | 5,881 [89] | Go single binary; Python SDK (Connect needs ≥0.5.0) [85] |
| Dagster | `1.13.24` (2026-09-21) [95] | Apache-2.0 [95] | 16,199 [95] | Pure Python; asset-oriented |
| Apache Airflow | 3.3.2 (docs "stable") [96] | Apache-2.0 [99] | 46,961 [99] | Pure Python; DAG-oriented |

**Positioning in one paragraph.** For this box the field splits fast. Trigger.dev (webapp 3+ vCPU/6+ GB plus worker 4+ vCPU/8+ GB [53]), Airflow (≥4 GB, Linux-only production [96][97]) and LangSmith Deployment (self-hosting is an Enterprise add-on; the standalone Agent Server still authenticates a license key at startup [76][79]) are disqualified on footprint, platform or licensing. n8n is licence-clean for personal use [1] and has native Telegram + MCP [7][8], but hosts subprocesses awkwardly (Execute Command disabled by default from 2.0 [6]; no execution timeout by default (`EXECUTIONS_TIMEOUT=-1`; `EXECUTIONS_TIMEOUT_MAX` 3,600 s merely caps user-set per-workflow timeouts and is adjustable) [5]; FIFO-only concurrency, disabled by default (`N8N_CONCURRENCY_PRODUCTION_LIMIT=-1`) [4]). Inngest is a neat single binary [82] but its HTTP-invocation model and SSPL licence make it a poorer fit than the Python-native options. The realistic shortlist is **Prefect 3** (pip-only, SQLite or your Postgres, Process work pool, automations in OSS [27][28][34][37]), **Hatchet** (MIT, Postgres-only "lite" container, streaming, priority 1–3, concurrency keys, MCP [59][62][63][66][71]), **Temporal** (strongest durability, single `brew install temporal` dev binary, but a 2 MB payload / 50 MB history ceiling that forbids streaming events through it [16][17][23]), and **Windmill** (best UI/MCP, but concurrency limits are Enterprise-only and OSS job retention is 30 days [43][48]). The cheapest, lowest-risk path is "keep the bespoke runner, add observability", with Prefect or Hatchet as an optional shadow-mode pilot (§7).

## 2. Interfaces & surfaces

| Product | Trigger surfaces | API / SDK / CLI | UI ("watch progress" / "what's scheduled, did it run") | Auth (self-hosted) | Mobile reach |
|---|---|---|---|---|---|
| n8n | Telegram Trigger node (message, callback_query, channel_post, inline_query, polls…; restrict by chat/user IDs) [8]; webhooks; cron | Public REST API (docs at docs.n8n.io/connect/n8n-api.md; available self-hosted and on by default — disable with `N8N_PUBLIC_API_DISABLED=true`; built-in API playground is self-hosted only; on n8n Cloud the API is unavailable during the free trial) [110]; built-in **MCP server** (OAuth or API key; Claude Desktop/Code, Codex, Gemini CLI listed) [7] | Executions list per workflow; per-node data; execution data pruned after 336 h by default [5] | Owner account + API key; SSO/SAML/LDAP paid [3] | Responsive web UI; Telegram is native |
| Temporal | Schedules (`client.create_schedule`, cron/interval/jitter, pause, backfill, overlap policies) [19]; Signals/Updates; no built-in inbound webhook — your HTTP layer starts workflows | Python SDK 1.33.0 [14]; `temporal` CLI (brew, arm64) [17]; gRPC 7233; Web UI 8080 (8233 dev) [16][24] | Workflow list filtered by status/ID/type/time; event history (timeline/compact/JSON); Schedules page with upcoming runs; pending activities with heartbeat details; cancel/signal/reset/terminate from UI [22] | Web UI has **no auth by default**; enable with `TEMPORAL_AUTH_ENABLED=true` plus `TEMPORAL_AUTH_CLIENT_ID/CLIENT_SECRET/PROVIDER_URL/CALLBACK_URL` (OIDC) — documented at docs.temporal.io/self-hosted-guide/security, not the /web-ui page [109]; server "should not be exposed to the open internet" [15] | Web UI only |
| Prefect 3 | Cron/interval/RRule schedules with IANA tz [36]; `POST /api/deployments/{id}/create_flow_run` [39]; automations (event → run/cancel/notify/webhook-out) available self-hosted; inbound **webhooks are Cloud-only** [34][35] | `prefect` CLI, Python SDK, REST API; `prefect deployment run flow/deploy` [33] | Flow-run list, per-run logs (log_prints), deployment schedule view, automations, concurrency pages [27][31] | Basic auth via `PREFECT_SERVER_API_AUTH_STRING="admin:pass"` + `PREFECT_API_AUTH_STRING` on clients; CSRF/CORS settings [30]; no RBAC in OSS — RBAC is listed as a Cloud Enterprise feature on the pricing page [26], and the security-settings page [30] does not mention RBAC at all | Web UI only |
| Windmill | Schedules (croner syntax, seconds field, `L`/`#`/`W`) [46]; webhooks async/sync/SSE (`/api/w/{ws}/jobs/run{,_wait_result,_and_stream}/p/...`) [47]; MCP server (`/api/mcp/gateway`, Claude Code: `claude mcp add --transport http windmill <url>`) [44] | REST, `wmill` CLI, Python client `wmill` [45] | Jobs page streams logs live; Job Progress Stream API over SSE; cancel with reason [48]; Schedules menu [46] | Local accounts; SSO limited to 10 users in CE [41] | Web UI; MCP via claude.com connectors |
| Trigger.dev | Cron schedules, task triggers, Realtime | TS SDK; Python via `python.runScript` / `python.stream.runScript` inside a TS task [55] | Dashboard with run traces, logs never deleted self-hosted [52] | Dashboard login; `PAYMENT_DISABLED=true` unlocks all (HN) [107] | Web UI |
| Hatchet | Declarative crons (`on_crons=[...]`, UTC, 5/6 fields) or programmatic `create_cron` [64]; incoming webhooks with Basic/API-key/HMAC auth and CEL event-key mapping (docs show the cloud URL; self-hosted not stated) [68]; events | Python SDK `hatchet-sdk` (`HATCHET_CLIENT_TOKEN`, `HATCHET_CLIENT_TLS_STRATEGY=none` for self-host) [73]; REST + gRPC 7077; dashboard 8888/8080 [59][60]; **`hatchet mcp serve` / `hatchet mcp install --target claude-code,cursor`** [71] | Dashboard: runs, events, workers, Triggers → Cron Jobs; streams via `subscribe_to_stream` [63][64]; bulk cancel [67] | Email/password admin, API tokens; `-dev` images disable auth [60] | Web UI; MCP |
| LangSmith Deployment | Agent Server: assistants/threads/runs, crons, `/stream` [80] | `langgraph` CLI (`langgraph dev` in-memory, `langgraph build`) [78][79] | LangSmith UI (SaaS or Enterprise self-host) [76] | License key + `LANGSMITH_API_KEY` [79] | Web UI |
| Inngest | `TriggerCron` (tz, jitter), `TriggerEvent`, batch, debounce, cancel-on-event [88]; Event API | Python SDK (`pip install inngest`, FastAPI/`serve`; `pip install inngest[connect]` for WebSocket workers) [85][87]; single binary `inngest start` on 8288 (UI/API) + 8289 (Connect) [82] | Dev/self-host dashboard on 8288 [82] | `--event-key` / `--signing-key` [82] | Web UI |
| Dagster | Schedules, sensors (daemon required) [91]; GraphQL `launchRun` / `terminateRun` on `/graphql` [94] | Python, `dagster` CLI, GraphQL client [94] | Dagster webserver (runs, logs, assets) [91] | None built in for OSS webserver (unverified) | Web UI |
| Airflow 3 | Cron/timetables; REST API on api-server | Python, CLI | Airflow UI | Users/roles | Web UI |

## 3. Headless / server automation fit

- **Licence terms for a personal server.** n8n's Sustainable Use License permits "internal business purposes" and "non-commercial or personal use"; only `.ee.` files need an Enterprise licence [1]. Windmill CE is AGPL with "unlimited executions" [41]. Inngest is SSPL 1.0: running unmodified for internal use is unrestricted; the copyleft only bites if you offer it as a service [84]. Temporal, Hatchet, LangGraph OSS are MIT; Prefect, Dagster, Airflow, Trigger.dev are Apache-2.0 [13][40][57][74][81][95][99]. None of these impose ToS on headless personal automation; all are non-interactive by design.
- **Auth posture.** Temporal Web UI ships with no auth (OIDC is opt-in via `TEMPORAL_AUTH_ENABLED=true` + `TEMPORAL_AUTH_*` on the UI server [109]) and Temporal says hosts "should not be exposed to the open internet" [15][22] — put it behind Cloudflare Access, never on the tunnel unauthenticated. Prefect OSS has only basic auth [30] and no RBAC (RBAC is a Cloud Enterprise feature per the pricing page [26]; [30] is silent on it). Hatchet dev images disable auth entirely (`-dev` variants) [60]. Windmill CE has local accounts + SSO for ≤10 users [41]. n8n CE lacks SSO/LDAP [3].
- **Rate limits.** Self-hosted: none documented for any candidate. Cloud tiers: Prefect Hobby 625 API req/min [26]; Hatchet Team 500 RPS [61]; Inngest Free 50k executions/mo, 5 concurrent steps [83].
- **Security-relevant behaviours.** n8n's Execute Command node runs shell on the n8n host and is "disabled by default from n8n 2.0" for security [6]; re-enable it (and Read/Write Files from Disk) by clearing the block list, `NODES_EXCLUDE="[]"` [111]. n8n's public REST API is enabled by default on self-hosted instances (opt out with `N8N_PUBLIC_API_DISABLED=true`); the built-in API playground is self-hosted-only, and on Cloud the API is unavailable during the free trial [110] — so an exposed CE instance has an authenticated-by-API-key management surface on from day one. Windmill's MCP preprocessors can read `x-user-id` headers that "cannot be forged by prompt injection" [44]. Hatchet encrypts webhook secrets [68]. Inngest self-hosted has "no automatic database cleanup" — you delete old rows yourself [82]; Hatchet defaults to 30-day retention via `SERVER_LIMITS_DEFAULT_TENANT_RETENTION_PERIOD=720h` [70]; n8n prunes executions after `EXECUTIONS_DATA_MAX_AGE=336` h [5]; Windmill OSS retains job details max 30 days [48]; Temporal's per-namespace retention of closed workflows defaults to **3 days** when unset at `temporal operator namespace create` (min 1 day; max 30 days on ≤1.17, only storage-bounded from 1.18) [108] — the dev server's `--db-filename` persistence is still subject to it, so a 3-day default makes Temporal's "run history" the shortest of the shortlist unless raised at namespace creation. Windmill stores only the first 5,000 characters of a job's logs in Postgres as a buffer; larger logs are streamed to instance object storage on Enterprise Edition [48], and whether CE streams them into its 10 GiB object-storage quota [41] is not stated on the jobs page (unverified as of 2026-09-24) — a 90-minute streaming job in CE would hit the buffer within minutes, so treat Windmill's live-log view as a tail, not an archive.
- **macOS reality.** Only Prefect (pip), Temporal CLI (`brew install temporal`, arm64) [17], Inngest (brew/curl binary) [87] and n8n (npm) run natively without Docker. Windmill, Hatchet, Trigger.dev, LangGraph Agent Server and Airflow are Docker-first; Airflow production is Linux-only [96]. Docker Desktop's VM memory "defaults to 50% of your host's memory" [106] — 8 GB on this box, i.e. more than the 6 GB headroom, so the VM must be capped explicitly (2–3 GB) or replaced by a lighter runtime (OrbStack/colima remain unverified as of 2026-09-24 — the memory-footprint claims for Hatchet/Windmill on the Mini hinge on which runtime is used). Image architecture is no longer a blocker: `ghcr.io/windmill-labs/windmill:main` and `ghcr.io/hatchet-dev/hatchet/hatchet-lite:latest` both publish linux/amd64 + linux/arm64 manifests [114].

## 4. Cost

**Self-hosting licence cost is $0 for every candidate.** What differs is footprint and what is gated.

| Product | Free/self-host tier and gates | Paid reference points |
|---|---|---|
| n8n | CE: "almost the complete feature set", no execution limit; excludes variables, environments, external secrets, S3 binary, log streaming, multi-main, projects, SSO, sharing, Git; registering (email) unlocks folders, debug-in-editor, custom execution data [3] | Cloud Starter €20/mo billed annually (2,500 exec, 5 concurrent), Pro €50/mo billed annually (10k exec, 20 concurrent), Business €667/mo billed annually, self-hosted only (40k exec, SSO/Git/secrets), Enterprise custom (200+ concurrent) [2] |
| Temporal | Server + UI MIT, no gates [13] | Temporal Cloud $50/M actions ($25/M volume), $150 credits for 90 days, no base fee; Business support from $500/mo; active storage $0.042/GBh [18] |
| Prefect | Server Apache-2.0; webhooks, email notifications, incidents, AI log summaries are Cloud-only [34][35] | Cloud Hobby free (2 users, **5 deployments**, 7-day retention, 625 req/min), Starter $100/mo (20 deployments), Team $100/user/mo (100 deployments, 14-day retention), Enterprise custom [26] |
| Windmill | CE: unlimited executions, ≤3 workspaces, ≤50 users, SSO ≤10, 10 GiB object storage, 100 email triggers/day; no audit logs, git sync, error/recovery handlers, **concurrency limits**, UI-managed worker groups, dedicated workers; job retention 30 days [41][43][46][48][49] | EE self-hosted from $120/mo ($20/dev, $10/operator, $50/worker/mo) [41] |
| Trigger.dev | Apache-2.0; self-host loses warm starts, autoscaling, checkpoints [52][57] | Cloud Free $5 credits/mo, 20 concurrent, 10 schedules, 1-day logs; Hobby $10; Pro $50; runs $0.25/10k + compute $0.0000169/s (0.25 vCPU) to $0.00068/s [54] |
| Hatchet | MIT; lite or compose; retention 30 days configurable [59][70][74] | Cloud Developer free 100k runs/mo then $10/M; Team $500/mo (3-day retention, 500 RPS); Scale $1,000/mo; Enterprise incl. self-hosting support [61] |
| LangSmith Deployment | OSS `langgraph` MIT; `langgraph dev` needs a free `LANGSMITH_API_KEY` [78]; standalone server needs `LANGGRAPH_CLOUD_LICENSE_KEY` [79]; full self-hosted LangSmith is "an add-on to the Enterprise plan" [76] | Developer $0 (5k traces/mo, 1 seat), Plus $39/seat (10k traces, 1 free small serverless deployment), Enterprise custom; LCU $1.50, LSU $1.00 [75] |
| Inngest | SSPL; `inngest start` with SQLite + in-memory Redis, or Postgres + Redis; support not guaranteed for self-host [82][84] | Cloud Free 50k exec/mo, 5 concurrent steps, 3 workers, 24-h trace history; Pro $99+/mo; Business $499+/mo [83]; step timeout max 2 h, function run length Free 30 days [86]. Note the usage-limits page [86] still lists a "Basic" plan (25 concurrent steps, 90-day runs, 512 KiB events) that the pricing page [83] no longer offers (Free/Pro/Business/Enterprise) — vendor docs inconsistency; which table is current is unverified as of 2026-09-24 |
| Dagster | OSS Apache-2.0, all three services free [95] | Dagster+ Solo $120/mo (7.5k credits/mo included) and Starter $1,200/mo (30k credits/mo) — the pricing page states "Updated Solo and Starter pricing takes effect May 1, 2026", so the older $10/mo + $0.04/credit and $100/mo figures still shown on the page are superseded as of 2026-09-24 (the page's FAQ still describes the pay-as-you-go model, so the exact in-force terms are unverified as of 2026-09-24); Pro/Enterprise custom [90] |
| Airflow | Apache-2.0 | n/a (managed offerings not evaluated) |
| Keep-bespoke add-ons | Grafana OSS AGPL-3.0 [102]; Grafana Cloud Free: 10k series, 50 GB logs, 50 GB traces, 14-day retention, 3 users [101]; Healthchecks self-host BSD-3 (Python 3.12+, Django, Postgres) [103] or hosted Free 20 checks/100 log entries, Business $20/mo 100 checks [104]; Cronicle MIT (Node.js cron UI, live log viewer, REST API) [105] | — |

**This server's load: ~1,500 jobs/month (30–60/day), 2 concurrent, ~20 distinct schedules (assumption), median job short, tail 5–90 min. Assumptions: 1 job = 1 workflow run ≈ 10 orchestrator "actions"/steps; no cloud storage beyond metadata.**

| Option | Monthly $ | Binding limit at this load | RAM budget on the Mini (Docker VM incl. where needed) |
|---|---|---|---|
| Bespoke runner (today) | $0 | none | already paid |
| Bespoke + OTEL collector + Prometheus + Grafana OSS (local) | $0 | none | ~0.6–1.2 GB (unverified estimate) |
| Bespoke + Grafana Cloud Free + hosted Healthchecks Free | $0 | Healthchecks Free = 20 checks (≈ our schedule count; tight) [104]; Grafana 10k series [101] | ~0.1 GB (collector only) |
| Prefect 3 server (pip, Postgres) | $0 | none in OSS; Cloud Hobby's 5-deployment cap would bind [26] | ~0.3–0.6 GB server + one worker (unverified) |
| Hatchet lite (Docker, Postgres msgqueue) | $0 | none; default 60 s execution timeout must be raised or extended in-task via `ctx.refresh_timeout` [65] | ~0.5–1 GB + Docker VM (unverified); arm64 image published [114] |
| Temporal (brew dev server `--db-filename`, or compose postgres-only) | $0 | 2 MB payload, 50 MB history [23] | dev binary ~0.2–0.4 GB (unverified); compose ~1 GB + VM (unverified) |
| Windmill CE (Docker) | $0 | concurrency limits EE-only [43]; 30-day retention; 5,000-char DB log buffer per job, S3 log streaming EE [48] | server + LSP + 1 worker at "1 worker per 1 vCPU and 1–2 GB RAM" [42] ⇒ ~2–3 GB + VM |
| n8n CE (npm or Docker, Postgres) | $0 | none by default: `EXECUTIONS_TIMEOUT` defaults to `-1` (no timeout); `EXECUTIONS_TIMEOUT_MAX` (default 3,600 s) only caps the per-workflow timeout a user may set and is itself configurable [5] | ~0.3–0.6 GB (unverified) |
| Temporal Cloud (if ever) | ≈$0.75 (15k actions × $50/M) — below any minimum; $150 credit covers 90 days [18] | none | workers only |
| Hatchet Cloud Developer | $0 (15k of 100k free runs) [61] | 100k runs/mo | workers only |
| Inngest Cloud Free | $0 (1.5k of 50k) [83] | 5 concurrent steps, 24-h traces, 3 Connect workers [83][85] | workers only |
| Trigger.dev Cloud | ≈$30+ (1.8M compute-seconds × $0.0000169 at 0.25 vCPU) minus $5 credit [54] (unverified arithmetic; Python wrapper overhead ignored) | 10 schedules on Free [54] | n/a |

## 5. Strengths & weaknesses per reviews

Benchmarks: Windmill publishes a competitor benchmark (Windmill 1.483.1 vs Airflow 2.7.3, Prefect 2.14.4, Temporal 2.34.0, Kestra 0.22.3, Hatchet 0.62.0 on AWS m4.large; fibonacci tasks; timings taken from APIs/DB with no cross-engine timestamp verification) [50]; its GitHub tagline claims "13x vs Airflow" [51]. Vendor-run, the compared versions are 18+ months behind current releases (Prefect 3.8.x, Hatchet 0.107.x, Windmill 1.817), and irrelevant at 2 concurrent — do not weight it (whether the relative ordering still holds on current versions is unverified as of 2026-09-24).

- **n8n** — HN: "I can run it locally without limits" (simple10, 2025-05-03, story 43879282); a production user hit "30-second execution limits" and "Memory caps at 512MB caused OOMs" on n8n Cloud and left (webRunes, 2025-12-21, story 46346022); "n8n requires a lot of time and care. It's not intended for high loads" (neoecos, 2025-05-03, story 43879282); licence is fine for internal/non-commercial but a startup was quoted "$50k for a commercial license" (JimDabell, 2025-07-17, story 44592006) [107]. Docs themselves say memory issues come from large JSON, Code nodes and manual executions, and that Execute Command is off by default in 2.0 [6][11].
- **Temporal** — HN: self-hosted deploy docs "does _not_ look simple" (gsanderson, 2023-02-02, story 34610686); Temporal staff: "100% open source (MIT license)…self-host it anywhere you like" (tomwheeler, 2026-04-30, story 47966625); "Temporal and co are not for real-time data pubsub…keep small memory footprint, better to use something else" (adeptima, 2024-12-21, story 42482037) [107]. Docs confirm the compose files are "intended for local development and testing" and the dev server "is not intended for production use" [16][24]. The archived `temporalio/docker-compose` warned ARM builds v1.12–v1.14 were broken, fixed from v1.14.2 [25].
- **Prefect** — HN: "more polish and is easier to get started than any of the existing options. We've been running their self-hosted for over three years and it basically stays out of the way" (computershit, 2024-08-12, story 41224316); chose self-hosted Prefect over a $20k/yr Dagster+ quote (Eridrus, 2024-08-22, story 41320774); "Prefect even removed basic features from the self-hosted version (webhooks) to force people to use their Cloud offering" (hk__2, 2025-12-04, story 46064757) [107] — consistent with docs [35].
- **Windmill** — HN: "you don't need to make any changes to existing scripts when migrating" (igorlp, 2025-10-10, story 45534012); founder on AGPL being "less friendly" than Apache (rubenfiszel, 2024-07-23, story 41037745); "made running and tracking these things accessible to my 'low'-technical co-founder" (bluecoconut, 2023-08-04, story 37000920); "if you don't care about the solution being a proper data pipelines orchestration platform, I'd recommend starting with Windmill" (computershit, 2024-08-12, story 41224316) [107].
- **Hatchet** — HN: "Can't see anywhere that describes what each one of those does" about the multi-service deploy (anentropic, story 43572733); "there are too many things to learn to get even a simple example…going" (bosky101, story 43572733); founder: "a general-purpose background jobs platform which offers durable workflows as a feature" (abelanger, 2026-01-03, story 46466074); "Hatchet and Temporal are MIT licensed…I can't find the license for Inngest" (ensignavenger, 2024-06-27, story 40813704) [107]. Engine still 0.x semver (v0.107.2, 2026-09-18); the Python SDK is versioned independently and is at `hatchet-sdk` 1.41.1 on PyPI (2026-09-24) [74][113], so the SDK surface the recipe in §7c uses is past 1.0 even though the engine is not.
- **Inngest** — HN: "so much simpler operationally" than Temporal (mshafir, 2026-09-14, story 49696335); "unfortunately not very reliable" (presentation, 2025-10-24, story 45686472); Inngest engineer on extreme load: "doesn't scale so well at this load, at all" (tonyhb, 2026-03-11, story 47320768) [107]. Docs: support "does not guarantee direct support for self-hosted instances" [82].
- **Trigger.dev** — HN: "a simplified temporal…exclusively in Typescript" (rubenfiszel, story 34610686); "Self-hostable with PAYMENT_DISABLED=true" (zlwaterfield, 2025-12-01, story 46102906) [107]. Docs: 6 GB + 8 GB minimums [53].
- **LangGraph/LangSmith** — HN: "Their docs are content marketing for platform services" (senko, 2025-04-07, story 43580012); a production user says deployments "was one of the only ways…your agent was going to work…in production" but the TS SDK "felt…not super TypeScript-y" (shcallaway, 2025-10-21, story 45658381) [107].
- **Dagster / Airflow** — HN: Airflow "criticized harshly for poor local development experience and deployment complexity"; Dagster liked but faced adoption resistance (computershit, 2024-08-12, story 41224316) [107]. Airflow docs: SQLite/SequentialExecutor standalone is dev-only, ≥4 GB, compose "does not provide any security guarantees required for production" [97][98].

Reliability record (from primary docs, not opinion): Temporal enforces hard limits (2 MB blob, 4 MB gRPC, 50 MB / 51,200-event history, 2,000 pending ops) that make it predictable [23]; Hatchet timed-out tasks are "not guaranteed…stopped immediately" [65]; Windmill workers "stream the logs while executing" and cancellations are recorded with `canceled_by`/`canceled_reason` [48]; Prefect's scheduler creates runs up to `P100D` ahead, max 100 per deployment, loop 60 s [36].

## 6. Finance / trading relevance

None of the ten products has any finance-specific feature. Two indirect points: (1) Atlas's paper-trading/research loops are exactly the "cron + retries + run history + cancel" workload every candidate covers, and a durable engine (Temporal, Hatchet durable tasks with replay/"exactly-once semantics" [72]) would give crash-resume for multi-step research chains — but Atlas has no live order path, so durability's main payoff (never double-submitting an order) does not apply today. (2) Windmill's native worker group ships Postgres/MySQL/Snowflake/BigQuery connectors for lightweight data jobs [49]; irrelevant to the Claude-subprocess pattern.

## 7. Integration recipe for our server

**Recommended: keep the bespoke runner; bolt on observability and a "did it run" contract now; run Prefect 3 in shadow mode as the optional UI pilot; reach for Hatchet only if native priority lanes/streaming are required.** Rationale: the 11k lines include Telegram auth, guards, audit logs, protected-path policy, deploy gates and the Agent SDK harness — none of which any orchestrator replaces; what they replace (croniter + queue + state machine + a dashboard) is the smallest, most stable part. The orchestrator that replaces it must itself fit in ~1 GB, run on macOS without a fat Docker VM, and accept a 90-minute subprocess that streams events — which every candidate does only with caveats (see per-product gotchas).

### 7a. Keep-bespoke + X (do first; ~days)

1. **Cost/tokens per job, for free, from the Agent SDK.** Claude Code emits OTEL metrics `claude_code.cost.usage` (USD, attrs `model`, `query_source`=main/subagent/auxiliary), `claude_code.token.usage`, `claude_code.session.count`, plus events `claude_code.api_request`, `tool_result` etc. [100]. Set on the job subprocess env:
   ```bash
   CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_METRICS_EXPORTER=otlp OTEL_LOGS_EXPORTER=otlp \
   OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318 \
   OTEL_RESOURCE_ATTRIBUTES=job_id=$JOB_ID,skill=$SKILL
   ```
   Sink: either a local OTEL collector → Prometheus → Grafana OSS (AGPL; ~0.6–1.2 GB, unverified) or the collector forwarding to **Grafana Cloud Free** (10k series, 50 GB logs, 14-day retention) [101] — metrics only, no job content. (Whether the cost metric is populated under Max subscription auth is not stated in the doc [100] — verify on the first job.)
   **Cardinality warning.** `OTEL_METRICS_INCLUDE_RESOURCE_ATTRIBUTES` defaults to `true`, which copies every key in `OTEL_RESOURCE_ATTRIBUTES` onto every metric datapoint — so the `job_id=$JOB_ID` above becomes a new series per job per metric per model/effort combination, and `OTEL_METRICS_INCLUDE_SESSION_ID` (default `true`) adds `session.id` on top [100]. At ~1,500 jobs/month that blows through Grafana Cloud Free's 10k active series in days. Set `OTEL_METRICS_INCLUDE_RESOURCE_ATTRIBUTES=false OTEL_METRICS_INCLUDE_SESSION_ID=false` for the metrics pipeline and keep `job_id`/`skill` only on the **logs/events** exporter (events are not series-bounded), or replace `job_id` with `skill` alone. `OTEL_METRICS_INCLUDE_VERSION` defaults to `false`; `OTEL_METRICS_INCLUDE_ACCOUNT_UUID` defaults to `true` [100]. Useful attributes that come for free on `claude_code.cost.usage`: `effort` (low…max), `speed` (`fast` when fast mode), `agent.name` (built-in subagent names verbatim, user-defined → `custom`), `skill.name` (third-party → `third-party`), `model` [100]. The `claude_code.assistant_response` event (one per model reply; `response` text redacted unless `OTEL_LOG_ASSISTANT_RESPONSES=1`, 60 KB truncation; `query_source` such as `repl_main_thread` or a subagent name) is the per-turn log line to mirror into the audit JSONL if you want one exporter instead of two [100].
2. **Dead-man switches per schedule.** Self-host Healthchecks (BSD-3, Django + Postgres you already run) [103] or use hosted Free (20 checks) [104]; the runner pings `/start` and `/<uuid>` around each schedule; Telegram notifications are built in. This answers "did it run" without a new UI.
3. **Run-history UI.** The existing web dashboard already reads the `jobs` table; add the three views every orchestrator UI has: run list with status/duration filters, per-run event stream (tail the audit_log JSONL over SSE), and a "next 24 h" schedule table from croniter. Estimated 300–600 lines (unverified).

### 7b. Shadow-mode pilot: Prefect 3 as the visibility layer (~1–2 weeks)

Why Prefect over the others for a pilot: pure pip, Apache-2.0, SQLite default or your Postgres (`PREFECT_SERVER_DATABASE_CONNECTION_URL=postgresql+asyncpg://…`) [28], Process work pool runs each flow "within its own isolated subprocess" [37], deployment `concurrency_limit` (an `int` or a `ConcurrencyLimitConfig(limit=…, collision_strategy=ENQUEUE|CANCEL_NEW)` from `prefect.client.schemas.objects`; `grace_period_seconds` 60–86,400, server default 300 s, is how long a `CANCEL_NEW`/`ENQUEUE` slot stays held while infrastructure starts; CLI `prefect deploy --concurrency-limit 1 --collision-strategy CANCEL_NEW`) [33][115], work-queue priority ("lower numbers take greater priority") [32], global concurrency limits with 5-minute leases [31], cron/interval/RRule with IANA tz [36], automations in OSS [34], REST `POST /api/deployments/{id}/create_flow_run` for the Telegram bot [39], basic auth [30].

```bash
pip install "prefect==3.8.*"                      # same venv as the runner
prefect config set PREFECT_SERVER_DATABASE_CONNECTION_URL="postgresql+asyncpg://…/prefect"
PREFECT_SERVER_API_AUTH_STRING="admin:$(openssl rand -hex 16)" prefect server start --host 127.0.0.1   # UI :4200, behind Caddy + CF Access
prefect work-pool create agent-pool --type process
prefect work-queue create fast --pool agent-pool --priority 1 ; prefect work-queue create slow --pool agent-pool --priority 2
prefect worker start --pool agent-pool --limit 2                # the "2 concurrent" lane
```
```python
# flows/agent_job.py — thin wrapper; the existing executor stays untouched
from prefect import flow, get_run_logger
from runner.executor import run_job          # bespoke code, unchanged

@flow(log_prints=True, timeout_seconds=90*60)
def agent_job(job_id: str, skill: str, payload: dict):
    log = get_run_logger()
    for ev in run_job(job_id, skill, payload):   # generator yielding audit events
        log.info("%s", ev)                       # shows live in the Prefect run page
if __name__ == "__main__":
    from prefect.client.schemas.objects import ConcurrencyLimitConfig, ConcurrencyLimitStrategy
    agent_job.to_deployment(name="atlas-research", cron="0 13 * * 3", work_queue_name="slow",
                            concurrency_limit=ConcurrencyLimitConfig(limit=1, collision_strategy=ConcurrencyLimitStrategy.CANCEL_NEW)).apply()
    # to_deployment/deploy have no collision_strategy kwarg; concurrency_limit is int | ConcurrencyLimitConfig (CLI: --concurrency-limit 1 --collision-strategy CANCEL_NEW)
```
Gotchas: no inbound webhooks in OSS [35] — the Telegram bot calls the REST API; Prefect logs go through the API (`log_prints`), so keep the JSONL audit log as the source of truth and mirror at ~1 line/s max; OSS has no retention pruning documented — schedule a `prefect` DB cleanup (unverified); `serve()`-style processes pause their schedule on Ctrl-C by default [37] — `flow.serve(..., pause_on_shutdown=False)` keeps the schedule active across restarts ("If True, provided schedule will be paused when the serve function is stopped. If False, the schedules will continue running") [115], which is what you want under launchd where the process is restarted by the supervisor rather than retired; the `prefect worker` + work-pool path used above does not have this behaviour at all, since schedules live on the server.

### 7c. Alternative pilot: Hatchet lite (if priority lanes + streaming must be native)

```bash
curl -O https://docs.hatchet.run/…/docker-compose.hatchet.yml   # lite: postgres + hatchet-lite on 8888 (UI/API) + 7077 (gRPC) [59]
SERVER_MSGQUEUE_KIND=postgres docker compose -f docker-compose.hatchet.yml up -d          # no RabbitMQ [60]
export HATCHET_CLIENT_TOKEN=…  HATCHET_CLIENT_TLS_STRATEGY=none                            # [73]
hatchet mcp install --target claude-code && hatchet mcp auth --grant local                 # [71]
```
```python
from datetime import timedelta
from hatchet_sdk import Hatchet, Context, ConcurrencyExpression, ConcurrencyLimitStrategy
hatchet = Hatchet()
wf = hatchet.workflow(name="agent-job", on_crons=["0 13 * * 3"], default_priority=1,
    concurrency=ConcurrencyExpression(expression="'global'", max_runs=2,
                                      limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN))
@wf.task(execution_timeout=timedelta(minutes=20), schedule_timeout=timedelta(hours=6))
async def run(input, ctx: Context):
    async for ev in run_job_async(input.job_id):
        if ctx.exit_flag: break                       # cancellation from dashboard/API [67]
        if ev.kind == "heartbeat": ctx.refresh_timeout(timedelta(minutes=15))   # additive: extends the running task's deadline while it keeps producing events [65]
        await ctx.aio_put_stream(ev)                  # live in dashboard / subscribe_to_stream [63]
hatchet.worker("mini", slots=2, workflows=[wf]).start()
```
Gotchas: default execution timeout is **60 s** and schedule timeout 5 min [65]; `ctx.refresh_timeout(timedelta)` is additive ("the new timeout is added to the existing timeout") and can be called repeatedly, so a modest fixed `execution_timeout` plus refreshes on each streamed event bounds a hung job faster than a flat 95-minute ceiling for variable-length work [65]; crons are UTC and missed schedules are not replayed [64]; streamed chunks are dropped if no consumer is subscribed before they're published [63]; priority only orders runs of the same workflow [66]; incoming-webhook docs show only the cloud URL [68]; Docker VM memory must be capped [106].

### 7d. Why not the rest (one line each)

Temporal: excellent durability, but events cannot flow through it (2 MB payload, 50 MB history [23]); you'd heartbeat a progress summary every ~30 s (`heartbeat_timeout`, cancellations "delivered…when they Heartbeat" [21]) and still keep your own event store — you gain durability you don't need yet and lose nothing in visibility only if you also build UI glue. Windmill: best UI/MCP, but concurrency limits are EE-only [43], job history 30 days [48], and Python deps are resolved per script by Windmill's own lockfile [45] — run our venv via a bash script instead. n8n: Telegram + MCP native [7][8], but Execute Command is disabled by default (`NODES_EXCLUDE="[]"` re-enables it) [6][111], the native Python task runner only imports packages baked into the `n8nio/runners` image (so our venv is reachable only through Execute Command) [112], no per-execution timeout unless you set one (`EXECUTIONS_TIMEOUT=-1`) [5], FIFO with no priority [4]. Inngest: HTTP-invoked steps (or Connect WS), step timeout ≤2 h [86], SSPL [84], the self-hosting quick-start's worker examples are Node/Go only — a Python worker is assembled from the separate Python quick-start (`pip install inngest`, `serve` a FastAPI app or `inngest[connect]`) pointed at `INNGEST_DEV=0`/self-host URL [82][85][87]; the docs' plan tables are also internally inconsistent (usage-limits lists a "Basic" plan the pricing page no longer has) [83][86]. Trigger.dev/Airflow/LangSmith: footprint and licensing (§1).

## 8. Verdict

1. Every candidate is free to self-host; the decision is footprint, macOS-native install, and how gracefully a 90-minute streaming subprocess fits — Prefect and Hatchet fit, Temporal fits with a side channel, Windmill/n8n fit with gates, the rest do not.
2. The bespoke runner already implements the parts that are hard to buy (Telegram auth, guards, audit, deploy gates); an orchestrator would replace only the scheduler/queue/state machine and give a UI in return.
3. Do "keep + X" now: Agent SDK OTEL metrics (cost/tokens) → Grafana (local or Cloud Free), Healthchecks-style pings per schedule, three dashboard views.
4. Pilot Prefect 3 in shadow mode (pip, your Postgres, Process pool, 2-slot worker); promote only if the UI measurably reduces "what happened?" time.
5. Choose Hatchet lite instead only if native priority lanes, concurrency keys and live streams in the UI are must-haves and a capped Docker VM is acceptable; leave Temporal for a future live-order path.

Fit scores (1–10) for this box and workload:

| Product | Research (visibility of long runs) | Coding/agentic (host Agent SDK subprocesses) | Cost efficiency | Automation friendliness (API/cron/webhooks/Telegram) | Trading research (Atlas loops) |
|---|---|---|---|---|---|
| Keep bespoke + OTEL/Grafana + Healthchecks | 7 | 9 | 10 | 8 | 8 |
| Prefect 3 (self-hosted) | 8 | 8 | 9 | 7 (no OSS webhooks) | 8 |
| Hatchet (lite) | 8 | 8 | 8 (Docker VM tax) | 8 | 8 |
| Temporal (self-hosted) | 6 | 7 | 8 | 6 (no inbound webhook, UI unauthenticated) | 7 (durability unused without live orders) |
| Windmill CE | 8 | 6 (own dep model; concurrency EE) | 8 | 8 (MCP, webhooks, SSE) | 7 |
| n8n CE | 5 | 4 | 9 | 8 (Telegram, MCP) | 5 |
| Inngest (self-hosted) | 6 | 6 | 8 | 7 | 6 |
| Dagster OSS | 5 | 4 | 7 | 5 | 6 (asset model suits data, not agents) |
| Trigger.dev | 6 | 3 (TS wrapper) | 3 (14 GB minimums) | 6 | n/a — cannot run on this box |
| LangSmith Deployment | 6 | 3 (LangGraph-only) | 4 (licence key; Enterprise self-host) | 5 | n/a — not deployable here |
| Airflow 3 | 5 | 3 | 5 (≥4 GB, Linux prod) | 5 | n/a — Linux-only production |

## 9. Sources

All accessed 2026-09-24.

1. https://raw.githubusercontent.com/n8n-io/n8n/master/LICENSE.md
2. https://n8n.io/pricing/
3. https://docs.n8n.io/deploy/host-n8n/community-edition-features.md
4. https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/control-concurrency.md
5. https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/executions.md
6. https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand.md
7. https://docs.n8n.io/build/ways-of-building-workflows/connect-to-n8n-mcp-server.md
8. https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.telegramtrigger.md
9. https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode.md
10. https://docs.n8n.io/deploy/host-n8n/install-options/install-with-docker.md
11. https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/fix-memory-issues.md
12. https://api.github.com/repos/n8n-io/n8n and https://api.github.com/repos/n8n-io/n8n/releases/latest
13. https://api.github.com/repos/temporalio/temporal and https://api.github.com/repos/temporalio/temporal/releases/latest
14. https://api.github.com/repos/temporalio/sdk-python/releases/latest
15. https://docs.temporal.io/self-hosted-guide/deployment
16. https://docs.temporal.io/cli/server
17. https://docs.temporal.io/cli/setup-cli
18. https://temporal.io/pricing
19. https://docs.temporal.io/develop/python/schedules
20. https://docs.temporal.io/develop/python/failure-detection
21. https://docs.temporal.io/encyclopedia/detecting-activity-failures
22. https://docs.temporal.io/web-ui
23. https://docs.temporal.io/self-hosted-guide/defaults
24. https://github.com/temporalio/samples-server/tree/main/compose
25. https://github.com/temporalio/docker-compose (archived 2026-01-05)
26. https://www.prefect.io/pricing
27. https://docs.prefect.io/v3/manage/server/index
28. https://docs.prefect.io/v3/how-to-guides/self-hosted/server-cli.md
29. https://docs.prefect.io/v3/how-to-guides/self-hosted/server-docker.md
30. https://docs.prefect.io/v3/advanced/security-settings.md
31. https://docs.prefect.io/v3/concepts/global-concurrency-limits.md
32. https://docs.prefect.io/v3/concepts/work-pools.md
33. https://docs.prefect.io/v3/concepts/deployments.md
34. https://docs.prefect.io/v3/concepts/automations.md
35. https://docs.prefect.io/v3/concepts/webhooks
36. https://docs.prefect.io/v3/concepts/schedules.md
37. https://docs.prefect.io/v3/how-to-guides/deployment_infra/run-flows-in-local-processes.md
38. https://docs.prefect.io/v3/how-to-guides/workflows/run-background-tasks.md
39. https://docs.prefect.io/v3/api-ref/rest-api/server/deployments/create-flow-run-from-deployment
40. https://api.github.com/repos/PrefectHQ/prefect and https://api.github.com/repos/PrefectHQ/prefect/releases/latest
41. https://www.windmill.dev/pricing
42. https://www.windmill.dev/docs/advanced/self_host
43. https://www.windmill.dev/docs/core_concepts/concurrency_limits
44. https://www.windmill.dev/docs/core_concepts/mcp
45. https://www.windmill.dev/docs/getting_started/scripts_quickstart/python
46. https://www.windmill.dev/docs/core_concepts/scheduling
47. https://www.windmill.dev/docs/core_concepts/webhooks
48. https://www.windmill.dev/docs/core_concepts/jobs
49. https://www.windmill.dev/docs/core_concepts/worker_groups
50. https://www.windmill.dev/docs/misc/benchmarks/competitors
51. https://api.github.com/repos/windmill-labs/windmill and https://api.github.com/repos/windmill-labs/windmill/releases/latest
52. https://trigger.dev/docs/self-hosting/overview
53. https://trigger.dev/docs/self-hosting/docker
54. https://trigger.dev/pricing
55. https://trigger.dev/docs/config/extensions/pythonExtension
56. https://trigger.dev/docs/runs/max-duration
57. https://api.github.com/repos/triggerdotdev/trigger.dev and https://api.github.com/repos/triggerdotdev/trigger.dev/releases/latest
58. https://docs.hatchet.run/self-hosting
59. https://docs.hatchet.run/self-hosting/hatchet-lite
60. https://docs.hatchet.run/self-hosting/docker-compose
61. https://hatchet.run/pricing
62. https://docs.hatchet.run/home/concurrency
63. https://docs.hatchet.run/home/streaming
64. https://docs.hatchet.run/home/cron-runs
65. https://docs.hatchet.run/home/timeouts
66. https://docs.hatchet.run/home/priority
67. https://docs.hatchet.run/home/cancellation
68. https://docs.hatchet.run/v1/webhooks
69. https://docs.hatchet.run/v1/workers
70. https://docs.hatchet.run/self-hosting/data-retention
71. https://docs.hatchet.run/reference/cli/mcp
72. https://docs.hatchet.run/home/durable-execution
73. https://raw.githubusercontent.com/hatchet-dev/hatchet-python-quickstart/main/README.md
74. https://api.github.com/repos/hatchet-dev/hatchet and https://api.github.com/repos/hatchet-dev/hatchet/releases/latest
75. https://www.langchain.com/pricing
76. https://docs.langchain.com/langsmith/self-hosted
77. https://docs.langchain.com/langsmith/deployments
78. https://docs.langchain.com/oss/python/langgraph/local-server
79. https://docs.langchain.com/langsmith/deploy-standalone-server
80. https://docs.langchain.com/langsmith/agent-server
81. https://api.github.com/repos/langchain-ai/langgraph and https://api.github.com/repos/langchain-ai/langgraph/releases/latest
82. https://www.inngest.com/docs/self-hosting
83. https://www.inngest.com/pricing
84. https://raw.githubusercontent.com/inngest/inngest/main/LICENSE.md
85. https://www.inngest.com/docs/setup/connect
86. https://www.inngest.com/docs/usage-limits/inngest
87. https://www.inngest.com/docs/getting-started/python-quick-start
88. https://www.inngest.com/docs/reference/python/functions/create
89. https://api.github.com/repos/inngest/inngest and https://api.github.com/repos/inngest/inngest/releases/latest
90. https://dagster.io/pricing
91. https://docs.dagster.io/deployment/oss/oss-deployment-architecture
92. https://docs.dagster.io/deployment/oss/oss-instance-configuration
93. https://docs.dagster.io/guides/operate/managing-concurrency
94. https://docs.dagster.io/api/graphql/index
95. https://api.github.com/repos/dagster-io/dagster and https://api.github.com/repos/dagster-io/dagster/releases/latest
96. https://airflow.apache.org/docs/apache-airflow/stable/installation/prerequisites.html
97. https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html
98. https://airflow.apache.org/docs/apache-airflow/stable/start.html
99. https://api.github.com/repos/apache/airflow
100. https://code.claude.com/docs/en/monitoring-usage
101. https://grafana.com/pricing/
102. https://api.github.com/repos/grafana/grafana
103. https://healthchecks.io/docs/self_hosted/
104. https://healthchecks.io/pricing/
105. https://api.github.com/repos/jhuckaby/Cronicle, https://raw.githubusercontent.com/jhuckaby/Cronicle/master/README.md, https://raw.githubusercontent.com/jhuckaby/Cronicle/master/LICENSE.md
106. https://docs.docker.com/desktop/settings-and-maintenance/settings/
107. Hacker News via Algolia API, comment search, queries: `hatchet temporal inngest`, `n8n self-hosting`, `temporal.io self-host`, `windmill orchestrator`, `prefect self-hosted`, `prefect dagster airflow self-hosted`, `trigger.dev self-host`, `langgraph platform`, `inngest`, `hatchet.run` — https://hn.algolia.com/api/v1/search?query=<q>&tags=comment&hitsPerPage=40 (story IDs quoted inline)
108. https://docs.temporal.io/temporal-service/temporal-server (namespace retention defaults)
109. https://docs.temporal.io/self-hosted-guide/security (Web UI OIDC env vars)
110. https://docs.n8n.io/connect/n8n-api.md and https://docs.n8n.io/connect/n8n-api/api-reference.md
111. https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/block-specific-nodes.md
112. https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.code/
113. https://pypi.org/pypi/langgraph/json, https://pypi.org/pypi/langgraph-cli/json, https://pypi.org/pypi/hatchet-sdk/json, https://pypi.org/pypi/prefect/json
114. https://ghcr.io/v2/windmill-labs/windmill/manifests/main and https://ghcr.io/v2/hatchet-dev/hatchet/hatchet-lite/manifests/latest (OCI image index, anonymous pull token)
115. https://docs.prefect.io/v3/api-ref/python/prefect-flows (`to_deployment`/`deploy`/`serve` signatures)

Not found on first pass (WebSearch budget exhausted; direct fetches failed) — status after the 2026-09-24 re-verification: (resolved) n8n public REST API docs live at https://docs.n8n.io/connect/n8n-api.md and https://docs.n8n.io/connect/n8n-api/api-reference.md; Temporal default namespace retention is 3 days when unset at `temporal operator namespace create` (min 1 day; max 30 days on ≤1.17, storage-bounded from 1.18) per https://docs.temporal.io/temporal-service/temporal-server, LangGraph "Self-Hosted Lite / 1M nodes per year" tier (legacy langchain-ai.github.io page only redirects; current docs do not list it), (resolved) ghcr.io/windmill-labs/windmill:main is a multi-arch manifest (amd64 + arm64); ghcr.io/hatchet-dev/hatchet/hatchet-lite:latest is also amd64 + arm64, exact RAM footprints for Temporal/Hatchet/Prefect/n8n/Inngest servers (no vendor numbers; all marked unverified), Reddit threads (fetch blocked).

## Verification log (2026-09-24)

**Corrections applied (13).**
- Major (2): Dagster+ Solo/Starter cloud reference points ($10/$100 → $120/$1,200 with credit bundles, May-2026 repricing; page still shows both blocks and a pay-as-you-go FAQ, flagged unverified); Prefect §7b snippet (`collision_strategy` is not a `to_deployment` kwarg — now `ConcurrencyLimitConfig` from `prefect.client.schemas.objects`, with CLI flags noted).
- Minor (11): n8n default execution timeout (none; `EXECUTIONS_TIMEOUT=-1`, `EXECUTIONS_TIMEOUT_MAX` only caps user-set values) in §1 and §4; n8n concurrency disabled by default; Hatchet engine `v0.107.2` + SDK `py/1.41.1` in §1 and §5; LangGraph row now cites PyPI `langgraph` 1.2.12 / `langgraph-cli` 0.4.32 instead of a CLI dev pre-tag; n8n public REST API row (docs found; on by default self-hosted, `N8N_PUBLIC_API_DISABLED`); n8n Cloud pricing qualified as billed-annually, Business self-hosted-only, Enterprise 200+ concurrent; n8n Python posture (native task runner, `n8nio/runners`, Pyodide gone, Cloud forbids imports); Temporal Web UI auth env vars with the correct source page; two "Not found" items marked resolved (n8n API docs, Temporal retention; Windmill/hatchet-lite arm64).

**Topics added.** Prefect `ConcurrencyLimitConfig` (`grace_period_seconds` 60–86,400, default 300 s) and `pause_on_shutdown=False` (§7b); Hatchet `ctx.refresh_timeout` (additive) in the §7c snippet and gotchas, SDK versioned independently of the engine (§5), arm64 images (§3, §4); n8n API defaults, `NODES_EXCLUDE="[]"`, native Python runner (§2, §3, §7d); Temporal 3-day default namespace retention (§3); Claude Code OTEL cardinality controls, `assistant_response` event and `effort`/`speed`/`agent.name`/`skill.name` attributes (§7a); Windmill 5,000-char DB log buffer with EE S3 streaming (§3, §4); Inngest "Basic"-plan docs inconsistency and Python self-host path (§4, §7d); OrbStack/colima still unverified (§3); Dagster+ repricing (§4).

**Claims re-verified with sources today.** Hatchet release list via GitHub API [74]; `hatchet-sdk` 1.41.1, `prefect` 3.8.6, `langgraph` 1.2.12, `langgraph-cli` 0.4.32 via PyPI JSON [113]; ghcr OCI indexes for windmill:main (amd64+arm64) and hatchet-lite:latest (amd64+arm64) [114]; Prefect deployment concurrency semantics [33] and `to_deployment`/`serve` signatures [115]; Prefect serve pause-on-stop text [37]; Hatchet timeout defaults and refresh semantics [65]; n8n API [110], node block list [111], Code-node Python [112]; Temporal retention [108]; Claude Code telemetry env defaults and attributes [100]; Windmill jobs log buffer [48]; Inngest usage-limits vs pricing [83][86]; Inngest self-hosting examples Node/Go [82]; Dagster pricing page text [90].

**Stale or unverifiable flags left in place.** Dagster+ exact in-force terms (page shows both pre- and post-May-2026 blocks); Inngest "Basic" plan (docs inconsistency); Windmill CE log-to-object-storage behaviour; Windmill competitor benchmark on current versions; OrbStack/colima footprint; all RAM footprint estimates; Prefect OSS retention-pruning; Trigger.dev cloud arithmetic; whether `claude_code.cost.usage` populates under subscription auth; Hatchet self-hosted incoming-webhook URL; LangGraph "Self-Hosted Lite" tier; Dagster OSS webserver auth.

**Quality rating: good.** Primary-source coverage is complete for the shortlist (Prefect, Hatchet, Temporal, Windmill, n8n); the two major errors were both in the actionable recipe/cost sections and are fixed; remaining uncertainty is confined to vendor-side inconsistencies and unpublished footprint numbers, each marked inline.
