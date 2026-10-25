/* ---------- Ngữ pháp: danh mục mẫu, chi tiết, học thẻ (nhớ / quên + lặp lại ngắt quãng) ---------- */
import { $, $$, esc, escText, pct, relDay, shuffle, debounce, normJa, toast, confirmDialog } from '../util.js';
import * as store from '../store.js';
import { loadGrammar, getQ } from '../data.js';
import { boxLabel } from '../srs.js';
import { navigate } from '../app.js';

export async function render(app, route) {
  const G = await loadGrammar();
  if (!G.points.length) {
    app.innerHTML = '<div class="card"><h1>Ngữ pháp</h1><p class="empty">Chưa có dữ liệu mẫu ngữ pháp (<code>data/grammar.json</code>). Chạy <code>python -I scripts/build_grammar.py</code>.</p></div>';
    return;
  }
  if (route.segs[0] === 'p' && route.segs[1]) return detailPage(app, G, decodeURIComponent(route.segs[1]), route.params);
  if (route.segs[0] === 'study') return studyPage(app, G, route.params);
  return homePage(app, G, route.params);
}

/* ---------- trạng thái thẻ ---------- */
const NEW = 'new', LEARNING = 'learning', KNOWN = 'known';
function statusOf(pid) {
  const c = store.gcardOf(pid);
  if (!c) return NEW;
  return c.box >= 4 ? KNOWN : LEARNING;
}
const STATUS_LABEL = { [NEW]: 'Chưa học', [LEARNING]: 'Đang học', [KNOWN]: 'Gần thuộc' };
const STATUS_CLASS = { [NEW]: '', [LEARNING]: 'warn', [KNOWN]: 'good' };
const statusPill = (pid) => { const s = statusOf(pid); return `<span class="pill ${STATUS_CLASS[s]}">${STATUS_LABEL[s]}</span>`; };
const isDue = (pid) => { const c = store.gcardOf(pid); return !!c && c.due <= Date.now(); };

function counts(G) {
  const c = { all: G.points.length, [NEW]: 0, [LEARNING]: 0, [KNOWN]: 0, due: 0, lapsed: 0 };
  for (const p of G.points) {
    c[statusOf(p.id)]++;
    const card = store.gcardOf(p.id);
    if (card && card.due <= Date.now()) c.due++;
    if (card && card.lapses > 0 && card.box < 4) c.lapsed++;
  }
  return c;
}

/** Danh sách mã mẫu cho từng bộ thẻ. */
function deck(G, mode, { group = '', limit = 0 } = {}) {
  let pts = G.points.filter(p => !group || p.group === group);
  const card = (p) => store.gcardOf(p.id);
  if (mode === 'due') pts = pts.filter(p => card(p) && card(p).due <= Date.now()).sort((a, b) => card(a).due - card(b).due);
  else if (mode === 'new') pts = pts.filter(p => !card(p)).sort((a, b) => b.n - a.n); // hay ra đề trước
  else if (mode === 'weak') pts = pts.filter(p => card(p) && card(p).lapses > 0 && card(p).box < 4).sort((a, b) => card(b).lapses - card(a).lapses);
  else pts = shuffle(pts);
  if (limit) pts = pts.slice(0, limit);
  return pts.map(p => p.id);
}

