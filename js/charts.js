/* ---------- Tiny SVG charts (no deps). Marks follow: thin bars ≤24px, 4px rounded data-end,
   2px lines, ≥8px markers, hairline grid, text in text tokens. ---------- */
import { esc } from './util.js';

const NS = 'http://www.w3.org/2000/svg';

function svgEl(w, h) {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  return svg;
}
function el(tag, attrs = {}, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}
function niceMax(v) {
  if (v <= 5) return 5;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return m * p;
}
function attachTip(wrap, svg, getText) {
  const tip = document.createElement('div');
  tip.className = 'tip'; tip.hidden = true; wrap.appendChild(tip);
  svg.addEventListener('mousemove', (e) => {
    const t = getText(e);
    if (!t) { tip.hidden = true; return; }
    const r = wrap.getBoundingClientRect();
    tip.textContent = t; tip.hidden = false;
    tip.style.left = (e.clientX - r.left) + 'px';
    tip.style.top = (e.clientY - r.top) + 'px';
  });
  svg.addEventListener('mouseleave', () => { tip.hidden = true; });
}

/** Column chart: data = [{label, value, value2?}] — single series (value) with optional faded second series underneath. */
export function columns(container, data, { color = 'var(--s1)', color2 = 'color-mix(in srgb, var(--s1) 30%, transparent)', height = 180, yLabel = '' } = {}) {
  container.innerHTML = '';
  container.classList.add('chart');
  const W = 640, H = height, padL = 32, padR = 8, padT = 12, padB = 26;
  const svg = svgEl(W, H);
  const max = niceMax(Math.max(1, ...data.map(d => Math.max(d.value || 0, d.value2 || 0))));
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const slot = innerW / Math.max(1, data.length);
  const bw = Math.min(24, slot * 0.62);
  // grid: 5 steps so every tick is an integer for max ∈ {5,10,20,50,100,…}
  for (let i = 0; i <= 5; i++) {
    const y = padT + innerH - (innerH * i) / 5;
    svg.appendChild(el('line', { x1: padL, x2: W - padR, y1: y, y2: y, class: 'grid-line' }));
    svg.appendChild(el('text', { x: padL - 6, y: y + 4, 'text-anchor': 'end' }, Math.round((max * i) / 5)));
  }
  const bars = [];
  data.forEach((d, i) => {
    const x = padL + slot * i + (slot - bw) / 2;
    const draw = (v, c) => {
      const h = (innerH * v) / max;
      if (h <= 0) return;
      const y0 = padT + innerH, y = y0 - h;
      const r = Math.min(4, h, bw / 2);
      const path = `M${x},${y0} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${y0} Z`;
      svg.appendChild(el('path', { d: path, fill: c }));
    };
    if (d.value2 != null) draw(d.value2, color2);
    draw(d.value || 0, color);
    bars.push({ x0: padL + slot * i, x1: padL + slot * (i + 1), d });
    if (data.length <= 14 || i % Math.ceil(data.length / 10) === 0)
      svg.appendChild(el('text', { x: x + bw / 2, y: H - 8, 'text-anchor': 'middle' }, d.label));
  });
  container.appendChild(svg);
  attachTip(container, svg, (e) => {
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const b = bars.find(b => px >= b.x0 && px < b.x1);
    return b ? `${b.d.tip || b.d.label}: ${b.d.value}${yLabel}${b.d.value2 != null ? ` / ${b.d.value2}` : ''}` : '';
  });
  return svg;
}

