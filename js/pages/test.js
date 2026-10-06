/* ---------- Mock test: setup, run, result ---------- */
import { $, $$, esc, uid, pct, fmtTime, fmtDate, fmtDuration, toast, confirmDialog } from '../util.js';
import * as store from '../store.js';
import { PAPERS, SECTIONS, TYPES, paperOf, getQ, toItems, composeSection, loadExams, getExam, questionsOf, typeLabel, bankStats } from '../data.js';
import { renderItem, renderQuestion, renderPassage, sectionPill } from '../question.js';
import { ring } from '../charts.js';
import { navigate } from '../app.js';

export async function render(app, route) {
  const [sub, id] = route.segs;
  if (sub === 'run' && id) return runPage(app, id);
  if (sub === 'result' && id) return resultPage(app, id);
  return setupPage(app, route.params);
}

/* ================= SETUP ================= */
async function setupPage(app, params) {
  const exams = await loadExams();
  const sessions = store.listSessions();
  const stats = bankStats();
  let mode = params.mode || 'strict';
  let scope = params.scope || 'full';      // full | moji | bunpo_dokkai | choukai
  let source = 'random';                   // random | <examId>

  const draw = () => {
    const availableExams = exams.filter(e => {
      const need = scope === 'full' ? ['moji', 'bunpo', 'dokkai', 'choukai'] : paperOf(scope).sections;
      return need.every(s => (e.parts[s] || []).length > 0);
    });
    if (source !== 'random' && !availableExams.find(e => e.id === source)) source = 'random';
    const paper = scope === 'full' ? null : paperOf(scope);
    const minutes = scope === 'full' ? PAPERS.reduce((a, p) => a + p.minutes, 0) : paper.minutes;
    const nQ = scope === 'full' ? 102 : paper.sections.reduce((a, s) => a + Object.values(TYPES).filter(t => t.section === s).reduce((x, t) => x + t.count, 0), 0);

    app.innerHTML = `
      <h1>Thi thử</h1>
      <p class="muted">Cấu trúc đề N3 thật: 文字・語彙 30 phút · 文法・読解 70 phút · 聴解 40 phút.</p>

      ${sessions.length ? `<div class="card" style="border-color:var(--primary)">
        <div class="card-title"><h2>Bài đang làm dở</h2></div>
        ${sessions.map(ss => `<div class="row between" style="padding:.4rem 0;border-top:1px solid var(--border)">
          <div><b>${esc(ss.title)}</b> <span class="pill">${ss.mode === 'strict' ? 'Có giờ' : 'Không giờ'}</span> <span class="small muted">${fmtDate(ss.updatedAt, true)}</span></div>
          <div class="row"><a class="btn btn-primary btn-sm" href="#/test/run/${esc(ss.id)}">Tiếp tục</a><button class="btn btn-sm btn-danger" data-del="${esc(ss.id)}">Huỷ</button></div>
        </div>`).join('')}</div>` : ''}

      <div class="card">
        <h3>1. Chế độ</h3>
        <div class="seg" role="tablist">
          <button class="${mode === 'strict' ? 'active' : ''}" data-mode="strict">⏱ Strict · có giờ</button>
          <button class="${mode === 'normal' ? 'active' : ''}" data-mode="normal">☕ Normal · không giờ</button>
        </div>
        <p class="small muted mt" style="margin-bottom:0">${mode === 'strict'
          ? 'Hết giờ tự nộp phần đó. Giống thi thật, nên làm vào cuối tuần khi có 2–2,5 tiếng liền.'
          : 'Không đếm ngược, có thể thoát và làm tiếp sau. Chỉ làm từng phần. Hợp với lúc bận.'}</p>
      </div>

      <div class="card">
        <h3>2. Phạm vi</h3>
        <div class="seg">
          ${mode === 'strict' ? `<button class="${scope === 'full' ? 'active' : ''}" data-scope="full">Đề đầy đủ (3 phần)</button>` : ''}
          ${PAPERS.map(p => `<button class="${scope === p.id ? 'active' : ''}" data-scope="${p.id}">${esc(p.jp)}</button>`).join('')}
        </div>
        <p class="small muted mt" style="margin-bottom:0">~${nQ} câu${mode === 'strict' ? ` · ${minutes} phút` : ''}.</p>
      </div>

      <div class="card">
        <h3>3. Nguồn đề</h3>
        <label class="field"><span>Chọn đề</span>
          <select class="input" id="exam-src">
            <option value="random" ${source === 'random' ? 'selected' : ''}>🎲 Đề ngẫu nhiên từ ngân hàng (${stats.total.toLocaleString('vi')} câu, ưu tiên câu chưa làm/hay sai)</option>
            ${[['Đề thi thật các năm', availableExams.filter(e => e.official)], ['Đề luyện / mô phỏng', availableExams.filter(e => !e.official)]]
              .filter(([, list]) => list.length)
              .map(([label, list]) => `<optgroup label="${label} (${list.length})">${list.map(e => `<option value="${esc(e.id)}" ${source === e.id ? 'selected' : ''}>${esc(e.name)} · ${examCount(e, scope)} câu${store.get().history.some(h => h.examId === e.id) ? ' ✓ đã làm' : ''}</option>`).join('')}</optgroup>`).join('')}
          </select>
        </label>
        <p class="small muted" style="margin-bottom:0">${availableExams.length} bộ đề có sẵn cho phạm vi này. Đề ngẫu nhiên được ghép đúng tỉ lệ 問題 của JLPT N3.</p>
      </div>

      <div class="row mt">
        <button class="btn btn-primary btn-lg" id="start">Bắt đầu${mode === 'strict' ? ` · ${minutes} phút` : ''}</button>
        <span class="small muted">Có thể thoát giữa chừng; bài được lưu tự động.</span>
      </div>`;

    $$('[data-mode]', app).forEach(b => b.onclick = () => { mode = b.dataset.mode; if (mode === 'normal' && scope === 'full') scope = 'moji'; draw(); });
    $$('[data-scope]', app).forEach(b => b.onclick = () => { scope = b.dataset.scope; draw(); });
    $('#exam-src', app).onchange = (e) => { source = e.target.value; };
    $$('[data-del]', app).forEach(b => b.onclick = async () => {
      if (await confirmDialog({ title: 'Huỷ bài đang làm?', body: 'Các câu đã trả lời trong bài này sẽ mất.', ok: 'Huỷ bài', danger: true })) { store.deleteSession(b.dataset.del); draw(); }
    });
    $('#start', app).onclick = async () => {
      const session = await createSession({ mode, scope, source, exams });
      if (!session) return;
      store.saveSession(session);
      navigate(`#/test/run/${session.id}`);
    };
  };
  draw();
}