/* ---------- trang chính ---------- */
function homePage(app, G, params) {
  let tab = params.tab || 'cards';
  let query = params.q || '';
  let group = params.g || '';
  let filter = params.f || '';
  let limit = 60;
  let front = localStorageGet('gr-front') || 'pattern';

  const draw = () => {
    const c = counts(G);
    const groups = G.groups && G.groups.length ? G.groups : [...new Set(G.points.map(p => p.group))].sort();
    app.innerHTML = `
      <div class="row between">
        <div><h1 style="margin-bottom:.1em">Ngữ pháp</h1><p class="muted" style="margin:0">${G.points.length} mẫu gom từ ${G.questions?.toLocaleString('vi') ?? 'các'} câu trong ngân hàng. Học thẻ: quên thì lặp lại ngắt quãng 1 → 3 → 7 → 14 → 30 → 60 ngày.</p></div>
      </div>
      <div class="grid-tiles mt">
        <div class="tile"><div class="label">Đến hạn ôn</div><div class="value" style="color:${c.due ? 'var(--bad)' : 'inherit'}">${c.due}</div></div>
        <div class="tile"><div class="label">Chưa học</div><div class="value">${c[NEW]}</div></div>
        <div class="tile"><div class="label">Đang học</div><div class="value">${c[LEARNING]}</div><div class="sub">hay quên: ${c.lapsed}</div></div>
        <div class="tile"><div class="label">Gần thuộc (≥ 1 tháng)</div><div class="value">${c[KNOWN]}</div><div class="progress-line mt"><i style="width:${pct(c[KNOWN], c.all)}%"></i></div></div>
      </div>
      <div class="tabs mt">
        <button class="${tab === 'cards' ? 'active' : ''}" data-tab="cards">Học thẻ</button>
        <button class="${tab === 'list' ? 'active' : ''}" data-tab="list">Danh sách mẫu (${G.points.length})</button>
      </div>
      <div id="body"></div>`;
    $$('[data-tab]', app).forEach(b => b.onclick = () => { tab = b.dataset.tab; limit = 60; draw(); });
    if (tab === 'cards') cardsTab(c, groups); else listTab(groups);
  };

  /* --- tab học thẻ --- */
  const cardsTab = (c, groups) => {
    const body = $('#body', app);
    body.innerHTML = `
      <div class="card">
        <div class="row between"><h3 style="margin:0">Chọn bộ thẻ</h3>
          <div class="row"><span class="small muted">Mặt trước:</span>
            <div class="seg"><button data-front="pattern" class="${front === 'pattern' ? 'active' : ''}">Mẫu ngữ pháp</button><button data-front="meaning" class="${front === 'meaning' ? 'active' : ''}">Ý nghĩa</button></div></div></div>
        <p class="small muted">Lật thẻ rồi chọn <b>Nhớ</b> hoặc <b>Quên</b>. Thẻ quên sẽ quay lại ngay trong phiên này và hẹn ôn lại vào ngày mai; thẻ nhớ được giãn dần ra.</p>
        <div class="row">
          <button class="btn btn-primary btn-lg" data-deck="due" ${c.due ? '' : 'disabled'}>Ôn đến hạn (${c.due})</button>
          <button class="btn btn-lg" data-deck="new" data-n="10" ${c[NEW] ? '' : 'disabled'}>Học 10 mẫu mới</button>
          <button class="btn btn-lg" data-deck="new" data-n="20" ${c[NEW] ? '' : 'disabled'}>20 mẫu mới</button>
          <button class="btn btn-lg" data-deck="weak" ${c.lapsed ? '' : 'disabled'}>Hay quên (${c.lapsed})</button>
          <button class="btn btn-lg" data-deck="all" data-n="20">Ngẫu nhiên 20 thẻ</button>
        </div>
        <div class="row mt">
          <span class="small muted">Hoặc theo nhóm:</span>
          <select class="input" id="grp" style="max-width:260px"><option value="">Tất cả nhóm</option>${groups.map(g => `<option ${g === group ? 'selected' : ''}>${esc(g)}</option>`).join('')}</select>
          <button class="btn" id="grp-go">Học nhóm này</button>
        </div>
      </div>`;
    $$('[data-front]', body).forEach(b => b.onclick = () => { front = b.dataset.front; localStorageSet('gr-front', front); cardsTab(c, groups); });
    $$('[data-deck]', body).forEach(b => b.onclick = () => start(b.dataset.deck, +b.dataset.n || 0, group));
    $('#grp', body).onchange = (e) => { group = e.target.value; };
    $('#grp-go', body).onclick = () => start('all', 0, group);
  };
  const start = (mode, n, grp) => {
    const ids = deck(G, mode, { group: grp, limit: n });
    if (!ids.length) { toast('Bộ thẻ này đang trống'); return; }
    sessionStorageSet('gr-deck', JSON.stringify({ ids, front, title: deckTitle(mode, grp) }));
    navigate('#/grammar/study');
  };

  /* --- tab danh sách --- */
  const listTab = (groups) => {
    const body = $('#body', app);
    body.innerHTML = `
      <div class="search-bar">
        <input class="input" id="q" type="search" placeholder="Tìm mẫu hoặc nghĩa, ví dụ: ばかり, chỉ toàn" value="${esc(query)}">
        <select class="input" id="g" style="max-width:220px"><option value="">Mọi nhóm</option>${groups.map(g => `<option ${g === group ? 'selected' : ''}>${esc(g)}</option>`).join('')}</select>
        <select class="input" id="f" style="max-width:160px">${[['', 'Mọi trạng thái'], ['due', 'Đến hạn'], [NEW, 'Chưa học'], [LEARNING, 'Đang học'], [KNOWN, 'Gần thuộc']].map(([v, l]) => `<option value="${v}" ${v === filter ? 'selected' : ''}>${l}</option>`).join('')}</select>
        <span class="small muted" id="cnt" style="align-self:center"></span>
      </div>
      <div class="ref-list" id="list"></div><div id="more-wrap"></div>`;
    const paint = () => {
      const list = filterPoints(G.points, { query, group, filter });
      $('#cnt', body).textContent = `${list.length} mẫu`;
      $('#list', body).innerHTML = list.slice(0, limit).map(p => `
        <a class="ref-card" href="#/grammar/p/${encodeURIComponent(p.id)}" style="color:inherit;text-decoration:none">
          <span class="ref-ja">${esc(p.pattern)}</span>
          <span>${esc(p.meaning_vi)} ${statusPill(p.id)}${isDue(p.id) ? ' <span class="pill bad">đến hạn</span>' : ''}</span>
          <div class="meta small"><span class="ja">${esc(p.formula || '')}</span> <span class="muted">· ${esc(p.group || '')} · ${p.n} câu</span></div>
        </a>`).join('') || '<p class="empty">Không có mẫu nào khớp.</p>';
      $('#more-wrap', body).innerHTML = list.length > limit ? `<button class="btn mt" id="more">Xem thêm (${list.length - limit})</button>` : '';
      $('#more', body)?.addEventListener('click', () => { limit += 100; paint(); });
    };
    paint();
    $('#q', body).oninput = debounce((e) => { query = e.target.value; limit = 60; paint(); }, 150);
    $('#g', body).onchange = (e) => { group = e.target.value; limit = 60; paint(); };
    $('#f', body).onchange = (e) => { filter = e.target.value; limit = 60; paint(); };
  };
  draw();
}

