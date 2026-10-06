/* ---------- Quick drill: chọn dạng → làm từng câu, chữa ngay ---------- */
import { $, $$, esc, uid, pct, toast, fmtDuration } from '../util.js';
import * as store from '../store.js';
import { SECTIONS, TYPES, typesOf, typeLabel, getQ, toItems, composeDrill, composePassageDrill, questionsOfType } from '../data.js';
import { renderItem } from '../question.js';
import { navigate } from '../app.js';

const DRILL_KEY = 'drill-current';

export async function render(app, route) {
  if (route.segs[0] === 'run') return runPage(app);
  return setupPage(app, route.params);
}

function setupPage(app, params) {
  const prev = store.getSession(DRILL_KEY);
  let section = params.section || (params.type ? TYPES[params.type]?.section : null) || 'moji';
  let selected = new Set(params.type ? [params.type] : []);
  let count = Number(params.count) || 10;
  let strategy = 'mixed';
  let includeB = store.settings().drillIncludeB !== false;

  const draw = () => {
    const types = typesOf(section).filter(t => questionsOfType(t).length);
    if (![...selected].some(t => TYPES[t].section === section)) selected = new Set(types.filter(t => !TYPES[t].passage).slice(0, 5));
    const isPassage = [...selected].some(t => TYPES[t]?.passage);
    const poolSize = [...selected].reduce((a, t) => a + questionsOfType(t).filter(q => includeB || q.tier !== 'B').length, 0);
    const bCount = [...selected].reduce((a, t) => a + questionsOfType(t).filter(q => q.tier === 'B').length, 0);
    const stats = store.get().stats;
    app.innerHTML = `
      <h1>Luyện nhanh</h1>
      <p class="muted">Làm từng câu, biết đúng sai và đọc giải thích ngay. Câu sai tự động vào "Xem sau".</p>
      ${prev && !prev.finished ? `<div class="card" style="border-color:var(--primary)"><div class="row between"><div><b>Bài luyện đang dở</b> · ${Object.keys(prev.answers).length}/${prev.qids.length} câu</div><div class="row"><a class="btn btn-primary btn-sm" href="#/drill/run">Tiếp tục</a><button class="btn btn-sm" id="discard">Bỏ</button></div></div></div>` : ''}
      <div class="card">
        <h3>1. Phần</h3>
        <div class="seg">${Object.keys(SECTIONS).map(s => `<button class="${s === section ? 'active' : ''}" data-s="${s}">${esc(SECTIONS[s].label)}</button>`).join('')}</div>
      </div>
      <div class="card">
        <h3>2. Dạng bài <span class="small muted">(chọn nhiều)</span></h3>
        <div class="stack">
          ${types.map(t => { const st = typeStats(t, stats); return `
            <label class="check"><input type="checkbox" data-t="${t}" ${selected.has(t) ? 'checked' : ''}>
              <span>${TYPES[t].mondai ? `<span class="muted">問題${TYPES[t].mondai}</span> ` : ''}<b>${esc(TYPES[t].label)}</b> <span class="ja muted small">${esc(TYPES[t].jp)}</span>
              <span class="small muted">· ${questionsOfType(t).length} câu${st.n ? ` · bạn đúng ${pct(st.c, st.n)}% (${st.n} lượt)` : ''}</span></span></label>`; }).join('')}
        </div>
      </div>
      <div class="card">
        <h3>3. Số lượng & cách chọn câu</h3>
        <div class="row">
          <div class="seg">${(isPassage ? [1, 2, 3] : [10, 20, 30]).map(n => `<button class="${count === n ? 'active' : ''}" data-n="${n}">${n} ${isPassage ? 'đoạn' : 'câu'}</button>`).join('')}</div>
          <div class="seg">
            <button class="${strategy === 'mixed' ? 'active' : ''}" data-st="mixed" title="Ưu tiên câu chưa làm và câu hay sai">Thông minh</button>
            <button class="${strategy === 'unseen' ? 'active' : ''}" data-st="unseen">Chưa làm</button>
            <button class="${strategy === 'wrong' ? 'active' : ''}" data-st="wrong">Từng sai</button>
          </div>
        </div>
        ${bCount ? `<label class="check mt" style="display:flex"><input type="checkbox" id="incB" ${includeB ? 'checked' : ''}> <span class="small">Gồm cả nguồn luyện tập tự sinh (${bCount.toLocaleString('vi')} câu, độ khó không đều) — bỏ chọn nếu chỉ muốn câu lấy từ đề mô phỏng</span></label>` : ''}
        <p class="small muted mt" style="margin-bottom:0">Kho hiện có ${poolSize.toLocaleString('vi')} câu cho các dạng đã chọn.</p>
      </div>
      <button class="btn btn-primary btn-lg mt" id="start" ${!selected.size ? 'disabled' : ''}>Bắt đầu</button>`;

    $$('[data-s]', app).forEach(b => b.onclick = () => { section = b.dataset.s; count = TYPES[[...selected][0]]?.passage ? 2 : 10; draw(); });
    $$('[data-t]', app).forEach(c => c.onchange = () => {
      if (c.checked) selected.add(c.dataset.t); else selected.delete(c.dataset.t);
      // không trộn dạng có đoạn văn với dạng không có
      const wantPassage = TYPES[c.dataset.t].passage;
      if (c.checked) for (const t of [...selected]) if (!!TYPES[t].passage !== !!wantPassage) selected.delete(t);
      count = wantPassage ? 2 : (count <= 3 ? 10 : count);
      draw();
    });
    $$('[data-n]', app).forEach(b => b.onclick = () => { count = Number(b.dataset.n); draw(); });
    $$('[data-st]', app).forEach(b => b.onclick = () => { strategy = b.dataset.st; draw(); });
    $('#incB', app)?.addEventListener('change', (e) => { includeB = e.target.checked; store.setSetting('drillIncludeB', includeB); draw(); });
    $('#discard', app)?.addEventListener('click', () => { store.deleteSession(DRILL_KEY); draw(); });
    $('#start', app).onclick = () => {
      const types = [...selected];
      const qids = isPassage ? composePassageDrill({ types, count, statsOf: store.statOf, includeB }) : composeDrill({ types, count, strategy, statsOf: store.statOf, includeB });
      if (!qids.length) { toast('Không có câu phù hợp. Thử đổi cách chọn câu.'); return; }
      store.saveSession({ id: DRILL_KEY, title: `Luyện nhanh · ${types.map(typeLabel).join(', ')}`, types, qids, includeB, items: toItems(qids), answers: {}, idx: 0, startedAt: Date.now(), updatedAt: Date.now(), finished: false, lastAt: Date.now() });
      navigate('#/drill/run');
    };
  };
  draw();
}

