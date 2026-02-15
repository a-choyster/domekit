/**
 * Canvas-based chart rendering (line + bar).
 */

const COLORS = {
  line: '#6c8cff',
  bar: '#6c8cff',
  barAlt: '#c084fc',
  grid: 'rgba(100,110,140,0.15)',
  text: '#9499a8',
};

export function lineChart(canvasId, { labels, data, title, yLabel }) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;

  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = 200 * dpr;
  canvas.style.height = '200px';
  ctx.scale(dpr, dpr);

  const w = rect.width, h = 200;
  const pad = { top: 20, right: 20, bottom: 30, left: 50 };
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  ctx.clearRect(0, 0, w, h);

  if (!data.length) {
    ctx.fillStyle = COLORS.text;
    ctx.font = '13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No data', w / 2, h / 2);
    return;
  }

  const maxVal = Math.max(...data, 1);
  const yScale = plotH / maxVal;
  const xStep = data.length > 1 ? plotW / (data.length - 1) : plotW;

  // Grid lines
  ctx.strokeStyle = COLORS.grid;
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w - pad.right, y); ctx.stroke();
    ctx.fillStyle = COLORS.text;
    ctx.font = '11px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(maxVal - (maxVal / 4) * i), pad.left - 6, y + 4);
  }

  // Line
  ctx.strokeStyle = COLORS.line;
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = pad.left + i * xStep;
    const y = pad.top + plotH - v * yScale;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Fill area
  ctx.globalAlpha = 0.1;
  ctx.fillStyle = COLORS.line;
  ctx.lineTo(pad.left + (data.length - 1) * xStep, pad.top + plotH);
  ctx.lineTo(pad.left, pad.top + plotH);
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;

  // X labels (show a few)
  if (labels.length) {
    ctx.fillStyle = COLORS.text;
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(labels.length / 6));
    for (let i = 0; i < labels.length; i += step) {
      const x = pad.left + i * xStep;
      ctx.fillText(labels[i], x, h - 8);
    }
  }
}

export function barChart(canvasId, { labels, data, colors, title }) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;

  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = 200 * dpr;
  canvas.style.height = '200px';
  ctx.scale(dpr, dpr);

  const w = rect.width, h = 200;
  const pad = { top: 20, right: 20, bottom: 40, left: 50 };
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  ctx.clearRect(0, 0, w, h);

  if (!data.length) {
    ctx.fillStyle = COLORS.text;
    ctx.font = '13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No data', w / 2, h / 2);
    return;
  }

  const maxVal = Math.max(...data, 1);
  const barW = Math.min(40, (plotW / data.length) * 0.7);
  const gap = (plotW - barW * data.length) / (data.length + 1);

  // Grid
  ctx.strokeStyle = COLORS.grid;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w - pad.right, y); ctx.stroke();
    ctx.fillStyle = COLORS.text;
    ctx.font = '11px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(maxVal - (maxVal / 4) * i), pad.left - 6, y + 4);
  }

  // Bars
  data.forEach((v, i) => {
    const x = pad.left + gap + i * (barW + gap);
    const barH = (v / maxVal) * plotH;
    const y = pad.top + plotH - barH;
    ctx.fillStyle = colors?.[i] || COLORS.bar;
    ctx.fillRect(x, y, barW, barH);

    // Label
    ctx.fillStyle = COLORS.text;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.save();
    ctx.translate(x + barW / 2, h - 6);
    ctx.rotate(-0.4);
    ctx.fillText(labels[i] || '', 0, 0);
    ctx.restore();
  });
}
