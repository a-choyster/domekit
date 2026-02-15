/**
 * Reusable status card component.
 */

export function statusCard({ title, value, status, subtitle }) {
  const statusCls = status === 'ok' ? 'status-ok' : status === 'warn' ? 'status-warn' : status === 'error' ? 'status-error' : '';
  return `
    <div class="card ${statusCls}">
      <div class="card-title">${title}</div>
      <div class="card-value">${value}</div>
      ${subtitle ? `<div class="text-muted" style="font-size:12px;margin-top:4px">${subtitle}</div>` : ''}
    </div>`;
}
