/**
 * Request event timeline — drill into any request_id.
 */

import { fetchAuditByRequest } from '../api.js';
import { eventBadge } from './badge.js';
import { formatTime, formatJSON } from '../lib/format.js';

export async function renderTimeline(container, requestId) {
  container.innerHTML = '<p class="text-muted">Loading timeline...</p>';

  try {
    const entries = await fetchAuditByRequest(requestId);
    if (!entries.length) {
      container.innerHTML = '<p class="text-muted">No events found for this request.</p>';
      return;
    }

    entries.sort((a, b) => new Date(a.ts) - new Date(b.ts));

    const html = `
      <div style="margin-bottom:12px">
        <strong>Request:</strong> <code class="text-mono">${requestId}</code>
        <span class="text-muted" style="margin-left:12px">${entries.length} events</span>
      </div>
      <div class="timeline">
        ${entries.map(e => `
          <div class="timeline-event">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">
                ${eventBadge(e.event)}
                <span class="text-mono" style="font-size:12px">${formatTime(e.ts)}</span>
              </div>
              ${Object.keys(e.detail || {}).length ? `<pre class="json-detail">${formatJSON(e.detail)}</pre>` : ''}
            </div>
          </div>
        `).join('')}
      </div>
      <style>
        .timeline { position: relative; padding-left: 24px; }
        .timeline::before {
          content: ''; position: absolute; left: 8px; top: 0; bottom: 0;
          width: 2px; background: var(--border);
        }
        .timeline-event { position: relative; margin-bottom: 16px; }
        .timeline-dot {
          position: absolute; left: -20px; top: 6px;
          width: 10px; height: 10px; border-radius: 50%;
          background: var(--accent); border: 2px solid var(--bg-secondary);
        }
        .timeline-content { padding-left: 4px; }
      </style>
    `;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<p style="color:var(--red)">Error: ${err.message}</p>`;
  }
}
