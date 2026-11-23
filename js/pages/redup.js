/* ---------- Từ láy trong đề đã thi (N3 / N2): danh sách, học thẻ, kiểm tra, câu đề thật, ghép cặp ---------- */
import { $, $$, esc, pct, relDay, shuffle, debounce, normJa, toast, confirmDialog, renderStem } from '../util.js';
import * as store from '../store.js';
import { loadRedup } from '../data.js';
import { boxLabel } from '../srs.js';
import { navigate } from '../app.js';

const LEVELS = ['N3', 'N2'];
const lsGet = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } };
const ssSet = (k, v) => { try { sessionStorage.setItem(k, v); } catch { /* ignore */ } };
const changed = () => document.dispatchEvent(new CustomEvent('wcards-changed'));

export async function render(app, route) {
  const R = await loadRedup();
  if (!R.words.length) {
    app.innerHTML = '<div class="card"><h1>Từ láy</h1><p class="empty">Chưa có dữ liệu (<code>data/redup.json</code>). Chạy <code>python -I scripts/build_redup.py</code>.</p></div>';
    return;
  }
  const lv = levelOf(R, route.params);
  if (route.segs[0] === 'w' && route.segs[1]) return detailPage(app, R, decodeURIComponent(route.segs[1]), lv);
  if (route.segs[0] === 'study') return studyPage(app, R);
  if (route.segs[0] === 'test') return testPage(app, R, lv);
  if (route.segs[0] === 'exam') return examPage(app, R, lv);
  if (route.segs[0] === 'match') return matchPage(app, R, lv);
  return homePage(app, R, lv, route.params);
}

/* ---------- cấp độ & bộ từ ---------- */
function levelOf(R, params) {
  const want = params.lv || lsGet('rd-level') || 'N3';
  return R.levels[want] ? want : (LEVELS.find(l => R.levels[l]) || 'N3');
}
const pools = new Map();
/** Từ láy của một cấp, từ hay ra đề nhất xếp trước. */
function wordsOf(R, lv) {
  if (!pools.has(lv)) {
    pools.set(lv, R.words.filter(w => w.lv[lv]).sort((a, b) =>
      b.lv[lv].exams.length - a.lv[lv].exams.length || b.lv[lv].tested - a.lv[lv].tested || b.lv[lv].n - a.lv[lv].n || a.read.localeCompare(b.read, 'ja')));
  }
  return pools.get(lv);
}
const examLabel = (e) => { const [y, m] = e.split('-'); return `${+m}/${y}`; };

/* ---------- trạng thái thẻ ---------- */
const NEW = 'new', LEARNING = 'learning', KNOWN = 'known';
function statusOf(id) {
  const c = store.wcardOf(id);
  if (!c) return NEW;
  return c.box >= 4 ? KNOWN : LEARNING;
}
const STATUS_LABEL = { [NEW]: 'Chưa học', [LEARNING]: 'Đang học', [KNOWN]: 'Gần thuộc' };
const STATUS_CLASS = { [NEW]: '', [LEARNING]: 'warn', [KNOWN]: 'good' };
const statusPill = (id) => { const s = statusOf(id); return `<span class="pill ${STATUS_CLASS[s]}">${STATUS_LABEL[s]}</span>`; };
const isDue = (id) => { const c = store.wcardOf(id); return !!c && c.due <= Date.now(); };

function counts(pool) {
  const c = { all: pool.length, [NEW]: 0, [LEARNING]: 0, [KNOWN]: 0, due: 0, lapsed: 0 };
  for (const w of pool) {
    c[statusOf(w.id)]++;
    const card = store.wcardOf(w.id);
    if (card && card.due <= Date.now()) c.due++;
    if (card && card.lapses > 0 && card.box < 4) c.lapsed++;
  }
  return c;
}

/** Mã từ cho một bộ thẻ. `pool` đã xếp theo độ hay ra đề. */
function deck(pool, mode, limit = 0) {
  const card = (w) => store.wcardOf(w.id);
  let ws;
  if (mode === 'due') ws = pool.filter(w => card(w) && card(w).due <= Date.now()).sort((a, b) => card(a).due - card(b).due);
  else if (mode === 'new') ws = pool.filter(w => !card(w));
  else if (mode === 'weak') ws = pool.filter(w => card(w) && card(w).lapses > 0 && card(w).box < 4).sort((a, b) => card(b).lapses - card(a).lapses);
  else ws = shuffle(pool);
  if (limit) ws = ws.slice(0, limit);
  return ws.map(w => w.id);
}
const DECK_TITLE = { due: 'Ôn đến hạn', new: 'Từ mới', weak: 'Hay quên', all: 'Xáo trộn' };

/* ---------- hiển thị một từ ---------- */
const readOf = (w) => (w.read !== w.w ? w.read : '');
const altOf = (w) => [readOf(w), ...(w.forms || [])].filter(Boolean).join(' · ');
/** Tô đậm từ trong câu ví dụ. */
function hl(ja, f) {
  const h = esc(ja), k = esc(f);
  return k && h.includes(k) ? h.split(k).join(`<mark class="rd-hl">${k}</mark>`) : h;
}
const exHTML = (ex, max) => (ex || []).slice(0, max).map(e => `
  <div class="gr-ex"><div class="ja">${hl(e.ja, e.f)}</div><div class="small muted">${esc(e.vi ? `${e.vi} · ${e.src}` : e.src)}</div></div>`).join('');
