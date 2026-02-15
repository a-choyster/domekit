/**
 * DomeKit Dashboard — hash-based router and init.
 */

import { fetchHealth } from './api.js';

const VIEWS = {
  logs:     () => import('./views/logs.js'),
  health:   () => import('./views/health.js'),
  security: () => import('./views/security.js'),
  metrics:  () => import('./views/metrics.js'),
};

const VIEW_TITLES = {
  logs: 'Audit Logs',
  health: 'Health Status',
  security: 'Security Alerts',
  metrics: 'Metrics',
};

let currentView = null;
let currentModule = null;

async function navigate(viewName) {
  if (!VIEWS[viewName]) viewName = 'logs';
  if (viewName === currentView) return;

  // Destroy previous view
  if (currentModule?.destroy) currentModule.destroy();

  currentView = viewName;

  // Update nav
  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.toggle('active', link.dataset.view === viewName);
  });
  document.getElementById('view-title').textContent = VIEW_TITLES[viewName] || viewName;

  // Load and render
  const container = document.getElementById('content');
  container.innerHTML = '<p class="text-muted">Loading...</p>';

  try {
    currentModule = await VIEWS[viewName]();
    await currentModule.render(container);
  } catch (err) {
    container.innerHTML = `<p style="color:var(--red)">Failed to load view: ${err.message}</p>`;
  }
}

function getHashView() {
  const hash = window.location.hash.replace('#/', '').replace('#', '');
  return hash || 'logs';
}

// Health indicator polling
async function pollHealth() {
  const dot = document.getElementById('health-indicator');
  const label = document.getElementById('health-label');
  try {
    const h = await fetchHealth();
    dot.className = 'health-dot ok';
    label.textContent = `Online — ${h.manifest?.app || 'DomeKit'}`;
  } catch {
    dot.className = 'health-dot error';
    label.textContent = 'Offline';
  }
}

// Theme toggle
function initTheme() {
  const saved = localStorage.getItem('domekit-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);

  document.getElementById('theme-toggle').addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next === 'dark' ? '' : next);
    if (next === 'dark') {
      document.documentElement.removeAttribute('data-theme');
      localStorage.removeItem('domekit-theme');
    } else {
      localStorage.setItem('domekit-theme', next);
    }
  });
}

// Init
window.addEventListener('hashchange', () => navigate(getHashView()));

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  navigate(getHashView());
  pollHealth();
  setInterval(pollHealth, 30000);
});