function examCount(e, scope) {
  const secs = scope === 'full' ? ['moji', 'bunpo', 'dokkai', 'choukai'] : paperOf(scope).sections;
  return secs.reduce((a, s) => a + (e.parts[s] || []).length, 0);
}

async function createSession({ mode, scope, source, exams }) {
  const papers = scope === 'full' ? PAPERS : [paperOf(scope)];
  const exam = source !== 'random' ? exams.find(e => e.id === source) : null;
  const sessPapers = [];
  for (const p of papers) {
    let qids = [];
    for (const s of p.sections) {
      if (exam) qids.push(...(exam.parts[s] || []).filter(id => getQ(id)));
      else qids.push(...composeSection(s, { statsOf: store.statOf }));
    }
    if (!qids.length) { toast(`Chưa có câu hỏi cho phần ${p.jp}`); return null; }
    sessPapers.push({ id: p.id, qids, items: toItems(qids), answers: {}, flags: {}, elapsed: 0, done: false, limit: mode === 'strict' ? p.minutes * 60 : null });
  }
  const title = (exam ? exam.name : 'Đề ngẫu nhiên') + (scope === 'full' ? ' · Đề đầy đủ' : ' · ' + paperOf(scope).jp);
  return { id: uid(), mode, scope, examId: exam?.id || null, title, papers: sessPapers, paperIdx: 0, itemIdx: 0, createdAt: Date.now(), updatedAt: Date.now(), started: false };
}