/** Câu tự soạn (kèm dịch) cho từ mà đề chỉ đưa ra trong lựa chọn trả lời, không có câu hoàn chỉnh nào. */
const extraEx = (w) => (w.x ? [{ ja: w.x.ja, f: w.w, vi: w.x.vi, src: 'ví dụ bổ sung, không lấy từ đề' }] : []);
/** Câu dùng để khoét chỗ trống: câu trong đề của cấp này, không có thì lấy câu của cấp kia, rồi mới tới câu tự soạn. */
function clozeEx(w, lv) {
  if (w.lv[lv].ex.length) return w.lv[lv].ex;
  const other = LEVELS.filter(x => x !== lv && w.lv[x]).flatMap(x => w.lv[x].ex);
  return other.length ? other : extraEx(w);
}

function statLine(w, lv, R) {
  const s = w.lv[lv];
  if (!s) return '';
  return `ra trong <b>${s.exams.length}</b>/${R.levels[lv].exams.length} đề ${lv}` + (s.tested ? ` · <span class="pill warn">★ câu hỏi từ vựng ×${s.tested}</span>` : '');
}

function bodyHTML(w, lv, R, { examples = 3 } = {}) {
  const order = [lv, ...LEVELS.filter(x => x !== lv)].filter(x => w.lv[x]);
  return `
    <div class="gr-sec"><div class="gr-label">Ý nghĩa</div><div><b>${esc(w.vi)}</b></div></div>
    ${w.note ? `<div class="gr-sec"><div class="gr-label">Ghi chú</div><div>${esc(w.note)}</div></div>` : ''}
    ${order.map(x => `<div class="gr-sec"><div class="gr-label">Trong đề ${x} · ${w.lv[x].exams.length}/${R.levels[x].exams.length} đề</div>${exHTML(w.lv[x].ex, examples) || '<span class="muted small">Chỉ gặp trong các lựa chọn trả lời, đề không có câu hoàn chỉnh nào dùng từ này.</span>'}</div>`).join('')}
    ${w.x ? `<div class="gr-sec"><div class="gr-label">Ví dụ bổ sung</div>${exHTML(extraEx(w), 1)}</div>` : ''}`;
}

