/**
 * Color-coded event type badges.
 */

const EVENT_STYLES = {
  'request.start': { cls: 'badge-blue', label: 'REQ START' },
  'request.end':   { cls: 'badge-green', label: 'REQ END' },
  'tool.call':     { cls: 'badge-purple', label: 'TOOL CALL' },
  'tool.result':   { cls: 'badge-purple', label: 'TOOL RESULT' },
  'policy.block':  { cls: 'badge-red', label: 'BLOCKED' },
};

const SEVERITY_STYLES = {
  critical: 'badge-red',
  high: 'badge-orange',
  medium: 'badge-yellow',
  low: 'badge-green',
};

export function eventBadge(eventType) {
  const style = EVENT_STYLES[eventType] || { cls: 'badge-blue', label: eventType };
  return `<span class="badge ${style.cls}">${style.label}</span>`;
}

export function severityBadge(severity) {
  const cls = SEVERITY_STYLES[severity] || 'badge-blue';
  return `<span class="badge ${cls}">${severity.toUpperCase()}</span>`;
}