/* ================= RUN ================= */
async function runPage(app, id) {
  const session = store.getSession(id);
  if (!session) { app.innerHTML = `<div class="card"><h2>Không tìm thấy bài</h2><p>Bài này đã nộp hoặc bị huỷ.</p><a class="btn" href="#/test">Về Thi thử</a></div>`; return; }

  let timer = null, lastTick = null;
  const save = () => { session.updatedAt = Date.now(); store.saveSession(session); };
  const stop = () => { clearInterval(timer); timer = null; lastTick = null; };

  const paper = () => session.papers[session.paperIdx];
  const paperDef = () => paperOf(paper().id);

  const drawIntro = () => {
    stop();
    const p = paper(), def = paperDef();
    const first = session.paperIdx === 0;
    app.innerHTML = `
      <div class="card" style="max-width:640px;margin:2rem auto">
        <p class="muted small" style="margin:0">${esc(session.title)} · phần ${session.paperIdx + 1}/${session.papers.length}</p>
        <h1 class="ja">${esc(def.jp)}</h1>
        <p>${esc(def.label)} · <b>${p.qids.length} câu</b>${p.limit ? ` · <b>${Math.round(p.limit / 60)} phút</b>` : ' · không giới hạn thời gian'}</p>
        ${def.sections.includes('choukai') ? '<p class="small muted">Chuẩn bị tai nghe. Trong thi thật mỗi bài nghe chỉ phát 1 lần; hãy cố gắng chỉ nghe 1 lần.</p>' : ''}
        ${p.limit ? '<p class="small muted">Đồng hồ bắt đầu chạy khi bạn bấm Bắt đầu. Hết giờ phần này sẽ tự nộp.</p>' : ''}
        <div class="row mt">
          <button class="btn btn-primary btn-lg" id="go">${first && !session.started ? 'Bắt đầu' : 'Bắt đầu phần này'}</button>
          <a class="btn" href="#/test">Để sau</a>
        </div>
      </div>`;
    $('#go', app).onclick = () => { session.started = true; p.startedAt = p.startedAt || Date.now(); session.itemIdx = 0; save(); drawRun(); };
  };

  const drawRun = () => {
    const p = paper(), def = paperDef();
    const items = p.items;
    const item = items[session.itemIdx];
    let numberBefore = 0;
    for (let i = 0; i < session.itemIdx; i++) numberBefore += items[i].qids.length;
    const answered = Object.keys(p.answers).length;

    app.innerHTML = `
      <div class="test-bar">
        <div>
          <div class="small muted">${esc(session.title)}</div>
          <b class="ja">${esc(def.jp)}</b> <span class="small muted">· câu ${numberBefore + 1}${item.qids.length > 1 ? `–${numberBefore + item.qids.length}` : ''} / ${p.qids.length}</span>
        </div>
        <div class="row">
          <span class="timer" id="timer">${p.limit ? fmtTime(p.limit - p.elapsed) : fmtTime(p.elapsed)}</span>
          <button class="btn btn-sm" id="toggle-nav">Danh sách</button>
          <button class="btn btn-sm btn-primary" id="submit">Nộp phần này</button>
        </div>
        <div class="progress-line"><i style="width:${pct(answered, p.qids.length)}%"></i></div>
      </div>
      <div class="card tight mb" id="nav-panel" hidden>
        <div class="navigator">${p.qids.map((qid, i) => `<button class="${p.answers[qid] != null ? 'done' : ''} ${p.flags[qid] ? 'flag' : ''} ${item.qids.includes(qid) ? 'cur' : ''}" data-q="${i}">${i + 1}</button>`).join('')}</div>
        <p class="small muted" style="margin:.5rem 0 0">Đã trả lời ${answered}/${p.qids.length}. Ô có vạch vàng = đánh dấu xem lại.</p>
      </div>
      <div id="item"></div>
      <div class="pager">
        <button class="btn" id="prev" ${session.itemIdx === 0 ? 'disabled' : ''}>← Trước</button>
        <div class="row">
          <button class="btn" id="mark">${item.qids.some(q => p.flags[q]) ? '🚩 Bỏ đánh dấu' : '🏳 Đánh dấu xem lại'}</button>
          ${session.itemIdx < items.length - 1 ? '<button class="btn btn-primary" id="next">Tiếp →</button>' : '<button class="btn btn-primary" id="finish">Xem lại & nộp</button>'}
        </div>
      </div>`;

    $('#item', app).appendChild(renderItem(item, {
      startIndex: numberBefore + 1, answers: p.answers, interactive: true,
      onSelect: (qid, idx) => { p.answers[qid] = idx; save(); refreshBar(); },
    }));

    const refreshBar = () => {
      const a = Object.keys(p.answers).length;
      $('.progress-line i', app).style.width = pct(a, p.qids.length) + '%';
    };
    $('#toggle-nav', app).onclick = () => { const n = $('#nav-panel', app); n.hidden = !n.hidden; };
    $$('#nav-panel button', app).forEach(b => b.onclick = () => {
      const qi = Number(b.dataset.q);
      let acc = 0;
      for (let i = 0; i < items.length; i++) { if (qi < acc + items[i].qids.length) { session.itemIdx = i; break; } acc += items[i].qids.length; }
      save(); drawRun();
    });
    $('#prev', app).onclick = () => { session.itemIdx--; save(); drawRun(); };
    $('#next', app)?.addEventListener('click', () => { session.itemIdx++; save(); drawRun(); });
    $('#finish', app)?.addEventListener('click', () => { $('#nav-panel', app).hidden = false; window.scrollTo({ top: 0, behavior: 'smooth' }); toast('Kiểm tra lại các ô trống rồi bấm "Nộp phần này"'); });
    $('#mark', app).onclick = () => { const on = !item.qids.some(q => p.flags[q]); item.qids.forEach(q => { if (on) p.flags[q] = 1; else delete p.flags[q]; }); save(); drawRun(); };
    $('#submit', app).onclick = async () => {
      const blank = p.qids.length - Object.keys(p.answers).length;
      const ok = await confirmDialog({ title: 'Nộp phần này?', body: blank ? `<p>Còn <b>${blank}</b> câu chưa trả lời. Câu bỏ trống tính là sai.</p>` : '<p>Bạn đã trả lời hết. Nộp bài phần này?</p>', ok: 'Nộp' });
      if (ok) submitPaper();
    };

    // timer
    stop();
    lastTick = Date.now();
    const timerEl = $('#timer', app);
    timer = setInterval(() => {
      const now = Date.now();
      p.elapsed += (now - lastTick) / 1000; lastTick = now;
      if (p.limit) {
        const left = p.limit - p.elapsed;
        timerEl.textContent = fmtTime(left);
        timerEl.classList.toggle('low', left < 300);
        if (left <= 0) { stop(); toast('Hết giờ! Tự động nộp phần này.'); submitPaper(); return; }
      } else timerEl.textContent = fmtTime(p.elapsed);
      if (Math.floor(p.elapsed) % 10 === 0) save();
    }, 1000);

    // keyboard: 1-4 chọn đáp án câu đầu của trang, ← → chuyển trang
    document.onkeydown = (e) => {
      if (e.target.matches('input,textarea,select')) return;
      if (e.key === 'ArrowRight' && $('#next', app)) $('#next', app).click();
      if (e.key === 'ArrowLeft' && !$('#prev', app).disabled) $('#prev', app).click();
      if (/^[1-4]$/.test(e.key) && item.qids.length === 1) $(`#item .opt[data-i="${Number(e.key) - 1}"]`, app)?.click();
    };
  };

  const submitPaper = () => {
    stop();
    const p = paper();
    p.done = true; p.finishedAt = Date.now();
    if (session.paperIdx < session.papers.length - 1) { session.paperIdx++; session.itemIdx = 0; save(); drawIntro(); }
    else finishSession();
  };

  const finishSession = () => {
    const entry = gradeSession(session);
    store.addHistory(entry);
    store.deleteSession(session.id);
    document.onkeydown = null;
    navigate(`#/test/result/${entry.id}`);
  };

  if (!session.started || !paper().startedAt) drawIntro(); else drawRun();
  return () => { stop(); document.onkeydown = null; };
}

