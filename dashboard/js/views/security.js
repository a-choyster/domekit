/**
 * Security / data leakage alerts view.
 */

import { fetchSecurityAlerts } from '../api.js';
import { severityBadge, eventBadge } from '../components/badge.js';
import { formatDateTime, formatJSON } from '../lib/format.js';

let refreshTimer = null;

export function destroy() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
}

export async function render(container) {
  await loadAlerts(container);
  refreshTimer = setInterval(() => loadAlerts(container), 15000);
}

async function loadAlerts(container) {
  try {
    const data = await fetchSecurityAlerts({ limit: 100 });
    const alerts = data.alerts || [];

    if (!alerts.length) {
      container.innerHTML = `
        <div class="card" style="text-align:center;padding:48px">
          <div style="font-size:36px;margin-bottom:12px">&#x2705;</div>
          <h3>No Security Alerts</h3>
          <p class="text-muted" style="margin-top:8px">No suspicious patterns detected in the audit log.</p>
        </div>
        <p class="text-muted" style="font-size:12px;margin-top:16px">Auto-refreshing every 15s</p>
      `;
      return;
    }

    // Summary by type
    const typeCounts = {};
    alerts.forEach(a => { typeCounts[a.type] = (typeCounts[a.type] || 0) + 1; });

    const summaryCards = Object.entries(typeCounts).map(([type, count]) => `
      <div class="card">
        <div class="card-title">${formatAlertType(type)}</div>
        <div class="card-value">${count}</div>
      </div>
    `).join('');

    const alertCards = alerts.map(a => `
      <div class="alert-card severity-${a.severity}">
        <div class="alert-header">
          <div style="display:flex;gap:8px;align-items:center">
            ${severityBadge(a.severity)}
            <span class="alert-type">${formatAlertType(a.type)}</span>
          </div>
          <span class="alert-time">${formatDateTime(a.ts)}</span>
        </div>
        <div class="alert-message">${escapeHtml(a.message)}</div>
        ${a.request_id ? `<div style="margin-top:6px;font-size:12px;color:var(--text-muted)">Request: <code>${a.request_id}</code></div>` : ''}
        <details style="margin-top:8px">
          <summary style="font-size:12px;cursor:pointer;color:var(--text-muted)">Details</summary>
          <pre class="json-detail" style="margin-top:6px">${formatJSON(a.detail)}</pre>
        </details>
      </div>
    `).join('');

    container.innerHTML = `
      <div class="card-grid mb-24">${summaryCards}</div>
      <h3 style="margin-bottom:12px">Recent Alerts</h3>
      ${alertCards}
      <p class="text-muted" style="font-size:12px;margin-top:16px">Auto-refreshing every 15s</p>
    `;
  } catch (err) {
    container.innerHTML = `<p style="color:var(--red)">Error loading alerts: ${err.message}</p>`;
  }
}

function formatAlertType(type) {
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