/* ---------- trang chính ---------- */
function homePage(app, R, lv0, params) {
  let lv = lv0;
  let query = params.q || '', group = '', filter = '', limit = 80;
  let front = lsGet('rd-front') || 'word';

  const draw = () => {
    const L = R.levels[lv], pool = wordsOf(R, lv), c = counts(pool);
    const nEx = L.exams.length;
    const groups = R.groups.filter(g => pool.some(w => w.group === g));
    const nTested = pool.filter(w => w.lv[lv].tested).length;
    app.innerHTML = `
      <div class="row between">
        <div><h1 style="margin-bottom:.1em">Từ láy trong đề thi</h1>
          <p class="muted" style="margin:0">${pool.length} từ láy (ぺらぺら, どんどん, 時々 …) đã xuất hiện trong ${nEx} đề JLPT ${lv} thật (${examLabel(L.exams[0])} → ${examLabel(L.exams[nEx - 1])}), xếp theo số đề có từ đó.</p></div>
        <div class="seg" id="lv">${LEVELS.filter(l => R.levels[l]).map(l => `<button data-lv="${l}" class="${l === lv ? 'active' : ''}">${l} · ${wordsOf(R, l).length} từ</button>`).join('')}</div>
      </div>
      <div class="grid-tiles mt">
        <div class="tile"><div class="label">Đến hạn ôn</div><div class="value" style="color:${c.due ? 'var(--bad)' : 'inherit'}">${c.due}</div></div>
        <div class="tile"><div class="label">Chưa học</div><div class="value">${c[NEW]}</div></div>
        <div class="tile"><div class="label">Đang học</div><div class="value">${c[LEARNING]}</div><div class="sub">hay quên: ${c.lapsed}</div></div>
        <div class="tile"><div class="label">Gần thuộc (≥ 1 tháng)</div><div class="value">${c[KNOWN]}</div><div class="progress-line mt"><i style="width:${pct(c[KNOWN], c.all)}%"></i></div></div>
      </div>
      <div class="card mt">
        <div class="row between"><h3 style="margin:0">Học thẻ</h3>
          <div class="row"><span class="small muted">Mặt trước:</span>
            <div class="seg"><button data-front="word" class="${front === 'word' ? 'active' : ''}">Từ</button><button data-front="meaning" class="${front === 'meaning' ? 'active' : ''}">Nghĩa</button></div></div></div>
        <p class="small muted">Lật thẻ rồi chọn <b>Nhớ</b> hoặc <b>Quên</b>. Thẻ quên quay lại ngay trong phiên và hẹn ôn ngày mai; thẻ nhớ giãn dần 3 → 7 → 14 → 30 → 60 ngày.</p>
        <div class="row">
          <button class="btn btn-primary btn-lg" data-deck="due" ${c.due ? '' : 'disabled'}>Ôn đến hạn (${c.due})</button>
          <button class="btn btn-lg" data-deck="new" data-n="10" ${c[NEW] ? '' : 'disabled'}>10 từ mới (hay ra nhất)</button>
          <button class="btn btn-lg" data-deck="new" data-n="20" ${c[NEW] ? '' : 'disabled'}>20 từ mới</button>
          <button class="btn btn-lg" data-deck="weak" ${c.lapsed ? '' : 'disabled'}>Hay quên (${c.lapsed})</button>
          <button class="btn btn-lg" data-deck="all">Xáo trộn tất cả</button>
        </div>
        <h3 style="margin:1.25rem 0 .6rem">Kiểm tra</h3>
        <div class="row">
          <a class="btn btn-lg btn-primary" href="#/redup/test?lv=${lv}">📝 Trắc nghiệm nghĩa · điền câu</a>
          <a class="btn btn-lg" href="#/redup/exam?lv=${lv}">📄 Câu đề thật có từ láy (${L.questions.length})</a>
          <a class="btn btn-lg" href="#/redup/match?lv=${lv}">🧩 Ghép cặp</a>
        </div>
      </div>
      <div class="search-bar mt">
        <input class="input" id="q" type="search" placeholder="Tìm từ hoặc nghĩa, ví dụ: ぺらぺら, trôi chảy" value="${esc(query)}">
        <select class="input" id="g" style="max-width:230px"><option value="">Mọi nhóm</option>${groups.map(g => `<option ${g === group ? 'selected' : ''}>${esc(g)}</option>`).join('')}</select>
        <select class="input" id="f" style="max-width:230px">${[['', 'Mọi từ'], ['tested', `★ Có trong câu hỏi từ vựng (${nTested})`], ['due', 'Đến hạn'], [NEW, 'Chưa học'], [LEARNING, 'Đang học'], [KNOWN, 'Gần thuộc']].map(([v, l]) => `<option value="${v}" ${v === filter ? 'selected' : ''}>${l}</option>`).join('')}</select>
        <span class="small muted" id="cnt" style="align-self:center"></span>
      </div>
      <div class="ref-list" id="list"></div><div id="more-wrap"></div>`;

    $$('[data-lv]', app).forEach(b => b.onclick = () => { lv = b.dataset.lv; lsSet('rd-level', lv); group = ''; limit = 80; draw(); });
    $$('[data-front]', app).forEach(b => b.onclick = () => { front = b.dataset.front; lsSet('rd-front', front); draw(); });
    $$('[data-deck]', app).forEach(b => b.onclick = () => {
      const ids = deck(pool, b.dataset.deck, +b.dataset.n || 0);
      if (!ids.length) { toast('Bộ thẻ này đang trống'); return; }
      ssSet('rd-deck', JSON.stringify({ ids, front, lv, title: `${DECK_TITLE[b.dataset.deck]} · ${lv}`, back: `#/redup?lv=${lv}` }));
      navigate('#/redup/study');
    });

    const paint = () => {
      const n = normJa(query), raw = query.trim().toLowerCase();
      const list = pool.filter(w => {
        if (group && w.group !== group) return false;
        if (filter === 'tested' ? !w.lv[lv].tested : filter === 'due' ? !isDue(w.id) : filter && statusOf(w.id) !== filter) return false;
        if (!raw) return true;
        return [w.w, w.read, ...(w.forms || [])].some(f => normJa(f).includes(n)) || w.vi.toLowerCase().includes(raw);
      });
      $('#cnt', app).textContent = `${list.length} từ`;
      $('#list', app).innerHTML = list.slice(0, limit).map(w => `
        <a class="ref-card" href="#/redup/w/${encodeURIComponent(w.id)}?lv=${lv}" style="color:inherit;text-decoration:none">
          <span class="ref-ja">${esc(w.w)}</span>
          <span>${esc(w.vi)} ${statusPill(w.id)}${isDue(w.id) ? ' <span class="pill bad">đến hạn</span>' : ''}</span>
          <div class="meta small">${altOf(w) ? `<span class="ja">${esc(altOf(w))}</span> · ` : ''}<span class="muted">${esc(w.group)} · ${statLine(w, lv, R)}</span></div>
        </a>`).join('') || '<p class="empty">Không có từ nào khớp.</p>';
      $('#more-wrap', app).innerHTML = list.length > limit ? `<button class="btn mt" id="more">Xem thêm (${list.length - limit})</button>` : '';
      $('#more', app)?.addEventListener('click', () => { limit += 100; paint(); });
    };
    paint();
    $('#q', app).oninput = debounce((e) => { query = e.target.value; limit = 80; paint(); }, 150);
    $('#g', app).onchange = (e) => { group = e.target.value; limit = 80; paint(); };
    $('#f', app).onchange = (e) => { filter = e.target.value; limit = 80; paint(); };
  };
  draw();
}

