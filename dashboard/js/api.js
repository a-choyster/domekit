/**
 * Backend API fetch wrapper for DomeKit dashboard.
 */

const BASE = '';

async function request(path, params = {}) {
  const url = new URL(path, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== '') url.searchParams.set(k, v);
  }
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

export async function fetchHealth() {
  return request('/v1/domekit/health');
}

export async function fetchLogs({ event, since, until, request_id, limit, offset } = {}) {
  return request('/v1/domekit/audit/logs', { event, since, until, request_id, limit, offset });
}

export async function fetchAuditByRequest(requestId) {
  return request(`/v1/domekit/audit/${requestId}`);
}

export async function fetchSecurityAlerts({ since, limit } = {}) {
  return request('/v1/domekit/security/alerts', { since, limit });
}

export async function fetchMetrics({ since, window } = {}) {
  return request('/v1/domekit/metrics', { since, window });
}

export function streamUrl() {
  return `${window.location.origin}/v1/domekit/audit/stream`;
}