function deckTitle(mode, grp) {
  const base = { due: 'Ôn đến hạn', new: 'Mẫu mới', weak: 'Hay quên', all: 'Ngẫu nhiên' }[mode] || 'Thẻ ngữ pháp';
  return grp ? `${grp}` : base;
}

function filterPoints(points, { query, group, filter }) {
  const n = normJa(query || ''), raw = (query || '').trim().toLowerCase();
  return points.filter(p => {
    if (group && p.group !== group) return false;
    if (filter === 'due' ? !isDue(p.id) : filter && statusOf(p.id) !== filter) return false;
    if (!raw) return true;
    return normJa(p.pattern).includes(n) || (p.reading || '').includes(raw) || (p.meaning_vi || '').toLowerCase().includes(raw) || (p.formula || '').toLowerCase().includes(raw);
  });
}

/* ---------- ví dụ & chi tiết ---------- */
const exHTML = (ex, max = 6) => (ex || []).slice(0, max).map(e => `
  <div class="gr-ex"><div class="ja">${esc(e.ja)}</div>${e.vi ? `<div class="small muted">${esc(e.vi)}</div>` : ''}</div>`).join('');

function bodyHTML(p, G, { examples = 6 } = {}) {
  return `
    <div class="gr-sec"><div class="gr-label">Công thức</div><div class="ja gr-formula">${esc(p.formula || '—')}</div></div>
    <div class="gr-sec"><div class="gr-label">Ý nghĩa</div><div><b>${esc(p.meaning_vi)}</b></div></div>
    ${p.explain_vi ? `<div class="gr-sec"><div class="gr-label">Giải thích</div><div>${escText(p.explain_vi)}</div></div>` : ''}
    <div class="gr-sec"><div class="gr-label">Ví dụ (từ đề thi)</div>${exHTML(p.ex, examples) || '<span class="muted">—</span>'}</div>
    ${(p.confusable || []).filter(id => G.byId.has(id)).length ? `<div class="gr-sec"><div class="gr-label">Dễ nhầm với</div>${p.confusable.filter(id => G.byId.has(id)).map(id => `<a class="pill" href="#/grammar/p/${encodeURIComponent(id)}">${esc(G.byId.get(id).pattern)}</a>`).join(' ')}</div>` : ''}`;
}