function gradeSession(session) {
  const bySection = {}, byType = {};
  let correct = 0, total = 0, secs = 0;
  const papers = session.papers.map(p => {
    const perQ = p.qids.length ? p.elapsed / p.qids.length : 0;
    for (const qid of p.qids) {
      const q = getQ(qid); if (!q) continue;
      const ok = p.answers[qid] === q.answer;
      total++; if (ok) correct++;
      const s = bySection[q.section] || (bySection[q.section] = { c: 0, n: 0 }); s.n++; if (ok) s.c++;
      const t = byType[q.type] || (byType[q.type] = { c: 0, n: 0 }); t.n++; if (ok) t.c++;
      store.recordAnswer(qid, ok, { mode: session.mode, secs: perQ });
    }
    secs += p.elapsed;
    return { id: p.id, qids: p.qids, answers: p.answers, elapsed: Math.round(p.elapsed), limit: p.limit };
  });
  return { id: uid(), t: Date.now(), mode: session.mode, kind: session.scope === 'full' ? 'full' : 'paper', scope: session.scope, title: session.title, examId: session.examId,
    papers, score: { correct, total }, bySection, byType, secs: Math.round(secs) };
}

/* ================= RESULT ================= */
async function resultPage(app, id) {
  const h = store.getHistory(id);
  if (!h) { app.innerHTML = `<div class="card"><h2>Không tìm thấy kết quả</h2><a class="btn" href="#/progress">Xem lịch sử</a></div>`; return; }
  const overall = pct(h.score.correct, h.score.total);

  // JLPT-style estimate: 言語知識(moji+bunpo) / 読解 / 聴解, mỗi phần 60 điểm, đỗ ≥95/180 & mỗi phần ≥19
  const est = {};
  const lk = { c: (h.bySection.moji?.c || 0) + (h.bySection.bunpo?.c || 0), n: (h.bySection.moji?.n || 0) + (h.bySection.bunpo?.n || 0) };
  if (lk.n) est['Kiến thức ngôn ngữ'] = Math.round(60 * lk.c / lk.n);
  if (h.bySection.dokkai?.n) est['Đọc hiểu'] = Math.round(60 * h.bySection.dokkai.c / h.bySection.dokkai.n);
  if (h.bySection.choukai?.n) est['Nghe hiểu'] = Math.round(60 * h.bySection.choukai.c / h.bySection.choukai.n);
  const estTotal = Object.values(est).reduce((a, b) => a + b, 0);
  const full = Object.keys(est).length === 3;

  const types = Object.entries(h.byType).sort((a, b) => (TYPES[a[0]]?.mondai || 99) - (TYPES[b[0]]?.mondai || 99));
  let filter = 'all';

  app.innerHTML = `
    <div class="row between">
      <div><h1 style="margin-bottom:.1em">Kết quả</h1><p class="muted" style="margin:0">${esc(h.title)} · ${fmtDate(h.t, true)} · ${h.mode === 'strict' ? 'có giờ' : 'không giờ'} · ${fmtDuration(h.secs)}</p></div>
      <div class="row"><a class="btn" href="#/test">Làm đề khác</a><a class="btn" href="#/progress">Tiến độ</a></div>
    </div>
    <div class="card mt">
      <div class="score-hero">
        <div id="ring"></div>
        <div style="flex:1;min-width:220px">
          <div class="hero-num">${h.score.correct}<span class="muted" style="font-size:1.2rem"> / ${h.score.total} câu</span></div>
          <div class="grid-tiles mt">
            ${Object.keys(SECTIONS).filter(s => h.bySection[s]).map(s => `<div class="tile"><div class="label">${sectionPill(s)}</div><div class="value">${pct(h.bySection[s].c, h.bySection[s].n)}%</div><div class="sub">${h.bySection[s].c}/${h.bySection[s].n}</div></div>`).join('')}
          </div>
        </div>
      </div>
      ${Object.keys(est).length ? `<p class="small muted mt" style="margin-bottom:0">Ước tính điểm JLPT (quy đổi tuyến tính, chỉ để tham khảo): ${Object.entries(est).map(([k, v]) => `${k} <b>${v}/60</b>`).join(' · ')}${full ? ` → tổng <b>${estTotal}/180</b> ${estTotal >= 95 && Object.values(est).every(v => v >= 19) ? '<span class="pill good">Đạt</span>' : '<span class="pill bad">Chưa đạt (cần ≥95 và mỗi phần ≥19)</span>'}` : ''}</p>` : ''}
    </div>

    <div class="card">
      <h3>Theo dạng bài</h3>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Dạng</th><th class="num">Đúng</th><th style="width:40%">Tỉ lệ</th></tr></thead><tbody>
        ${types.map(([t, v]) => { const p = pct(v.c, v.n); return `<tr><td>${esc(typeLabel(t))}</td><td class="num">${v.c}/${v.n}</td><td><div class="meter ${p >= 75 ? 'good' : p >= 55 ? 'warn' : 'bad'}"><i style="width:${p}%"></i></div></td></tr>`; }).join('')}
      </tbody></table></div>
      ${types.filter(([, v]) => v.n >= 3 && pct(v.c, v.n) < 60).length ? `<p class="small mt" style="margin-bottom:0">Nên luyện thêm: ${types.filter(([, v]) => v.n >= 3 && pct(v.c, v.n) < 60).map(([t]) => `<a href="#/drill?type=${t}">${esc(typeLabel(t))}</a>`).join(' · ')}</p>` : ''}
    </div>

    <h2 class="mt">Chữa bài</h2>
    <div class="filter-row" id="filters">
      <button class="btn btn-sm active" data-f="all">Tất cả (${h.score.total})</button>
      <button class="btn btn-sm" data-f="wrong">Sai (${h.score.total - h.score.correct})</button>
      <button class="btn btn-sm" data-f="right">Đúng (${h.score.correct})</button>
      <button class="btn btn-sm" data-f="flag">Đã lưu Xem sau</button>
    </div>
    <div id="list"></div>`;

  ring($('#ring', app), overall, { label: 'Kết quả' });

  const list = $('#list', app);
  const drawList = () => {
    list.innerHTML = '';
    let n = 0, shown = 0;
    for (const p of h.papers) {
      const def = paperOf(p.id);
      const items = toItems(p.qids);
      const head = document.createElement('h3'); head.className = 'ja mt'; head.textContent = def?.jp || p.id;
      let headAdded = false;
      for (const item of items) {
        const start = n + 1; n += item.qids.length;
        const keep = item.qids.filter(qid => {
          const q = getQ(qid); if (!q) return false;
          const ok = p.answers[qid] === q.answer;
          if (filter === 'wrong') return !ok;
          if (filter === 'right') return ok;
          if (filter === 'flag') return store.isFlagged(qid);
          return true;
        });
        if (!keep.length) continue;
        if (!headAdded) { list.appendChild(head); headAdded = true; }
        shown += keep.length;
        list.appendChild(renderItem({ pid: item.pid, qids: keep }, { startIndex: start, answers: p.answers, reveal: true, interactive: false }));
      }
    }
    if (!shown) list.innerHTML = '<p class="empty">Không có câu nào trong bộ lọc này.</p>';
  };
  $$('#filters button', app).forEach(b => b.onclick = () => { filter = b.dataset.f; $$('#filters button', app).forEach(x => x.classList.toggle('active', x === b)); drawList(); });
  drawList();
}