/** Horizontal bars with percentage: data = [{label, pct, n}] */
export function hbars(container, data, { height = null } = {}) {
  container.innerHTML = '';
  container.classList.add('chart');
  const rowH = 30, W = 640, padL = 150, padR = 48;
  const H = height || data.length * rowH + 8;
  const svg = svgEl(W, H);
  const innerW = W - padL - padR;
  data.forEach((d, i) => {
    const y = 6 + i * rowH;
    svg.appendChild(el('text', { x: padL - 10, y: y + 15, 'text-anchor': 'end', class: 'lbl' }, d.label));
    svg.appendChild(el('rect', { x: padL, y: y + 4, width: innerW, height: 14, rx: 4, fill: 'var(--surface-2)' }));
    const w = Math.max(0, (innerW * (d.pct || 0)) / 100);
    const c = d.pct >= 75 ? 'var(--good)' : d.pct >= 55 ? 'var(--warn)' : 'var(--bad)';
    if (w > 0) svg.appendChild(el('rect', { x: padL, y: y + 4, width: w, height: 14, rx: 4, fill: d.n ? c : 'var(--surface-2)' }));
    svg.appendChild(el('text', { x: padL + innerW + 8, y: y + 15, class: 'lbl' }, d.n ? `${d.pct}%` : '–'));
  });
  container.appendChild(svg);
  attachTip(container, svg, (e) => {
    const r = svg.getBoundingClientRect();
    const py = ((e.clientY - r.top) / r.height) * H;
    const i = Math.floor((py - 6) / rowH);
    const d = data[i];
    return d ? `${d.label}: ${d.n ? `${d.pct}% đúng (${d.c}/${d.n})` : 'chưa làm'}` : '';
  });
}

/** Multi-series line chart: series = [{name, color, points:[{x:label, y}]}] (all share x labels) */
export function lines(container, labels, series, { height = 200, yMax = 100, suffix = '%' } = {}) {
  container.innerHTML = '';
  container.classList.add('chart');
  const W = 640, H = height, padL = 36, padR = 12, padT = 12, padB = 26;
  const svg = svgEl(W, H);
  const innerW = W - padL - padR, innerH = H - padT - padB;
  for (let i = 0; i <= 4; i++) {
    const y = padT + innerH - (innerH * i) / 4;
    svg.appendChild(el('line', { x1: padL, x2: W - padR, y1: y, y2: y, class: 'grid-line' }));
    svg.appendChild(el('text', { x: padL - 6, y: y + 4, 'text-anchor': 'end' }, Math.round((yMax * i) / 4) + suffix));
  }
  const xOf = (i) => padL + (labels.length > 1 ? (innerW * i) / (labels.length - 1) : innerW / 2);
  const yOf = (v) => padT + innerH - (innerH * v) / yMax;
  labels.forEach((l, i) => {
    if (labels.length <= 10 || i % Math.ceil(labels.length / 8) === 0 || i === labels.length - 1)
      svg.appendChild(el('text', { x: xOf(i), y: H - 8, 'text-anchor': 'middle' }, l));
  });
  for (const s of series) {
    const pts = s.points.map((p, i) => (p == null ? null : [xOf(i), yOf(p)]));
    let d = '', pen = false;
    pts.forEach(p => { if (!p) { pen = false; return; } d += (pen ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1); pen = true; });
    if (d) svg.appendChild(el('path', { d, fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    pts.forEach(p => {
      if (!p) return;
      svg.appendChild(el('circle', { cx: p[0], cy: p[1], r: 5.5, fill: 'var(--surface)' }));
      svg.appendChild(el('circle', { cx: p[0], cy: p[1], r: 4, fill: s.color }));
    });
  }
  container.appendChild(svg);
  if (series.length > 1) {
    const lg = document.createElement('div'); lg.className = 'legend';
    lg.innerHTML = series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('');
    container.appendChild(lg);
  }
  attachTip(container, svg, (e) => {
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    let best = 0, bd = Infinity;
    labels.forEach((_, i) => { const d = Math.abs(xOf(i) - px); if (d < bd) { bd = d; best = i; } });
    const parts = series.map(s => s.points[best] == null ? null : `${s.name} ${s.points[best]}${suffix}`).filter(Boolean);
    return parts.length ? `${labels[best]} · ${parts.join(' · ')}` : '';
  });
}

/** Score ring */
export function ring(container, pctValue, { size = 110, label = '' } = {}) {
  const r = 46, c = 2 * Math.PI * r;
  const color = pctValue >= 75 ? 'var(--good)' : pctValue >= 55 ? 'var(--warn)' : 'var(--bad)';
  container.innerHTML = `
    <svg class="score-ring" viewBox="0 0 110 110" width="${size}" height="${size}" role="img" aria-label="${esc(label)} ${pctValue}%">
      <circle cx="55" cy="55" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="10"/>
      <circle cx="55" cy="55" r="${r}" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round"
        stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - pctValue / 100)}" transform="rotate(-90 55 55)"/>
      <text x="55" y="60" text-anchor="middle" style="font-size:24px;font-weight:700;fill:var(--text)">${pctValue}%</text>
    </svg>`;
}