/* ---------- chi tiết một từ ---------- */
function detailPage(app, R, id, lv) {
  const w = R.byId.get(id);
  if (!w) { app.innerHTML = '<div class="card"><p>Không tìm thấy từ này. <a href="#/redup">Về danh sách từ láy</a></p></div>'; return; }
  const here = w.lv[lv] ? lv : LEVELS.find(x => w.lv[x]);
  const draw = () => {
    const c = store.wcardOf(id);
    const qs = LEVELS.filter(x => R.levels[x]).flatMap(x => R.levels[x].questions.filter(q => q.words.includes(id)).map(q => ({ ...q, lv: x })));
    app.innerHTML = `
      <p class="small"><a href="#/redup?lv=${here}">← Từ láy ${here}</a></p>
      <div class="card">
        <div class="row between"><div>
          <h1 class="ja" style="margin:0">${esc(w.w)}</h1>
          ${altOf(w) ? `<div class="muted ja">${esc(altOf(w))}</div>` : ''}
          <div style="margin-top:.4rem"><span class="pill moji">${esc(w.group)}</span> ${statusPill(id)}</div>
          ${LEVELS.filter(x => w.lv[x]).map(x => `<div class="small" style="margin-top:.4rem">${statLine(w, x, R)}: <span class="muted">${w.lv[x].exams.map(examLabel).join(', ')}</span></div>`).join('')}</div>
          <div class="row">${c ? `<span class="small muted">${esc(boxLabel(c.box))} · ôn ${esc(relDay(c.due))}${c.lapses ? ` · quên ${c.lapses} lần` : ''}</span>` : ''}
            <button class="btn btn-primary" id="study">Học thẻ này</button>
            ${c ? '<button class="btn btn-ghost btn-sm" id="reset" title="Đưa về chưa học">Đặt lại</button>' : ''}</div></div>
        <div class="mt">${bodyHTML(w, here, R, { examples: 5 })}</div>
      </div>
      ${qs.length ? `<div class="card mt"><h3 style="margin-top:0">Câu hỏi đề thật có từ này (${qs.length})</h3>
        <p class="small muted">Bấm vào câu để xem các lựa chọn và đáp án.</p>
        ${qs.map(q => `<details class="rd-q"><summary><span class="ja">${renderStem(q.stem)}</span> <span class="small muted">${q.lv} ${examLabel(q.exam)}</span></summary>
          <ol class="ja">${q.options.map((o, k) => `<li${k === q.answer ? ' class="rd-ok"' : ''}>${renderStem(o)}${k === q.answer ? ' ✓' : ''}</li>`).join('')}</ol></details>`).join('')}
      </div>` : ''}`;
    $('#study', app).onclick = () => {
      ssSet('rd-deck', JSON.stringify({ ids: [id], front: 'word', lv: here, title: w.w, back: `#/redup/w/${encodeURIComponent(id)}?lv=${here}` }));
      navigate('#/redup/study');
    };
    $('#reset', app)?.addEventListener('click', async () => {
      if (await confirmDialog({ title: 'Đặt lại từ này về chưa học?', body: 'Lịch ôn của thẻ sẽ bị xoá.', ok: 'Đặt lại', danger: true })) {
        store.resetWord(id); changed(); draw();
      }
    });
  };
  draw();
}

