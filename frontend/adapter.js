// ============================================================================
// VeloRelAI "RPA Order Bot" — API adapter (LIVE MODE)
// ----------------------------------------------------------------------------
// Talks to the FastAPI backend served from the same origin as this file.
// Response shapes match the field names the Component's mock seed data used,
// so the template and renderVals() need no changes beyond Task 12's edits.
// ============================================================================

export const API_BASE = window.location.origin;

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// GET /api/health -> { db_ok, demomart_ok, error? }
export async function getHealth() {
  try {
    return await getJson("/api/health");
  } catch (e) {
    return { db_ok: false, demomart_ok: false, error: e.message || String(e) };
  }
}

// GET /api/inventory -> InventoryItem[] sorted by sku
export function getInventory() {
  return getJson("/api/inventory");
}

// POST /api/inventory/thresholds  body: {sku, reorder_threshold, reorder_qty}[]
export async function saveThresholds(edits) {
  const res = await fetch(`${API_BASE}/api/inventory/thresholds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edits),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// POST /api/runs -> {ok:true, run_id} or {ok:false, reason}
export async function startRun() {
  const res = await fetch(`${API_BASE}/api/runs`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// GET /api/runs -> {id, created_at, status}[] newest first, limit 20
export function listRuns() {
  return getJson("/api/runs");
}

// GET /api/runs/{id} -> {plan_json, summary_json, status, steps} or null
export function getRun(runId) {
  return getJson(`/api/runs/${runId}`);
}

// GET /api/orders -> newest first
export function listOrders() {
  return getJson("/api/orders");
}

// GET /api/screenshots/{run_id}/{filename} -> real PNG
export function getScreenshotUrl(path) {
  return `${API_BASE}/api/screenshots/${path}`;
}

// GET /api/storefront -> {url}
export function getStorefrontInfo() {
  return getJson("/api/storefront");
}

// GET /api/storefront/preview -> {products, total_count}
export function getStorefrontPreview() {
  return getJson("/api/storefront/preview");
}

// GET /api/runs/{id}/stream (SSE) -> events: plan | step | summary | status
export function streamRun(runId, { onPlan, onStep, onSummary, onStatus }) {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/runs/${runId}/stream`, { signal: controller.signal });
      if (!res.ok || !res.body) return;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);

          const eventMatch = /^event:\s*(.+)$/m.exec(frame);
          const dataMatch = /^data:\s*(.+)$/m.exec(frame);
          if (!eventMatch || !dataMatch) continue;

          const eventName = eventMatch[1].trim();
          let data;
          try {
            data = JSON.parse(dataMatch[1]);
          } catch {
            continue;
          }

          if (eventName === "plan") onPlan && onPlan(data);
          else if (eventName === "step") onStep && onStep(data);
          else if (eventName === "summary") onSummary && onSummary(data);
          else if (eventName === "status") onStatus && onStatus(data);
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        onStatus && onStatus({ status: "failed" });
      }
    }
  })();

  return () => controller.abort();
}
