/**
 * ai-server external heartbeat / dead-man's-switch.
 *
 * Runs on Cloudflare's edge (Cron Trigger, every 5 min). Polls the server's
 * public /health endpoint; after N consecutive failures it Telegram-DMs an
 * alert, and sends an all-clear when /health recovers. State (consecutive
 * failure count + "already alerted" flag) lives in KV so we alert once per
 * outage, not every tick.
 *
 * Because this executes off the Mac, it fires even when the Mac is asleep/dead
 * or the Cloudflare tunnel is down — the cases where the in-process alerters
 * (server-upkeep, done-DMs) cannot.
 */

export interface Env {
  HEARTBEAT_KV: KVNamespace;
  HEALTH_URL: string;
  FAILURES_BEFORE_ALERT: string;
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
}

const FAIL_KEY = "consecutive_failures";
const ALERTED_KEY = "alerted";

export default {
  async scheduled(_event: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(check(env));
  },

  // Manual trigger for testing: `curl https://<worker-url>/` runs one check.
  async fetch(_req: Request, env: Env): Promise<Response> {
    const result = await check(env);
    return new Response(JSON.stringify(result, null, 2), {
      headers: { "content-type": "application/json" },
    });
  },
};

async function check(env: Env): Promise<{ ok: boolean; detail: string; failures: number }> {
  const threshold = parseInt(env.FAILURES_BEFORE_ALERT || "2", 10);

  let ok = false;
  let detail = "";
  try {
    const resp = await fetch(env.HEALTH_URL, {
      method: "GET",
      signal: AbortSignal.timeout(10_000),
      cf: { cacheTtl: 0 },
    });
    ok = resp.status === 200;
    detail = `HTTP ${resp.status}`;
    if (!ok) {
      const body = await resp.text().catch(() => "");
      if (body) detail += ` — ${body.slice(0, 300)}`;
    }
  } catch (err) {
    ok = false;
    detail = `fetch error: ${err instanceof Error ? err.message : String(err)}`;
  }

  const failures = parseInt((await env.HEARTBEAT_KV.get(FAIL_KEY)) || "0", 10);
  const alerted = (await env.HEARTBEAT_KV.get(ALERTED_KEY)) === "1";

  if (ok) {
    if (alerted) {
      await sendTelegram(env, "✅ ai-server recovered — /health is 200 again.");
    }
    await env.HEARTBEAT_KV.put(FAIL_KEY, "0");
    await env.HEARTBEAT_KV.put(ALERTED_KEY, "0");
    return { ok: true, detail, failures: 0 };
  }

  const newFailures = failures + 1;
  await env.HEARTBEAT_KV.put(FAIL_KEY, String(newFailures));

  if (newFailures >= threshold && !alerted) {
    await sendTelegram(
      env,
      `🚨 ai-server DOWN — ${newFailures} consecutive failed health checks.\n` +
        `${detail}\nURL: ${env.HEALTH_URL}`
    );
    await env.HEARTBEAT_KV.put(ALERTED_KEY, "1");
  }

  return { ok: false, detail, failures: newFailures };
}

async function sendTelegram(env: Env, text: string): Promise<void> {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return;
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text }),
  }).catch(() => {
    /* best-effort; nothing we can do if Telegram is unreachable */
  });
}