/* ---------- học thẻ ---------- */
function studyPage(app, R) {
  let cfg = null;
  try { cfg = JSON.parse(sessionStorage.getItem('rd-deck') || 'null'); } catch { /* ignore */ }
  const total = (cfg?.ids || []).filter(id => R.byId.has(id));
  if (!total.length) { navigate('#/redup'); return; }

  const queue = total.slice();
  const failed = new Set();   // quên ít nhất 1 lần trong phiên
  const settled = new Set();  // đã nhớ xong trong phiên
  let flipped = false, again = 0, good = 0;
  const front = cfg.front || 'word';
  const back = cfg.back || '#/redup';
  const lv = R.levels[cfg.lv] ? cfg.lv : 'N3';

  const draw = () => {
    if (!queue.length) return summary();
    const w = R.byId.get(queue[0]);
    const c = store.wcardOf(w.id);
    app.innerHTML = `
      <div class="test-bar">
        <div><div class="small muted">Học thẻ từ láy · ${esc(cfg.title || '')}</div><b>${settled.size} / ${total.length}</b> <span class="small muted">· còn ${queue.length} lượt · quên ${again}</span></div>
        <div class="row"><a class="btn btn-sm" href="${esc(back)}">Dừng</a></div>
        <div class="progress-line"><i style="width:${pct(settled.size, total.length)}%"></i></div>
      </div>
      <div class="card gr-card" id="flash" tabindex="0" role="button" aria-label="Lật thẻ">
        ${!flipped ? `
          <div class="small muted" style="text-align:center">${esc(w.group)} · ${c ? esc(boxLabel(c.box)) : 'Mới'}${failed.has(w.id) ? ' · vừa quên' : ''}</div>
          <div class="gr-front ${front === 'word' ? 'ja' : ''}">${front === 'word' ? esc(w.w) : esc(w.vi)}</div>
          <p class="small muted" style="text-align:center;margin-top:1.5rem">${front === 'word' ? 'Nhớ nghĩa và một câu ví dụ' : 'Nhớ từ láy tiếng Nhật'}, rồi bấm để lật (Space)</p>`
        : `
          <div class="gr-back-head"><span class="ja gr-pattern">${esc(w.w)}</span> ${altOf(w) ? `<span class="muted ja">${esc(altOf(w))}</span>` : ''}</div>
          ${bodyHTML(w, lv, R, { examples: 3 })}
          <p class="small" style="margin-top:.75rem"><a href="#/redup/w/${encodeURIComponent(w.id)}?lv=${lv}" target="_blank" rel="noopener">Xem đầy đủ ↗</a></p>`}
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
    if (!flipped || !queue.length) return;
    const id = queue.shift();
    if (g === 'again') {
      if (!failed.has(id)) store.gradeWord(id, 'again');   // chỉ ghi lịch ở lần quên đầu tiên của phiên
      failed.add(id); again++;
      queue.splice(Math.min(queue.length, 3), 0, id);       // quay lại sau vài thẻ
    } else {
      if (!failed.has(id)) { store.gradeWord(id, 'good'); good++; }
      settled.add(id);
    }
    changed();
    flipped = false;
    draw();
  };

  const summary = () => {
    const weak = [...failed];
    app.innerHTML = `
      <div class="card" style="text-align:center">
        <h2>Xong bộ thẻ 🎉</h2>
        <p>${total.length} từ · nhớ ngay <b>${good}</b> · quên <b>${weak.length}</b> (ôn lại ngày mai)</p>
        ${weak.length ? `<div class="mt" style="text-align:left"><b>Các từ đã quên:</b>${weak.map(id => `<div><a class="ja" href="#/redup/w/${encodeURIComponent(id)}?lv=${lv}">${esc(R.byId.get(id).w)}</a> <span class="muted small">${esc(R.byId.get(id).vi)}</span></div>`).join('')}</div>` : ''}
        <div class="row mt" style="justify-content:center"><a class="btn btn-primary" href="${esc(back)}">Quay lại</a></div>
      </div>`;
  };

  const onKey = (e) => {
    if (e.target.matches?.('input,textarea,select')) return;
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); if (!flipped && queue.length) { flipped = true; draw(); } }
    else if (e.key === 'ArrowLeft' || e.key === '1') grade('again');
    else if (e.key === 'ArrowRight' || e.key === '2') grade('good');
  };
  document.addEventListener('keydown', onKey);
  draw();
  return () => document.removeEventListener('keydown', onKey);
}

/* ---------- kiểm tra trắc nghiệm ---------- */
const LETTERS = ['A', 'B', 'C', 'D'];
const KIND_ASK = { w2m: 'Từ này nghĩa là gì?', m2w: 'Từ láy nào có nghĩa này?', cloze: 'Chọn từ láy điền vào chỗ trống' };
const near = (a, b) => (a.near || []).includes(b.id) || (b.near || []).includes(a.id);

/** 3 dạng: từ → nghĩa, nghĩa → từ, câu trong đề bị khoét từ → chọn từ. */
function makeQuestion(w, pool, kind, lv) {
  const text = (x) => (kind === 'w2m' ? x.vi : x.w);
  const others = pool.filter(x => x.id !== w.id && !near(w, x));
  const same = shuffle(others.filter(x => x.group === w.group)), rest = shuffle(others.filter(x => x.group !== w.group));
  // hỏi nghĩa: ưu tiên từ cùng nhóm cho khó; điền câu: ưu tiên khác nhóm để chỉ có một đáp án hợp lý
  const order = kind === 'cloze' ? [...rest, ...same] : [...same, ...rest];
  const seen = new Set([text(w)]);
  const wrong = [];
  for (const x of order) {
    if (wrong.length >= 3) break;
    if (seen.has(text(x))) continue;
    seen.add(text(x)); wrong.push(x);
  }
  const opts = shuffle([w, ...wrong]);
  const ex = kind === 'cloze' ? shuffle(clozeEx(w, lv))[0] : null;
  return {
    id: w.id, kind, ex,
    prompt: kind === 'w2m' ? w.w : kind === 'm2w' ? w.vi : ex.ja.split(ex.f).join('（　　）'),
    sub: kind === 'cloze' ? ex.src : '',
    labels: opts.map(text), answer: opts.indexOf(w),
  };
}

function testPage(app, R, lv) {
  const pool = wordsOf(R, lv);
  const back = `#/redup?lv=${lv}`;
  let n = 20, scope = 'all', kindSel = 'mix';

  const setup = () => {
    const weak = pool.filter(w => statusOf(w.id) !== KNOWN).length;
    const tested = pool.filter(w => w.lv[lv].tested).length;
    const seg = (id, items, cur) => `<div class="seg" id="${id}">${items.map(([v, l]) => `<button data-v="${v}" class="${String(v) === String(cur) ? 'active' : ''}">${l}</button>`).join('')}</div>`;
    app.innerHTML = `
      <p class="small"><a href="${back}">← Từ láy ${lv}</a></p>
      <div class="card"><h1 style="margin-top:0">Kiểm tra từ láy ${lv}</h1>
        <p class="muted">Trắc nghiệm 4 đáp án: <b>từ → nghĩa</b>, <b>nghĩa → từ</b> và <b>điền từ vào câu lấy từ đề thi</b>. Từ trả lời sai được hẹn ôn lại ngày mai trong phần Học thẻ.</p>
        <div class="row"><span>Số câu:</span>${seg('n', [[10, 10], [20, 20], [40, 40], [pool.length, `Tất cả (${pool.length})`]], n)}</div>
        <div class="row mt"><span>Phạm vi:</span>${seg('s', [['all', `Tất cả ${pool.length} từ`], ['tested', `★ Có trong câu hỏi từ vựng (${tested})`], ['weak', `Chưa thuộc (${weak})`]], scope)}</div>
        <div class="row mt"><span>Dạng câu:</span>${seg('k', [['mix', 'Trộn cả 3'], ['w2m', 'Từ → nghĩa'], ['m2w', 'Nghĩa → từ'], ['cloze', 'Điền vào câu']], kindSel)}</div>
        <div class="row mt"><button class="btn btn-primary btn-lg" id="go">Bắt đầu</button></div>
      </div>`;
    const bind = (id, set) => $$(`#${id} button`, app).forEach(b => b.onclick = () => { set(b.dataset.v); $$(`#${id} button`, app).forEach(x => x.classList.toggle('active', x === b)); });
    bind('n', v => { n = +v; }); bind('s', v => { scope = v; }); bind('k', v => { kindSel = v; });
    $('#go', app).onclick = () => {
      let src = pool;
      if (scope === 'weak') src = pool.filter(w => statusOf(w.id) !== KNOWN);
      if (scope === 'tested') src = pool.filter(w => w.lv[lv].tested);
      if (kindSel === 'cloze') src = src.filter(w => clozeEx(w, lv).length);
      if (src.length < 4) { toast('Phạm vi này có quá ít từ'); return; }
      run(shuffle(src).slice(0, n));
    };
  };

  const run = (ws) => {
    const qs = ws.map(w => {
      let kinds = kindSel === 'mix' ? ['w2m', 'm2w'] : [kindSel];
      if (kindSel === 'mix' && clozeEx(w, lv).length) kinds = ['w2m', 'm2w', 'cloze', 'cloze'];
      return makeQuestion(w, pool, kinds[Math.floor(Math.random() * kinds.length)], lv);
    });
    let i = 0, picked = null;
    const results = [];
    const draw = () => {
      if (i >= qs.length) return finish();
      const q = qs[i];
      const done = picked != null;
      app.innerHTML = `
        <div class="test-bar"><div><div class="small muted">Kiểm tra từ láy ${lv}</div><b>${i + 1} / ${qs.length}</b> <span class="small muted">· đúng ${results.filter(r => r.ok).length}</span></div>
          <div class="row"><a class="btn btn-sm" href="${back}">Thoát</a></div>
          <div class="progress-line"><i style="width:${pct(i, qs.length)}%"></i></div></div>
        <div class="card mt">
          <div class="small muted">${KIND_ASK[q.kind]}</div>
          <div class="gr-front ${q.kind === 'm2w' ? '' : 'ja'}" style="${q.kind === 'cloze' ? 'font-size:1.3rem;text-align:left' : ''}">${esc(q.prompt)}</div>
          ${q.sub ? `<div class="muted small">${esc(q.sub)}</div>` : ''}
          <div class="mt">${q.labels.map((l, k) => `<button class="opt ${done ? (k === q.answer ? 'correct' : k === picked ? 'wrong' : '') : ''}" data-k="${k}" ${done ? 'disabled' : ''} style="margin-bottom:.5rem"><b>${LETTERS[k]}.</b> <span class="${q.kind === 'w2m' ? '' : 'ja'}" style="${q.kind === 'w2m' ? 'font-family:var(--font)' : ''}">${esc(l)}</span></button>`).join('')}</div>
          ${done ? feedback(q) : ''}
        </div>`;
      $$('[data-k]', app).forEach(b => b.onclick = () => pick(+b.dataset.k));
      $('#next', app)?.addEventListener('click', next);
    };
    const feedback = (q) => {
      const w = R.byId.get(q.id);
      const ok = picked === q.answer;
      const ex = q.ex || clozeEx(w, lv)[0];
      return `<div class="card tight" style="margin-top:.5rem"><b style="color:var(${ok ? '--good' : '--bad'})">${ok ? '✓ Đúng' : '✗ Sai'}</b>
        <div class="mt"><a class="ja" href="#/redup/w/${encodeURIComponent(w.id)}?lv=${lv}" target="_blank" rel="noopener"><b>${esc(w.w)}</b></a>${readOf(w) ? ` <span class="ja muted">${esc(readOf(w))}</span>` : ''} — ${esc(w.vi)}</div>
        ${w.note ? `<div class="small muted">${esc(w.note)}</div>` : ''}
        ${ex ? `<div class="small" style="margin-top:.3rem"><span class="ja">${hl(ex.ja, ex.f)}</span><br><span class="muted">${esc(ex.vi ? `${ex.vi} · ${ex.src}` : ex.src)}</span></div>` : ''}
        <div class="row mt"><button class="btn btn-primary" id="next">${i + 1 >= qs.length ? 'Xem kết quả' : 'Câu tiếp'} (Enter)</button></div></div>`;
    };
    const pick = (k) => {
      if (picked != null) return;
      picked = k;
      const q = qs[i], ok = k === q.answer;
      results.push({ ids: [q.id], ok });
      if (!ok) { store.gradeWord(q.id, 'again'); changed(); }
      draw();
    };
    const next = () => { if (picked == null) return; picked = null; i++; draw(); };
    const finish = () => resultPage(app, R, lv, results, { again: setup, back, title: 'Từ sai trong bài kiểm tra' });
    draw();
  };

  const onKey = quizKeys();
  document.addEventListener('keydown', onKey);
  setup();
  return () => document.removeEventListener('keydown', onKey);
}

/** Phím 1–4 chọn đáp án, Enter sang câu tiếp. */
function quizKeys() {
  return (e) => {
    if (e.target.matches?.('input,textarea,select')) return;
    if (/^[1-4]$/.test(e.key)) document.querySelector(`[data-k="${+e.key - 1}"]:not([disabled])`)?.click();
    else if (e.key === 'Enter') document.getElementById('next')?.click();
  };
}

/** Trang kết quả dùng chung cho hai bài kiểm tra. results = [{ids: [mã các từ bị tính sai], ok}] */
function resultPage(app, R, lv, results, { again, back, title }) {
  const good = results.filter(r => r.ok).length;
  const wrongIds = [...new Set(results.filter(r => !r.ok).flatMap(r => r.ids))];
  app.innerHTML = `
    <div class="card" style="text-align:center"><h2>Kết quả: ${good} / ${results.length} (${pct(good, results.length)}%)</h2>
      <div class="progress-line"><i style="width:${pct(good, results.length)}%"></i></div>
      <p class="muted">${wrongIds.length ? `${wrongIds.length} từ sai đã được hẹn ôn lại vào ngày mai.` : good === results.length ? 'Không sai câu nào. Rất tốt!' : ''}</p>
      <div class="row" style="justify-content:center">
        ${wrongIds.length ? '<button class="btn btn-primary" id="redo">Học lại các từ sai</button>' : ''}
        <button class="btn" id="again">Làm bài khác</button>
        <a class="btn" href="${back}">Quay lại</a></div></div>
    ${wrongIds.length ? `<div class="card mt"><b>Các từ sai</b>${wrongIds.map(id => { const w = R.byId.get(id); return `<div style="margin-top:.4rem"><a class="ja" href="#/redup/w/${encodeURIComponent(id)}?lv=${lv}"><b>${esc(w.w)}</b></a> <span class="muted small">${esc(w.vi)}</span></div>`; }).join('')}</div>` : ''}`;
  $('#again', app).onclick = again;
  $('#redo', app)?.addEventListener('click', () => {
    ssSet('rd-deck', JSON.stringify({ ids: wrongIds, front: 'word', lv, title, back }));
    navigate('#/redup/study');
  });
}

/* ---------- câu hỏi đề thật có từ láy ---------- */
const QTYPE = { context: 'Điền từ theo ngữ cảnh', paraphrase: 'Từ đồng nghĩa', usage: 'Cách dùng từ', reading: 'Cách đọc Kanji', orthography: 'Viết chữ Hán', formation: 'Cấu tạo từ', grammar: 'Ngữ pháp' };

function examPage(app, R, lv) {
  const all = R.levels[lv].questions;
  const back = `#/redup?lv=${lv}`;
  let n = 20, type = '';

  const setup = () => {
    const types = Object.keys(QTYPE).filter(t => all.some(q => q.type === t));
    app.innerHTML = `
      <p class="small"><a href="${back}">← Từ láy ${lv}</a></p>
      <div class="card"><h1 style="margin-top:0">Câu đề thật có từ láy · ${lv}</h1>
        <p class="muted">${all.length} câu hỏi nguyên văn trong ${R.levels[lv].exams.length} đề ${lv} mà từ láy là từ được hỏi hoặc nằm trong các lựa chọn. Chữa ngay từng câu, kèm nghĩa của mọi từ láy trong câu.</p>
        <div class="row"><span>Số câu:</span><div class="seg" id="n">${[10, 20, 40, all.length].map((v, i) => `<button data-v="${v}" class="${v === n ? 'active' : ''}">${i === 3 ? `Tất cả (${v})` : v}</button>`).join('')}</div></div>
        <div class="row mt"><span>Dạng:</span><div class="seg" id="t"><button data-v="" class="${type ? '' : 'active'}">Mọi dạng</button>${types.map(t => `<button data-v="${t}" class="${t === type ? 'active' : ''}">${QTYPE[t]} (${all.filter(q => q.type === t).length})</button>`).join('')}</div></div>
        <div class="row mt"><button class="btn btn-primary btn-lg" id="go">Bắt đầu</button></div>
      </div>`;
    const bind = (id, set) => $$(`#${id} button`, app).forEach(b => b.onclick = () => { set(b.dataset.v); $$(`#${id} button`, app).forEach(x => x.classList.toggle('active', x === b)); });
    bind('n', v => { n = +v; }); bind('t', v => { type = v; });
    $('#go', app).onclick = () => {
      const src = all.filter(q => !type || q.type === type);
      if (!src.length) { toast('Không có câu nào thuộc dạng này'); return; }
      run(shuffle(src).slice(0, n));
    };
  };

  const run = (qs) => {
    let i = 0, picked = null;
    const results = [];
    const draw = () => {
      if (i >= qs.length) return resultPage(app, R, lv, results, { again: setup, back, title: 'Từ sai trong câu đề thật' });
      const q = qs[i];
      const done = picked != null;
      const long = q.options.some(o => o.length > 16);
      app.innerHTML = `
        <div class="test-bar"><div><div class="small muted">Câu đề thật · ${lv} ${examLabel(q.exam)} · ${esc(QTYPE[q.type] || '')}</div><b>${i + 1} / ${qs.length}</b> <span class="small muted">· đúng ${results.filter(r => r.ok).length}</span></div>
          <div class="row"><a class="btn btn-sm" href="${back}">Thoát</a></div>
          <div class="progress-line"><i style="width:${pct(i, qs.length)}%"></i></div></div>
        <div class="card mt">
          <div class="ja rd-stem">${renderStem(q.stem)}</div>
          <div class="mt ${long ? '' : 'rd-opts'}">${q.options.map((o, k) => `<button class="opt ${done ? (k === q.answer ? 'correct' : k === picked ? 'wrong' : '') : ''}" data-k="${k}" ${done ? 'disabled' : ''} style="margin-bottom:.5rem"><span class="n">${k + 1}</span><span class="opt-body">${renderStem(o)}</span></button>`).join('')}</div>
          ${done ? feedback(q) : ''}
        </div>`;
      $$('[data-k]', app).forEach(b => b.onclick = () => pick(+b.dataset.k));
      $('#next', app)?.addEventListener('click', next);
    };
    const feedback = (q) => {
      const ok = picked === q.answer;
      return `<div class="card tight" style="margin-top:.5rem"><b style="color:var(${ok ? '--good' : '--bad'})">${ok ? '✓ Đúng' : `✗ Sai · đáp án: ${q.answer + 1}`}</b>
        <div class="gr-label" style="margin-top:.5rem">Từ láy trong câu này</div>
        ${q.words.map(id => R.byId.get(id)).filter(Boolean).map(w => `<div><a class="ja" href="#/redup/w/${encodeURIComponent(w.id)}?lv=${lv}" target="_blank" rel="noopener"><b>${esc(w.w)}</b></a>${readOf(w) ? ` <span class="ja muted small">${esc(readOf(w))}</span>` : ''} — ${esc(w.vi)}</div>`).join('')}
        <div class="row mt"><button class="btn btn-primary" id="next">${i + 1 >= qs.length ? 'Xem kết quả' : 'Câu tiếp'} (Enter)</button></div></div>`;
    };
    const pick = (k) => {
      if (picked != null) return;
      picked = k;
      const q = qs[i], ok = k === q.answer;
      // sai: hẹn ôn lại từ mà câu kiểm tra, và từ láy nằm trong lựa chọn vừa chọn nhầm
      const ids = ok ? [] : [...new Set([q.target, ...(q.ow[k] || [])])].filter(id => id && R.byId.has(id));
      results.push({ ids, ok });
      if (ids.length) { ids.forEach(id => store.gradeWord(id, 'again')); changed(); }
      draw();
    };
    const next = () => { if (picked == null) return; picked = null; i++; draw(); };
    draw();
  };

  const onKey = quizKeys();
  document.addEventListener('keydown', onKey);
  setup();
  return () => document.removeEventListener('keydown', onKey);
}

/* ---------- ghép cặp: từ ↔ nghĩa ---------- */
function matchPage(app, R, lv) {
  const pool = wordsOf(R, lv);
  const back = `#/redup?lv=${lv}`;
  const SIZE = 6;
  let timer = null;
  const round = () => {
    clearInterval(timer);
    // ưu tiên từ chưa thuộc, rồi lấy ngẫu nhiên; không lấy hai từ gần nghĩa vào cùng một ván
    const chosen = [];
    for (const w of [...shuffle(pool.filter(x => statusOf(x.id) !== KNOWN)), ...shuffle(pool)]) {
      if (chosen.length >= SIZE) break;
      if (chosen.includes(w) || chosen.some(x => x.vi === w.vi || near(x, w))) continue;
      chosen.push(w);
    }
    const left = shuffle(chosen), right = shuffle(chosen);
    const solved = new Set();
    let selL = null, selR = null, mistakes = 0;
    const t0 = Date.now();
    const draw = () => {
      app.innerHTML = `
        <p class="small"><a href="${back}">← Từ láy ${lv}</a></p>
        <div class="card"><div class="row between"><h2 style="margin:0">Ghép cặp từ láy ${lv}</h2><span class="small muted">Sai: ${mistakes} · <span id="tm">${Math.round((Date.now() - t0) / 1000)}</span>s</span></div>
          <p class="small muted">Chọn một từ bên trái và nghĩa tương ứng bên phải.</p>
          <div class="grid-2" style="align-items:start">
            <div>${left.map(w => `<button class="opt ${solved.has(w.id) ? 'correct' : selL === w.id ? 'selected' : ''}" data-l="${esc(w.id)}" ${solved.has(w.id) ? 'disabled' : ''} style="margin-bottom:.5rem">${esc(w.w)}</button>`).join('')}</div>
            <div>${right.map(w => `<button class="opt ${solved.has(w.id) ? 'correct' : selR === w.id ? 'selected' : ''}" data-r="${esc(w.id)}" ${solved.has(w.id) ? 'disabled' : ''} style="margin-bottom:.5rem;font-family:var(--font)">${esc(w.vi)}</button>`).join('')}</div>
          </div>
          ${solved.size === left.length ? `<div class="mt"><b>Xong! ${Math.round((Date.now() - t0) / 1000)} giây, sai ${mistakes} lần.</b><div class="row mt"><button class="btn btn-primary" id="more">Ván mới</button><a class="btn" href="${back}">Quay lại</a></div></div>` : ''}
        </div>`;
      $$('[data-l]', app).forEach(b => b.onclick = () => { selL = b.dataset.l; check(); });
      $$('[data-r]', app).forEach(b => b.onclick = () => { selR = b.dataset.r; check(); });
      $('#more', app)?.addEventListener('click', round);
    };
    const check = () => {
      if (selL && selR) {
        if (selL === selR) solved.add(selL);
        else { mistakes++; store.gradeWord(selL, 'again'); changed(); }
        selL = selR = null;
        if (solved.size === left.length) clearInterval(timer);
      }
      draw();
    };
    draw();
    timer = setInterval(() => { const el = $('#tm', app); if (el) el.textContent = Math.round((Date.now() - t0) / 1000); }, 500);
  };
  round();
  return () => clearInterval(timer);
}
