/**
 * Health status view — runtime, Ollama, model status cards.
 */

import { fetchHealth } from '../api.js';
import { statusCard } from '../components/card.js';
import { formatUptime, formatNumber } from '../lib/format.js';

let refreshTimer = null;

export function destroy() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
}

export async function render(container) {
  await loadHealth(container);
  refreshTimer = setInterval(() => loadHealth(container), 10000);
}

async function loadHealth(container) {
  try {
    const h = await fetchHealth();

    const cards = [
      statusCard({
        title: 'Runtime',
        value: h.status === 'ok' ? 'Online' : 'Error',
        status: h.status === 'ok' ? 'ok' : 'error',
        subtitle: `v${h.version} — up ${formatUptime(h.uptime_seconds)}`,
      }),
      statusCard({
        title: 'Ollama',
        value: h.ollama?.reachable ? 'Connected' : 'Offline',
        status: h.ollama?.reachable ? 'ok' : 'error',
        subtitle: h.ollama?.models?.length
          ? `${h.ollama.models.length} model(s): ${h.ollama.models.slice(0, 3).join(', ')}`
          : 'No models loaded',
      }),
      statusCard({
        title: 'Default Model',
        value: h.manifest?.default_model || '—',
        status: 'ok',
        subtitle: `Backend: ${h.manifest?.model_backend || '—'}`,
      }),
      statusCard({
        title: 'Audit Log',
        value: formatNumber(h.audit_log_entries ?? 0),
        status: 'ok',
        subtitle: h.audit_log_size_bytes != null
          ? `${(h.audit_log_size_bytes / 1024).toFixed(1)} KB`
          : '—',
      }),
    ];

    const manifest = h.manifest;
    const policyHtml = manifest ? `
      <div class="card mb-16">
        <div class="card-title">Policy Summary</div>
        <table style="font-size:13px">
          <tr><td style="padding:4px 12px 4px 0;color:var(--text-muted)">App</td><td>${manifest.app} v${manifest.app_version}</td></tr>
          <tr><td style="padding:4px 12px 4px 0;color:var(--text-muted)">Mode</td><td><span class="badge badge-blue">${manifest.policy_mode}</span></td></tr>
          <tr><td style="padding:4px 12px 4px 0;color:var(--text-muted)">Allowed Tools</td><td>${manifest.allowed_tools?.join(', ') || 'none'}</td></tr>
        </table>
      </div>` : '';

    container.innerHTML = `
      <div class="card-grid">${cards.join('')}</div>
      ${policyHtml}
      <p class="text-muted" style="font-size:12px">Auto-refreshing every 10s</p>
    `;
  } catch (err) {
    container.innerHTML = `
      <div class="card-grid">
        ${statusCard({ title: 'Runtime', value: 'Unreachable', status: 'error', subtitle: err.message })}
      </div>`;
  }
}