function detailPage(app, G, pid, params) {
  const p = G.byId.get(pid);
  if (!p) { app.innerHTML = `<div class="card"><p>Không tìm thấy mẫu này. <a href="#/grammar?tab=list">Về danh sách</a></p></div>`; return; }
  const draw = () => {
    const c = store.gcardOf(pid);
    const qs = p.qids.filter(id => getQ(id));
    app.innerHTML = `
      <p class="small"><a href="#/grammar?tab=list">← Danh sách mẫu ngữ pháp</a></p>
      <div class="card">
        <div class="row between"><div>
          <h1 class="ja" style="margin:0">${esc(p.pattern)}</h1>
          ${p.reading ? `<div class="muted ja">${esc(p.reading)}</div>` : ''}
          <div style="margin-top:.4rem"><span class="pill bunpo">${esc(p.group || '')}</span> ${statusPill(pid)} <span class="small muted">gặp trong ${p.n} câu</span></div></div>
          <div class="row">${c ? `<span class="small muted">${esc(boxLabel(c.box))} · ôn ${esc(relDay(c.due))}${c.lapses ? ` · quên ${c.lapses} lần` : ''}</span>` : ''}
            <button class="btn btn-primary" id="study">Học thẻ này</button>
            ${c ? '<button class="btn btn-ghost btn-sm" id="reset" title="Đưa về chưa học">Đặt lại</button>' : ''}</div></div>
        <div class="mt">${bodyHTML(p, G, { examples: 12 })}</div>
      </div>
      <div class="card mt"><h3 style="margin-top:0">Câu hỏi dùng mẫu này (${qs.length})</h3>
        <p class="small muted">Bấm một câu để làm lại và xem chữa bài.</p>
        ${qs.slice(0, 15).map(id => `<div><a class="ja" href="#/review/run?only=${encodeURIComponent(id)}">${esc(trunc(getQ(id).question, 70))}</a></div>`).join('')}
        ${qs.length > 15 ? `<p class="small muted">… và ${qs.length - 15} câu khác.</p>` : ''}
      </div>`;
    $('#study', app).onclick = () => {
      sessionStorageSet('gr-deck', JSON.stringify({ ids: [pid], front: 'pattern', title: p.pattern }));
      navigate('#/grammar/study');
    };
    $('#reset', app)?.addEventListener('click', async () => {
      if (await confirmDialog({ title: 'Đặt lại mẫu này về chưa học?', body: 'Lịch ôn của thẻ sẽ bị xoá.', ok: 'Đặt lại', danger: true })) {
        store.resetGrammar(pid); document.dispatchEvent(new CustomEvent('gcards-changed')); draw();
      }
    });
  };
  draw();
}
const trunc = (s, n) => { const t = (s || '').replace(/\s+/g, ' '); return t.length > n ? t.slice(0, n) + '…' : t; };