function typeStats(t, stats) {
  let n = 0, c = 0;
  for (const q of questionsOfType(t)) { const s = stats[q.id]; if (s) { n += s.n; c += s.c; } }
  return { n, c };
}

function runPage(app) {
  const d = store.getSession(DRILL_KEY);
  if (!d) { navigate('#/drill'); return; }
  const save = () => { d.updatedAt = Date.now(); store.saveSession(d); };

  const draw = () => {
    if (d.idx >= d.items.length) return drawSummary();
    const item = d.items[d.idx];
    let before = 0; for (let i = 0; i < d.idx; i++) before += d.items[i].qids.length;
    const allAnswered = item.qids.every(q => d.answers[q] != null);
    const done = Object.keys(d.answers).length;

    app.innerHTML = `
      <div class="test-bar">
        <div><div class="small muted">${esc(d.title)}</div><b>Câu ${before + 1}${item.qids.length > 1 ? `–${before + item.qids.length}` : ''} / ${d.qids.length}</b></div>
        <div class="row"><span class="small muted">Đúng ${countCorrect()}/${done}</span><a class="btn btn-sm" href="#/drill" id="quit">Dừng</a></div>
        <div class="progress-line"><i style="width:${pct(done, d.qids.length)}%"></i></div>
      </div>
      <div id="item"></div>
      <div class="pager"><span></span><button class="btn btn-primary btn-lg" id="next" ${allAnswered ? '' : 'disabled'}>${d.idx < d.items.length - 1 ? 'Câu tiếp →' : 'Xem kết quả'}</button></div>`;

    const mount = () => {
      const el = $('#item', app); el.innerHTML = '';
      const reveal = item.qids.every(q => d.answers[q] != null);
      el.appendChild(renderItem(item, {
        startIndex: before + 1, answers: d.answers, reveal, interactive: !reveal,
        onSelect: (qid, idx) => {
          if (d.answers[qid] != null) return;
          d.answers[qid] = idx;
          const q = getQ(qid);
          const ok = idx === q.answer;
          const now = Date.now();
          store.recordAnswer(qid, ok, { mode: 'drill', secs: Math.min(300, (now - (d.lastAt || now)) / 1000) });
          d.lastAt = now; save();
          document.dispatchEvent(new CustomEvent('srs-changed'));
          if (item.qids.every(q2 => d.answers[q2] != null)) { mount(); $('#next', app).disabled = false; $('#next', app).focus(); }
        },
      }));
    };
    mount();
    $('#next', app).onclick = () => { d.idx++; d.lastAt = Date.now(); save(); draw(); window.scrollTo({ top: 0 }); };
    document.onkeydown = (e) => {
      if (e.target.matches('input,textarea,select')) return;
      if (e.key === 'Enter' && !$('#next', app).disabled) $('#next', app).click();
      if (/^[1-4]$/.test(e.key) && item.qids.length === 1) $(`#item .opt[data-i="${Number(e.key) - 1}"]:not(:disabled)`, app)?.click();
    };
  };

  const countCorrect = () => d.qids.filter(q => d.answers[q] != null && d.answers[q] === getQ(q)?.answer).length;

  const drawSummary = () => {
    const c = countCorrect(), n = d.qids.length;
    if (!d.finished) {
      d.finished = true; save();
      const byType = {}, bySection = {};
      for (const qid of d.qids) { const q = getQ(qid); if (!q) continue; const ok = d.answers[qid] === q.answer;
        (byType[q.type] ||= { c: 0, n: 0 }).n++; if (ok) byType[q.type].c++;
        (bySection[q.section] ||= { c: 0, n: 0 }).n++; if (ok) bySection[q.section].c++; }
      store.addHistory({ id: uid(), t: Date.now(), mode: 'drill', kind: 'drill', title: d.title, examId: null,
        papers: [{ id: 'drill', qids: d.qids, answers: d.answers, elapsed: Math.round((Date.now() - d.startedAt) / 1000) }],
        score: { correct: c, total: n }, bySection, byType, secs: Math.round((Date.now() - d.startedAt) / 1000) });
    }
    const wrong = d.qids.filter(q => d.answers[q] !== getQ(q)?.answer);
    app.innerHTML = `
      <div class="card" style="max-width:720px;margin:1rem auto">
        <h1>Xong! ${c}/${n} câu đúng (${pct(c, n)}%)</h1>
        <p class="muted">${fmtDuration((Date.now() - d.startedAt) / 1000)} · ${wrong.length ? `${wrong.length} câu sai đã được thêm vào lịch "Xem sau".` : 'Không sai câu nào 🎉'}</p>
        <div class="row">
          <button class="btn btn-primary" id="again">Làm bộ mới cùng dạng</button>
          <a class="btn" href="#/drill">Chọn dạng khác</a>
          <a class="btn" href="#/review">Xem sau</a>
        </div>
      </div>
      ${wrong.length ? `<h2>Chữa lại câu sai</h2><div id="wrong"></div>` : ''}`;
    if (wrong.length) { const el = $('#wrong', app); let i = 1; for (const item of toItems(wrong)) { el.appendChild(renderItem(item, { startIndex: i, answers: d.answers, reveal: true, interactive: false })); i += item.qids.length; } }
    $('#again', app).onclick = () => {
      const isPassage = d.types.some(t => TYPES[t].passage);
      const qids = isPassage ? composePassageDrill({ types: d.types, count: d.items.length, statsOf: store.statOf, includeB: d.includeB !== false }) : composeDrill({ types: d.types, count: d.qids.length, strategy: 'mixed', statsOf: store.statOf, exclude: new Set(d.qids), includeB: d.includeB !== false });
      if (!qids.length) { toast('Hết câu mới cho dạng này.'); return; }
      store.saveSession({ ...d, qids, items: toItems(qids), answers: {}, idx: 0, startedAt: Date.now(), finished: false, lastAt: Date.now() });
      draw(); window.scrollTo({ top: 0 });
    };
    document.onkeydown = null;
  };

  draw();
  return () => { document.onkeydown = null; };
}
