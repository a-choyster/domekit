/**
 * Metrics view — throughput, tool usage, latency, summary.
 */

import { fetchMetrics } from '../api.js';
import { statusCard } from '../components/card.js';
import { lineChart, barChart } from '../components/chart.js';
import { formatDuration, formatNumber, formatTime } from '../lib/format.js';

let refreshTimer = null;

export function destroy() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
}

export async function render(container) {
  await loadMetrics(container);
  refreshTimer = setInterval(() => loadMetrics(container), 15000);
}

async function loadMetrics(container) {
  try {
    const m = await fetchMetrics({ window: 60 });

    const summary = m.summary || {};
    const latency = m.latency || {};
    const errors = m.error_rates || {};

    const cards = [
      statusCard({
        title: 'Total Requests',
        value: formatNumber(errors.total_requests || 0),
        status: 'ok',
      }),
      statusCard({
        title: 'Tool Calls',
        value: formatNumber(errors.tool_calls || 0),
        status: 'ok',
      }),
      statusCard({
        title: 'Policy Blocks',
        value: formatNumber(errors.policy_blocks || 0),
        status: errors.policy_blocks > 0 ? 'warn' : 'ok',
        subtitle: `Block rate: ${((errors.block_rate || 0) * 100).toFixed(1)}%`,
      }),
      statusCard({
        title: 'Latency (p50 / p95)',
        value: `${formatDuration(latency.p50)} / ${formatDuration(latency.p95)}`,
        status: 'ok',
        subtitle: `p99: ${formatDuration(latency.p99)} — ${latency.count || 0} samples`,
      }),
    ];

    container.innerHTML = `
      <div class="card-grid">${cards.join('')}</div>

      <div class="chart-container">
        <div class="chart-title">Request Throughput (per minute)</div>
        <canvas id="throughput-chart"></canvas>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px" class="mb-24">
        <div class="chart-container">
          <div class="chart-title">Tool Usage</div>
          <canvas id="tool-chart"></canvas>
        </div>
        <div class="chart-container">
          <div class="chart-title">Latency Percentiles (seconds)</div>
          <canvas id="latency-chart"></canvas>
        </div>
      </div>

      ${summary.event_counts ? `
        <div class="card">
          <div class="card-title">Event Breakdown</div>
          <table style="font-size:13px">
            ${Object.entries(summary.event_counts).map(([ev, count]) => `
              <tr>
                <td style="padding:4px 16px 4px 0;color:var(--text-muted)">${ev}</td>
                <td class="text-mono">${formatNumber(count)}</td>
              </tr>
            `).join('')}
          </table>
        </div>
      ` : ''}

      <p class="text-muted" style="font-size:12px;margin-top:16px">Auto-refreshing every 15s</p>
    `;

    // Render charts after DOM is updated
    requestAnimationFrame(() => {
      const tp = m.throughput || [];
      lineChart('throughput-chart', {
        labels: tp.map(b => formatTime(b.time)),
        data: tp.map(b => b.count),
      });

      const tools = m.tool_usage || [];
      barChart('tool-chart', {
        labels: tools.map(t => t.tool),
        data: tools.map(t => t.count),
      });

      barChart('latency-chart', {
        labels: ['p50', 'p95', 'p99'],
        data: [latency.p50 || 0, latency.p95 || 0, latency.p99 || 0],
        colors: ['#6c8cff', '#facc15', '#f87171'],
      });
    });
  } catch (err) {
    container.innerHTML = `<p style="color:var(--red)">Error loading metrics: ${err.message}</p>`;
  }
}