/* ---------- học thẻ ---------- */
function studyPage(app, G, params) {
  let cfg = null;
  try { cfg = JSON.parse(sessionStorage.getItem('gr-deck') || 'null'); } catch { /* ignore */ }
  if (!cfg || !cfg.ids?.length) { navigate('#/grammar'); return; }
  const total = cfg.ids.filter(id => G.byId.has(id));
  if (!total.length) { navigate('#/grammar'); return; }

  const queue = total.slice();
  const failed = new Set();   // quên ít nhất 1 lần trong phiên
  const settled = new Set();  // đã nhớ xong trong phiên
  let flipped = false, again = 0, good = 0;
  const front = cfg.front || 'pattern';

  const draw = () => {
    if (!queue.length) return summary();
    const p = G.byId.get(queue[0]);
    const c = store.gcardOf(p.id);
    app.innerHTML = `
      <div class="test-bar">
        <div><div class="small muted">Học thẻ · ${esc(cfg.title || '')}</div><b>${settled.size} / ${total.length}</b> <span class="small muted">· còn ${queue.length} lượt · quên ${again}</span></div>
        <div class="row"><a class="btn btn-sm" href="#/grammar">Dừng</a></div>
        <div class="progress-line"><i style="width:${pct(settled.size, total.length)}%"></i></div>
      </div>
      <div class="card gr-card" id="flash" tabindex="0" role="button" aria-label="Lật thẻ">
        ${!flipped ? `
          <div class="small muted" style="text-align:center">${esc(p.group || '')} · ${c ? esc(boxLabel(c.box)) : 'Mới'}${failed.has(p.id) ? ' · vừa quên' : ''}</div>
          <div class="gr-front ja">${front === 'pattern' ? esc(p.pattern) : esc(p.meaning_vi)}</div>
          ${front === 'pattern' && p.reading ? `<div class="muted ja" style="text-align:center">${esc(p.reading)}</div>` : ''}
          <p class="small muted" style="text-align:center;margin-top:1.5rem">Nhớ ý nghĩa, công thức và một ví dụ, rồi bấm để lật (Space)</p>`
        : `
          <div class="gr-back-head"><span class="ja gr-pattern">${esc(p.pattern)}</span> ${p.reading ? `<span class="muted ja">${esc(p.reading)}</span>` : ''}</div>
          ${bodyHTML(p, G, { examples: 3 })}
          <p class="small" style="margin-top:.75rem"><a href="#/grammar/p/${encodeURIComponent(p.id)}" target="_blank" rel="noopener">Xem đầy đủ ↗</a></p>`}
      </div>
      <div class="row mt gr-actions" ${flipped ? '' : 'hidden'} style="justify-content:center">
        <button class="btn btn-danger btn-lg" data-g="again">✗ Quên <span class="small muted">(←)</span></button>
        <button class="btn btn-primary btn-lg" data-g="good">✓ Nhớ <span class="small muted">(→)</span></button>
      </div>
      ${flipped ? '' : '<div class="row mt" style="justify-content:center"><button class="btn btn-lg" id="flip">Lật thẻ</button></div>'}`;
    $('#flash', app).onclick = (e) => { if (!flipped && !e.target.closest('a')) { flipped = true; draw(); } };
    $('#flip', app)?.addEventListener('click', () => { flipped = true; draw(); });
    $$('[data-g]', app).forEach(b => b.onclick = () => grade(b.dataset.g));
  };

  const grade = (g) => {
    if (!flipped) return;
    const pid = queue.shift();
    if (g === 'again') {
      if (!failed.has(pid)) store.gradeGrammar(pid, 'again'); // chỉ ghi lịch ở lần quên đầu tiên của phiên
      failed.add(pid); again++;
      queue.splice(Math.min(queue.length, 3), 0, pid);       // quay lại sau vài thẻ
    } else {
      if (!failed.has(pid)) { store.gradeGrammar(pid, 'good'); good++; }
      settled.add(pid);
    }
    document.dispatchEvent(new CustomEvent('gcards-changed'));
    flipped = false;
    draw();
  };

  const summary = () => {
    const weak = [...failed];
    app.innerHTML = `
      <div class="card" style="text-align:center">
        <h2>Xong bộ thẻ 🎉</h2>
        <p>${total.length} mẫu · nhớ ngay <b>${good}</b> · quên <b>${weak.length}</b> (ôn lại ngày mai)</p>
        ${weak.length ? `<div class="mt" style="text-align:left"><b>Các mẫu đã quên:</b>${weak.map(id => `<div><a class="ja" href="#/grammar/p/${encodeURIComponent(id)}">${esc(G.byId.get(id).pattern)}</a> <span class="muted small">${esc(G.byId.get(id).meaning_vi)}</span></div>`).join('')}</div>` : ''}
        <div class="row mt" style="justify-content:center"><a class="btn btn-primary" href="#/grammar">Về Ngữ pháp</a></div>
      </div>`;
  };

  const onKey = (e) => {
    if (e.target.matches('input,textarea,select')) return;
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); if (!flipped && queue.length) { flipped = true; draw(); } }
    else if (e.key === 'ArrowLeft' || e.key === '1') grade('again');
    else if (e.key === 'ArrowRight' || e.key === '2') grade('good');
  };
  document.addEventListener('keydown', onKey);
  draw();
  return () => document.removeEventListener('keydown', onKey);
}

function localStorageGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function localStorageSet(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }
function sessionStorageSet(k, v) { try { sessionStorage.setItem(k, v); } catch { /* ignore */ } }
