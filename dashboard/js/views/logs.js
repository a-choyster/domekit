/**
 * Log viewer with filters, expandable rows, and live tail.
 */

import { fetchLogs, streamUrl } from '../api.js';
import { eventBadge } from '../components/badge.js';
import { formatDateTime, formatJSON, shortId } from '../lib/format.js';
import { SSEManager } from '../lib/sse.js';
import { renderTimeline } from '../components/timeline.js';

let sse = null;
let liveTail = false;

export function destroy() {
  if (sse) { sse.disconnect(); sse = null; }
}

export async function render(container) {
  const state = { event: '', request_id: '', since: '', limit: 50, offset: 0, entries: [], total: 0 };

  container.innerHTML = buildShell();
  attachEvents(container, state);
  await loadData(container, state);
}

function buildShell() {
  return `
    <div class="filters">
      <select id="f-event">
        <option value="">All events</option>
        <option value="request.start">request.start</option>
        <option value="request.end">request.end</option>
        <option value="tool.call">tool.call</option>
        <option value="tool.result">tool.result</option>
        <option value="policy.block">policy.block</option>
      </select>
      <input id="f-request" type="text" placeholder="Request ID...">
      <input id="f-since" type="datetime-local">
      <button class="btn" id="f-apply">Apply</button>
      <button class="btn" id="f-clear">Clear</button>
      <div style="flex:1"></div>
      <button class="btn" id="live-toggle">
        <span class="live-dot" style="display:none" id="live-dot"></span>
        Live Tail
      </button>
    </div>
    <div id="log-table"></div>
    <div class="pagination" id="log-pagination"></div>
    <div id="timeline-panel" style="margin-top:24px"></div>
  `;
}

function attachEvents(container, state) {
  container.querySelector('#f-apply').addEventListener('click', () => {
    state.event = container.querySelector('#f-event').value;
    state.request_id = container.querySelector('#f-request').value;
    const sinceVal = container.querySelector('#f-since').value;
    state.since = sinceVal ? new Date(sinceVal).toISOString() : '';
    state.offset = 0;
    loadData(container, state);
  });

  container.querySelector('#f-clear').addEventListener('click', () => {
    state.event = ''; state.request_id = ''; state.since = ''; state.offset = 0;
    container.querySelector('#f-event').value = '';
    container.querySelector('#f-request').value = '';
    container.querySelector('#f-since').value = '';
    loadData(container, state);
  });

  container.querySelector('#live-toggle').addEventListener('click', () => {
    liveTail = !liveTail;
    const dot = container.querySelector('#live-dot');
    if (liveTail) {
      dot.style.display = 'inline-block';
      startLiveTail(container, state);
    } else {
      dot.style.display = 'none';
      if (sse) { sse.disconnect(); sse = null; }
    }
  });
}

async function loadData(container, state) {
  try {
    const data = await fetchLogs({
      event: state.event || undefined,
      request_id: state.request_id || undefined,
      since: state.since || undefined,
      limit: state.limit,
      offset: state.offset,
    });
    state.entries = data.entries;
    state.total = data.total;
    renderTable(container, state);
    renderPagination(container, state);
  } catch (err) {
    container.querySelector('#log-table').innerHTML =
      `<p style="color:var(--red)">Error loading logs: ${err.message}</p>`;
  }
}

function renderTable(container, state) {
  const tableDiv = container.querySelector('#log-table');
  if (!state.entries.length) {
    tableDiv.innerHTML = '<div class="table-wrap"><p style="padding:24px;text-align:center;color:var(--text-muted)">No log entries</p></div>';
    return;
  }

  const rows = state.entries.map((e, i) => `
    <tr class="log-row" data-idx="${i}">
      <td class="text-mono" style="font-size:12px">${formatDateTime(e.ts)}</td>
      <td>${eventBadge(e.event)}</td>
      <td><span class="truncate text-mono" style="font-size:12px;cursor:pointer" title="${e.request_id}">${shortId(e.request_id)}</span></td>
      <td>${e.model || '—'}</td>
      <td style="font-size:12px;color:var(--text-secondary)">${summarizeDetail(e.detail)}</td>
    </tr>
    <tr class="row-expand" id="expand-${i}"><td colspan="5"><pre class="json-detail">${formatJSON(e)}</pre></td></tr>
  `).join('');

  tableDiv.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Time</th><th>Event</th><th>Request</th><th>Model</th><th>Detail</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  // Row click → expand
  tableDiv.querySelectorAll('.log-row').forEach(row => {
    row.addEventListener('click', () => {
      const idx = row.dataset.idx;
      const expand = tableDiv.querySelector(`#expand-${idx}`);
      expand.classList.toggle('open');
    });
  });

  // Request ID click → timeline
  tableDiv.querySelectorAll('.truncate').forEach(span => {
    span.addEventListener('click', (ev) => {
      ev.stopPropagation();
      const rid = span.title;
      if (rid) renderTimeline(container.querySelector('#timeline-panel'), rid);
    });
  });
}

function renderPagination(container, state) {
  const pagDiv = container.querySelector('#log-pagination');
  const totalPages = Math.ceil(state.total / state.limit);
  const currentPage = Math.floor(state.offset / state.limit) + 1;

  pagDiv.innerHTML = `
    <span>Showing ${state.offset + 1}–${Math.min(state.offset + state.limit, state.total)} of ${state.total}</span>
    <div class="flex gap-8">
      <button class="btn btn-sm" id="pg-prev" ${currentPage <= 1 ? 'disabled' : ''}>Prev</button>
      <span>Page ${currentPage} / ${totalPages || 1}</span>
      <button class="btn btn-sm" id="pg-next" ${currentPage >= totalPages ? 'disabled' : ''}>Next</button>
    </div>
  `;

  pagDiv.querySelector('#pg-prev')?.addEventListener('click', () => {
    state.offset = Math.max(0, state.offset - state.limit);
    loadData(container, state);
  });
  pagDiv.querySelector('#pg-next')?.addEventListener('click', () => {
    state.offset += state.limit;
    loadData(container, state);
  });
}

function startLiveTail(container, state) {
  sse = new SSEManager(streamUrl(), {
    onMessage(entry) {
      state.entries.unshift(entry);
      if (state.entries.length > 200) state.entries.pop();
      state.total++;
      renderTable(container, state);
    },
  });
  sse.connect();
}

function summarizeDetail(detail) {
  if (!detail || !Object.keys(detail).length) return '—';
  if (detail.tool) return detail.tool;
  if (detail.tools_used?.length) return `tools: ${detail.tools_used.join(', ')}`;
  return Object.keys(detail).join(', ');
}
