/**
 * Reusable sortable table component.
 */

export function renderTable({ columns, rows, onRowClick }) {
  if (!rows.length) {
    return '<div class="table-wrap"><p style="padding:24px;text-align:center;color:var(--text-muted)">No data</p></div>';
  }

  const ths = columns.map(c =>
    `<th data-col="${c.key}">${c.label}<span class="sort-arrow"></span></th>`
  ).join('');

  const trs = rows.map((row, i) => {
    const tds = columns.map(c => `<td>${c.render ? c.render(row) : (row[c.key] ?? '')}</td>`).join('');
    return `<tr data-idx="${i}" style="cursor:${onRowClick ? 'pointer' : 'default'}">${tds}</tr>`;
  }).join('');

  return `<div class="table-wrap"><table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table></div>`;
}

export function attachTableSort(container, columns, rows, rerender) {
  container.querySelectorAll('th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.col;
      const col = columns.find(c => c.key === key);
      if (!col) return;
      const dir = th.classList.contains('asc') ? -1 : 1;
      container.querySelectorAll('th').forEach(t => t.classList.remove('asc', 'desc'));
      th.classList.add(dir === 1 ? 'asc' : 'desc');
      rows.sort((a, b) => {
        const av = a[key], bv = b[key];
        if (av < bv) return -dir;
        if (av > bv) return dir;
        return 0;
      });
      rerender();
    });
  });
}
