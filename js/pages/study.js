/* ---------- Học N2: lộ trình tuần · bài học · 練習 · まとめ問題 ----------
   #/study?t=<track>                 lộ trình của một track
   #/study/lesson/<track>/<unit>     bài học (giải thích + ví dụ + kiểm tra nhanh)
   #/study/do/<activityId>           練習 (chữa ngay từng câu) hoặc まとめ問題 (làm hết rồi nộp)
*/
import { $, $$, esc, pct, fmtDate, fmtTime, toast, shuffle, confirmDialog, todayKey, DAY } from '../util.js';
import * as store from '../store.js';
import {
  loadIndex, loadLesson, scheduleOf, trackStatus, planOf, setPlan, mondayOf, keyToTs, dateOf,
  questionsFor, ja, rich, plain, studySettings, setStudySettings, applyFurigana, WEEKDAYS, TRACK_SHORT,
} from '../study.js';

const LAST_TRACK_KEY = 'jlpt-n2-track';
const DRAFT_KEY = (id) => `jlpt-n2-draft:${id}`;
const LETTERS = ['1', '2', '3', '4'];
const KIND = {
  form: '文法形式の判断', order: '文の組み立て ★', usage: '用法', passage: '文章',
  read: '漢字読み', write: '表記', formation: '語形成', context: '文脈規定', paraphrase: '言い換え類義',
};

export async function render(app, route) {
  applyFurigana();
  const idx = await loadIndex();
  const [sub, a, b] = route.segs;
  let inner;
  if (sub === 'lesson') { app.dataset.track = a; inner = await lessonPage(app, idx, a, b); }
  else if (sub === 'do') { app.dataset.track = decodeURIComponent(a || '').split(':')[0]; inner = await runPage(app, idx, decodeURIComponent(a || ''), route.params); }
  else overview(app, idx, route.params);
  return () => { delete app.dataset.track; if (typeof inner === 'function') inner(); };
}

const trackOf = (idx, id) => idx.tracks.find(t => t.id === id);
const findItem = (idx, id) => {
  const t = trackOf(idx, id.split(':')[0]);
  return t ? scheduleOf(t).find(x => x.id === id) || null : null;
};
const itemHref = (x) => x.type === 'L' ? `#/study/lesson/${x.id.split(':')[0]}/${x.units[0].id}` : `#/study/do/${encodeURIComponent(x.id)}`;
const typeIcon = { L: '📖', P: '✏️', M: '📝' };
const typeName = { L: 'Học kiến thức mới', P: 'Luyện tập 2 bài đã học', M: 'Kiểm tra tổng hợp' };

function scoreText(st) {
  if (!st?.done) return '';
  return st.n ? `${st.c}/${st.n} · ${pct(st.c, st.n)}%` : 'đã học';
}
function scoreCls(st) {
  if (!st?.n) return 'good';
  const p = st.c / st.n;
  return p >= 0.8 ? 'good' : p >= 0.6 ? 'warn' : 'bad';
}

/* ================= Lộ trình ================= */
function overview(app, idx, params) {
  let tid = params.t || localStorage.getItem(LAST_TRACK_KEY) || 'bunpo';
  if (!trackOf(idx, tid)) tid = 'bunpo';
  localStorage.setItem(LAST_TRACK_KEY, tid);
  app.dataset.track = tid;
  const track = trackOf(idx, tid);
  const st = trackStatus(track);
  const todayTs = Date.now();

  const tabs = idx.tracks.map(t => {
    const s = trackStatus(t);
    return `<button class="${t.id === tid ? 'active' : ''}" data-t="${t.id}">${esc(t.title)} <span class="small muted">${pct(s.done, s.total)}%</span></button>`;
  }).join('');

  const readyUnits = track.units.filter(u => u.ready).length;
  const weeks = Math.ceil(track.units.length / 4);

  const plan = st.start ? `
    <div class="row between">
      <div>
        <div><b>Lịch học:</b> bắt đầu ${WEEKDAYS[(new Date(keyToTs(st.start)).getDay() + 6) % 7]} ${fmtDate(keyToTs(st.start))} · ${weeks} tuần · dự kiến xong ${fmtDate(keyToTs(st.start) + (weeks * 7 - 1) * DAY)}</div>
        <div class="small muted">${st.dayNo < 0 ? `Còn ${-st.dayNo} ngày nữa mới bắt đầu.` : st.dayNo >= weeks * 7 ? 'Đã qua hết lịch.' : `Hôm nay là ngày ${st.dayNo + 1} · tuần ${Math.floor(st.dayNo / 7) + 1}/${weeks}.`}
          ${st.behind ? `<span class="pill warn">chậm ${st.behind} buổi</span>` : st.dayNo >= 0 ? '<span class="pill good">đúng lịch</span>' : ''}</div>
      </div>
      <div class="row">
        ${st.behind >= 3 ? '<button class="btn btn-sm" id="shift">Lùi lịch 1 tuần</button>' : ''}
        <button class="btn btn-sm" id="replan">Đổi ngày bắt đầu</button>
      </div>
    </div>` : `
    <p style="margin-top:0">Chọn ngày bắt đầu để app xếp lịch theo tuần: <b>T2 課 · T3 課 · T4 練習 · T5 課 · T6 課 · T7 練習 · CN まとめ問題</b>.
      ${esc(TRACK_SHORT[tid])}: ${track.units.length} bài → ${weeks} tuần.</p>
    <div class="row">
      <button class="btn btn-primary btn-sm" data-start="${mondayOf(todayTs)}">Bắt đầu từ thứ 2 tuần này (${fmtDate(keyToTs(mondayOf(todayTs)))})</button>
      <button class="btn btn-sm" data-start="${mondayOf(todayTs, true)}">Từ thứ 2 tuần sau (${fmtDate(keyToTs(mondayOf(todayTs, true)))})</button>
      <span class="small muted">Chưa đặt lịch vẫn học được, cứ làm lần lượt từng buổi.</span>
    </div>`;

  const next = st.next;
  const today = st.today;
  const todayDone = today && store.studyOf(today.id)?.done;
  const focus = next ? `
    <div class="card today-card">
      <div class="row between">
        <div>
          ${today ? `<div class="small muted">Theo lịch hôm nay (${WEEKDAYS[today.slot]}): <b>${esc(today.label)}</b> ${todayDone ? '· <span class="pill good">đã xong</span>' : ''}</div>` : ''}
          <div class="small muted" style="margin-top:.2rem">${next === today || !today ? 'Buổi cần làm' : todayDone ? 'Học vượt' : 'Buổi tiếp theo (làm lần lượt)'}</div>
          <h2 style="margin:.1rem 0">${typeIcon[next.type]} ${esc(next.label)} <span class="jp">${esc(next.type === 'L' ? next.title : '')}</span></h2>
          <div class="muted">${esc(next.type === 'L' ? (next.units[0].title_vi || '') : next.title)}</div>
        </div>
        ${next.ready ? `<a class="btn btn-primary btn-lg" href="${itemHref(next)}">${next.type === 'L' ? 'Học ngay' : 'Làm bài'}</a>` : '<span class="pill warn">nội dung đang soạn</span>'}
      </div>
    </div>` : `<div class="card today-card"><h2>🎉 Đã hoàn thành toàn bộ ${esc(track.title)}</h2><p class="muted">Làm lại các まとめ問題 có điểm thấp để ôn.</p></div>`;

  const cur = next ? next.week : -1;
  const weekHTML = [];
  for (let w = 0; w < weeks; w++) {
    const items = st.items.filter(x => x.week === w);
    const done = items.filter(x => store.studyOf(x.id)?.done).length;
    const lessons = items.filter(x => x.type === 'L').map(x => x.units[0].label);
    const wStart = st.start ? keyToTs(st.start) + w * 7 * DAY : null;
    weekHTML.push(`
      <details class="week" ${w === cur || (w === cur + 1 && done) ? 'open' : ''}>
        <summary><b>Tuần ${w + 1}</b> <span class="muted">· ${esc(lessons[0])}${lessons.length > 1 ? ' – ' + esc(lessons[lessons.length - 1]) : ''}</span>
          ${wStart ? `<span class="small muted">· ${fmtDate(wStart).slice(0, 5)} – ${fmtDate(wStart + 6 * DAY).slice(0, 5)}</span>` : ''}
          <span class="pill ${done === items.length ? 'good' : ''}">${done}/${items.length}</span></summary>
        <div class="week-rows">${items.map(x => rowHTML(x, st.start)).join('')}</div>
      </details>`);
  }

  app.innerHTML = `
    <div class="row between mb study-hero">
      <div>
        <h1 style="margin-bottom:.1em">Học N2 <span class="jp muted" style="font-size:.7em">新完全マスター</span></h1>
        <p class="muted" style="margin:0">Học theo bài của sách, giải thích tiếng Việt chi tiết, ví dụ và bài tập tự soạn. Mỗi tuần 4 bài + 2 buổi 練習 + 1 まとめ問題.</p>
      </div>
      <label class="check small"><input type="checkbox" id="furi" ${studySettings().furigana !== false ? 'checked' : ''}> Hiện furigana</label>
    </div>
    <div class="seg track-tabs">${tabs}</div>
    <div class="card mt">${plan}</div>
    ${focus}
    <div class="row between mt"><h2 style="margin:0">Lộ trình ${esc(track.title)}</h2>
      <span class="small muted">${esc(track.book)} · ${readyUnits}/${track.units.length} bài đã có nội dung</span></div>
    <div class="weeks">${weekHTML.join('')}</div>
    <div class="card mt">
      <h3>Tra nhanh trong khoá N2</h3>
      <input class="input" id="q" placeholder="Gõ mẫu ngữ pháp / từ / kỹ năng, vd: 際, ものの, 対比…" autocomplete="off">
      <div id="qres" class="stack mt"></div>
    </div>`;

  $$('[data-t]', app).forEach(b => b.onclick = () => { localStorage.setItem(LAST_TRACK_KEY, b.dataset.t); location.hash = `#/study?t=${b.dataset.t}`; });
  $$('[data-start]', app).forEach(b => b.onclick = () => { setPlan(tid, b.dataset.start); overview(app, idx, { t: tid }); });
  $('#replan', app)?.addEventListener('click', () => replanDialog(app, idx, tid));
  $('#shift', app)?.addEventListener('click', () => {
    setPlan(tid, todayKey(new Date(keyToTs(st.start) + 7 * DAY)));
    toast('Đã lùi lịch 1 tuần');
    overview(app, idx, { t: tid });
  });
  $('#furi', app).onchange = (e) => { setStudySettings({ furigana: e.target.checked }); applyFurigana(); };
  const qi = $('#q', app), qr = $('#qres', app);
  qi.oninput = () => {
    const s = qi.value.trim().replace(/[〜～~]/g, '');
    if (!s) { qr.innerHTML = ''; return; }
    const hits = [];
    for (const t of idx.tracks) for (const u of t.units) {
      const its = (u.items || []).filter(i => plain(i).includes(s));
      if (its.length || plain(u.title).includes(s) || (u.title_vi || '').toLowerCase().includes(s.toLowerCase()))
        hits.push({ t, u, its });
    }
    qr.innerHTML = hits.slice(0, 20).map(({ t, u, its }) => `
      <a class="ref-item" href="#/study/lesson/${t.id}/${u.id}" style="display:block">
        <span class="pill">${esc(TRACK_SHORT[t.id])}</span> <b>${esc(u.label)}</b> <span class="jp">${esc(u.title)}</span>
        ${its.length ? `<div class="small jp">${its.slice(0, 6).map(esc).join('　')}</div>` : ''}
        ${u.ready ? '' : '<span class="small muted"> · đang soạn</span>'}
      </a>`).join('') || '<p class="small muted">Không thấy.</p>';
  };
}

function rowHTML(x, start) {
  const st = store.studyOf(x.id);
  const d = dateOf(x, start);
  const isToday = d && todayKey(new Date(d)) === todayKey();
  const late = d && !st?.done && d < Date.now() - DAY / 2 && !isToday;
  const unitTitle = x.type === 'L' ? `<span class="jp">${esc(x.units[0].title)}</span> <span class="small muted">${esc(x.units[0].title_vi || '')}</span>` : `<span class="small muted">${esc(x.title)}</span>`;
  const inner = `
      <span class="wd ${isToday ? 'today' : ''}">${WEEKDAYS[x.slot]}${d ? `<br><span class="small">${fmtDate(d).slice(0, 5)}</span>` : ''}</span>
      <span class="act-type t-${x.type}">${typeIcon[x.type]}</span>
      <span class="act-body"><b>${esc(x.label)}</b> ${unitTitle}</span>
      <span class="act-state">${st?.done ? `<span class="pill ${scoreCls(st)}">✓ ${esc(scoreText(st))}</span>` : late ? '<span class="pill warn">chưa làm</span>' : isToday ? '<span class="pill">hôm nay</span>' : ''}
        ${x.ready ? '' : '<span class="small muted">đang soạn</span>'}</span>`;
  return x.ready
    ? `<a class="act-row ${st?.done ? 'done' : ''} ${isToday ? 'is-today' : ''}" href="${itemHref(x)}">${inner}</a>`
    : `<div class="act-row disabled">${inner}</div>`;
}

function replanDialog(app, idx, tid) {
  const root = $('#modal-root');
  const cur = planOf(tid) || mondayOf();
  root.innerHTML = `<div class="modal-back" role="dialog" aria-modal="true"><div class="modal">
    <h3>Ngày bắt đầu lộ trình ${esc(TRACK_SHORT[tid])}</h3>
    <p class="small muted">Nên chọn một ngày thứ 2 để T2 = 課 đầu tuần, CN = まとめ問題. Đổi ngày không xoá kết quả đã làm.</p>
    <input type="date" class="input" id="pd" value="${esc(cur)}">
    <div class="row mt" style="justify-content:flex-end">
      <button class="btn btn-danger btn-sm" id="pclear">Bỏ lịch</button>
      <button class="btn" id="pcancel">Huỷ</button>
      <button class="btn btn-primary" id="pok">Lưu</button>
    </div></div></div>`;
  const close = () => { root.innerHTML = ''; };
  $('#pcancel').onclick = close;
  $('#pclear').onclick = () => { setPlan(tid, null); close(); overview(app, idx, { t: tid }); };
  $('#pok').onclick = () => {
    const v = $('#pd').value;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) { toast('Ngày không hợp lệ'); return; }
    if (new Date(v + 'T12:00:00').getDay() !== 1) toast('Lưu ý: ngày này không phải thứ 2, lịch sẽ lệch thứ trong tuần');
    setPlan(tid, v); close(); overview(app, idx, { t: tid });
  };
}

/* ================= Bài học ================= */
async function lessonPage(app, idx, tid, uid) {
  const track = trackOf(idx, tid);
  const unit = track?.units.find(u => u.id === uid);
  if (!unit) throw new Error('Không có bài này');
  const L = await loadLesson(tid, uid);
  const items = scheduleOf(track);
  const item = items.find(x => x.type === 'L' && x.units[0].id === uid);
  const st = store.studyOf(item.id);
  const pos = unit ? track.units.indexOf(unit) : -1;
  const prevU = track.units[pos - 1], nextU = track.units[pos + 1];

  let body = '';
  if (tid === 'bunpo') body = grammarBody(L);
  else if (tid === 'goi') body = vocabBody(L);
  else body = readingBody(L);

  app.innerHTML = `
    <div class="lesson-bar">
      <a href="#/study?t=${tid}" class="btn btn-sm btn-ghost">← Lộ trình</a>
      <span class="small muted">${esc(track.title)} · ${esc(unit.part || '')}</span>
      <span class="spacer"></span>
      <label class="check small"><input type="checkbox" id="furi" ${studySettings().furigana !== false ? 'checked' : ''}> Furigana</label>
      <label class="check small" title="Che nghĩa / bản dịch để tự kiểm tra, bấm vào chỗ bị che để xem"><input type="checkbox" id="hidevi"> Che nghĩa</label>
    </div>
    <header class="lesson-head">
      <div class="small muted">${typeIcon.L} ${esc(unit.label)} · ${WEEKDAYS[item.slot]} tuần ${item.week + 1}${st?.done ? ` · <span class="pill ${scoreCls(st)}">✓ ${esc(scoreText(st))}</span>` : ''}</div>
      <h1 class="jp">${esc(unit.title)}</h1>
      <p class="muted" style="margin:0">${esc(unit.title_vi || '')}</p>
    </header>
    <div class="card intro rich">${rich(L.intro)}</div>
    <div class="lesson-body">${body}</div>
    <section class="card mt" id="quiz">
      <div class="card-title"><h2>✅ Kiểm tra nhanh <span class="small muted">(${(L.quiz || []).length} câu · chữa ngay)</span></h2></div>
      <p class="small muted">Làm hết để hoàn thành bài. Sai câu nào, đọc giải thích rồi xem lại phần tương ứng ở trên.</p>
      <div id="quiz-list"></div>
      <div id="quiz-done"></div>
    </section>
    <div class="row between mt">
      ${prevU ? `<a class="btn btn-sm" href="#/study/lesson/${tid}/${prevU.id}">← ${esc(prevU.label)}</a>` : '<span></span>'}
      <button class="btn btn-sm" id="markdone">${st?.done ? 'Đã đánh dấu học xong ✓' : 'Đánh dấu đã học (không làm kiểm tra)'}</button>
      ${nextU ? `<a class="btn btn-sm" href="#/study/lesson/${tid}/${nextU.id}">${esc(nextU.label)} →</a>` : '<span></span>'}
    </div>`;

  const cleanup = wireLessonCommon(app);
  if (tid === 'dokkai') wireWorked(app, L);

  // kiểm tra nhanh: chữa ngay từng câu
  const quiz = (L.quiz || []).map(q => ({ ...q, _lesson: L.id, _passage: q.pass ? L.passages?.[q.pass] : null }));
  const answers = {};
  const list = $('#quiz-list', app);
  renderGroups(list, groupByPassage(quiz), {
    mode: 'instant', answers, tid,
    onAnswer: () => {
      if (Object.keys(answers).length < quiz.length) return;
      const c = quiz.filter(q => answers[q.id] === q.answer).length;
      const res = store.setStudy(item.id, { c, n: quiz.length, wrong: quiz.filter(q => answers[q.id] !== q.answer).map(q => q.id) });
      finishBox($('#quiz-done', app), idx, item, res, c, quiz.length);
    },
  });
  $('#markdone', app).onclick = () => { store.setStudy(item.id); toast('Đã đánh dấu học xong'); $('#markdone', app).textContent = 'Đã đánh dấu học xong ✓'; };
  $('#keyonly', app)?.addEventListener('change', (e) => app.classList.toggle('key-only', e.target.checked));
  return cleanup;
}

function wireLessonCommon(app) {
  $('#furi', app).onchange = (e) => { setStudySettings({ furigana: e.target.checked }); applyFurigana(); };
  $('#hidevi', app).onchange = (e) => { app.classList.toggle('hide-vi', e.target.checked); $$('.hideable.shown', app).forEach(x => x.classList.remove('shown')); };
  const onClick = (e) => {
    const h = e.target.closest('.hideable');
    if (h && app.classList.contains('hide-vi')) h.classList.toggle('shown');
  };
  app.addEventListener('click', onClick);
  $$('.toc a', app).forEach(a => a.onclick = (e) => { e.preventDefault(); document.getElementById(a.dataset.to)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  return () => { app.removeEventListener('click', onClick); app.classList.remove('hide-vi', 'key-only'); };
}

function grammarBody(L) {
  const pts = L.points || [];
  const toc = `<nav class="toc">${pts.map((p, i) => `<a href="#" data-to="pt-${esc(p.id)}"><span class="n">${i + 1}</span><span class="jp">${esc(plain(p.pattern))}</span></a>`).join('')}
    ${L.summary?.length ? '<a href="#" data-to="summary">Tóm tắt</a>' : ''}<a href="#" data-to="quiz">Kiểm tra</a></nav>`;
  const cards = pts.map((p, i) => `
    <section class="card point" id="pt-${esc(p.id)}">
      <div class="point-head">
        <span class="point-no">${i + 1}</span>
        <div><h2 class="jp">${ja(p.pattern)}</h2>${p.reading ? `<div class="small muted jp">${esc(p.reading)}</div>` : ''}</div>
      </div>
      <p class="point-meaning hideable">${esc(p.meaning)}</p>
      ${p.structure?.length ? `<div class="structure">${p.structure.map(s => `<span class="jp">${ja(s)}</span>`).join('')}</div>` : ''}
      <div class="rich">${rich(p.explain)}</div>
      ${p.nuance ? `<div class="callout warn"><b>⚠ Sắc thái & giới hạn</b>${rich(p.nuance)}</div>` : ''}
      ${examplesHTML(p.examples)}
      ${p.compare?.length ? `<h4>Phân biệt với mẫu dễ nhầm</h4><div class="tbl-wrap"><table class="tbl compare">${p.compare.map(c => `<tr><th class="jp">${ja(c.with)}</th><td class="rich">${rich(c.diff)}</td></tr>`).join('')}</table></div>` : ''}
      ${p.mistakes?.length ? `<h4>Lỗi hay gặp</h4><ul class="mistakes">${p.mistakes.map(m => `<li>${rich(m).replace(/^<p>|<\/p>$/g, '')}</li>`).join('')}</ul>` : ''}
      ${p.tip ? `<div class="callout tip"><b>💡 Mẹo làm đề</b>${rich(p.tip)}</div>` : ''}
    </section>`).join('');
  const summary = L.summary?.length ? `
    <section class="card" id="summary"><h2>Tóm tắt bài</h2>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Mẫu</th><th>Nghĩa</th><th>Dấu hiệu nhận biết</th></tr></thead>
      <tbody>${L.summary.map(s => `<tr><td class="jp">${ja(s.pattern)}</td><td class="hideable">${esc(s.meaning)}</td><td class="small">${ja(s.key)}</td></tr>`).join('')}</tbody></table></div>
    </section>` : '';
  return toc + cards + summary;
}

function examplesHTML(exs) {
  if (!exs?.length) return '';
  return `<h4>Ví dụ</h4><ol class="examples">${exs.map(e => `
    <li><div class="ex-ja jp">${ja(e.ja)}</div><div class="ex-vi hideable">${esc(e.vi)}</div>${e.note ? `<div class="ex-note">${ja(e.note)}</div>` : ''}</li>`).join('')}</ol>`;
}

function vocabBody(L) {
  const secs = L.sections || [];
  const nWords = secs.reduce((a, s) => a + (s.words || []).length, 0);
  const nKey = secs.reduce((a, s) => a + (s.words || []).filter(w => w.key).length, 0);
  const toc = `<nav class="toc">${secs.map((s, i) => `<a href="#" data-to="sec-${i}"><span class="jp">${esc(s.title)}</span></a>`).join('')}
    ${L.focus?.length ? '<a href="#" data-to="focus">Điểm cần chú ý</a>' : ''}<a href="#" data-to="quiz">Kiểm tra</a>
    <label class="check small" style="margin-left:auto"><input type="checkbox" id="keyonly"> Chỉ từ trọng tâm (${nKey}/${nWords})</label></nav>`;
  const word = (w) => `
    <div class="word ${w.key ? 'key' : ''}" id="w-${esc(w.id)}">
      <div class="w-main"><span class="w jp">${ja(w.w)}</span><span class="r jp">${esc(w.r || '')}</span>
        ${w.hv ? `<span class="hv">${esc(w.hv)}</span>` : ''}${w.pos ? `<span class="pill">${esc(w.pos)}</span>` : ''}${w.key ? '<span class="pill key-pill">trọng tâm</span>' : ''}</div>
      <div class="w-vi hideable">${esc(w.vi)}</div>
      ${w.senses?.length ? `<ol class="senses">${w.senses.map(s => `<li><span class="hideable">${esc(s.vi)}</span>${s.ex ? `<div class="w-ex"><span class="jp">${ja(s.ex.ja)}</span><span class="hideable"> — ${esc(s.ex.vi)}</span></div>` : ''}</li>`).join('')}</ol>` : ''}
      ${w.ex ? `<div class="w-ex"><span class="jp">${ja(w.ex.ja)}</span><span class="hideable"> — ${esc(w.ex.vi)}</span></div>` : ''}
      ${w.col?.length || w.rel ? `<div class="w-meta">${w.col?.length ? `<span>連語: <span class="jp">${w.col.map(c => ja(c)).join('、')}</span></span>` : ''}${w.rel ? `<span class="jp">${ja(w.rel)}</span>` : ''}</div>` : ''}
      ${w.note ? `<div class="w-note">${rich(w.note)}</div>` : ''}
    </div>`;
  const body = secs.map((s, i) => `
    <section class="card" id="sec-${i}"><h2><span class="jp">${esc(s.title)}</span> <span class="small muted">${esc(s.title_vi || '')}</span></h2>
      <div class="words">${(s.words || []).map(word).join('')}</div></section>`).join('');
  const focus = L.focus?.length ? `<section class="card" id="focus"><h2>Điểm cần chú ý</h2>${L.focus.map(f => `
      <div class="focus-item"><h3>${ja(f.title)}</h3><div class="rich">${rich(f.body)}</div>${examplesHTML(f.examples)}</div>`).join('')}</section>` : '';
  return toc + body + focus;
}

function passageHTML(p, { reveal = true } = {}) {
  if (!p) return '';
  return `<div class="passage study-passage">
    ${p.title ? `<div class="small muted">${esc(p.kind || '')} ${p.kind ? '·' : ''} <b class="jp">${esc(p.title)}</b></div>` : p.kind ? `<div class="small muted">${esc(p.kind)}</div>` : ''}
    <div class="ja">${ja(p.ja)}</div>
    ${p.vi ? `<details class="vi" ${reveal ? '' : 'hidden'}><summary>Bản dịch tiếng Việt</summary><div>${esc(p.vi).replace(/\n/g, '<br>')}</div></details>` : ''}
  </div>`;
}

function readingBody(L) {
  const strat = (L.strategy || []).map((s, i) => `<div class="step"><span class="point-no">${i + 1}</span><div><h3>${ja(s.title)}</h3><div class="rich">${rich(s.body)}</div></div></div>`).join('');
  const sig = L.signals?.length ? `<section class="card"><h2>Từ tín hiệu cần nhận ra</h2><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>Tín hiệu</th><th>Ý nghĩa / cách dùng</th></tr></thead><tbody>
      ${L.signals.map(s => `<tr><td class="jp" style="white-space:nowrap">${ja(s.ja)}</td><td><span class="hideable">${esc(s.vi)}</span>${s.note ? `<div class="small muted">${rich(s.note)}</div>` : ''}</td></tr>`).join('')}
      </tbody></table></div></section>` : '';
  // ví dụ mẫu dùng chung một đoạn văn → vẽ đoạn văn một lần, các câu nối tiếp nhau
  const firstOfPass = new Map();
  (L.worked || []).forEach((q, i) => { if (!firstOfPass.has(q.pass)) firstOfPass.set(q.pass, i); });
  const worked = (L.worked || []).map((q, i) => `
    <section class="card worked" data-w="${i}">
      <h2>Ví dụ mẫu ${i + 1}</h2>
      ${firstOfPass.get(q.pass) === i ? passageHTML(L.passages?.[q.pass], { reveal: false }) : `<p class="small muted">Dùng đoạn văn ở ví dụ mẫu ${firstOfPass.get(q.pass) + 1}.</p>`}
      <div class="q-text">${ja(q.q, true)}</div>
      <ol class="w-opts">${q.options.map((o, j) => `<li data-j="${j}">${ja(o, true)}</li>`).join('')}</ol>
      <button class="btn btn-primary btn-sm" data-reveal="${i}">Tự nghĩ đáp án trước, rồi bấm để xem phân tích</button>
      <div class="w-ans" hidden>
        <p><b>Đáp án: ${LETTERS[q.answer]}</b></p>
        <div class="callout tip"><b>Phân tích từng bước</b>${rich(q.walkthrough)}</div>
        <div class="rich">${rich(q.why)}</div>
      </div>
    </section>`).join('');
  return `<section class="card"><h2>Cách làm</h2><div class="steps">${strat}</div></section>${sig}${worked}`;
}

function wireWorked(app, L) {
  $$('[data-reveal]', app).forEach(b => b.onclick = () => {
    const sec = b.closest('.worked');
    const q = L.worked[Number(b.dataset.reveal)];
    sec.querySelector('.w-ans').hidden = false;
    sec.querySelector('details.vi')?.removeAttribute('hidden');
    sec.querySelectorAll('.w-opts li').forEach(li => li.classList.toggle('correct', Number(li.dataset.j) === q.answer));
    b.remove();
  });
}

/* ================= Câu hỏi (dùng chung) ================= */
function groupByPassage(qs) {
  const groups = [];
  let cur = null;
  for (const q of qs) {
    const key = q.pass ? `${q._lesson}/${q.pass}` : null;
    if (key && cur && cur.key === key) cur.qs.push(q);
    else { cur = { key, passage: q._passage, qs: [q] }; groups.push(cur); }
  }
  return groups;
}

/**
 * Vẽ các nhóm câu hỏi vào container.
 * mode: 'instant' (chữa ngay khi chọn) | 'exam' (chỉ ghi lựa chọn) | 'review' (hiện đáp án + giải thích)
 */
function renderGroups(container, groups, { mode, answers, onAnswer, tid, startNo = 1 }) {
  let no = startNo;
  container.innerHTML = '';
  for (const g of groups) {
    const wrap = document.createElement('div');
    wrap.className = 'q-group' + (g.passage ? ' with-passage' : '');
    if (g.passage) wrap.insertAdjacentHTML('beforeend', passageHTML(g.passage, { reveal: mode === 'review' }));
    const col = document.createElement('div');
    for (const q of g.qs) col.appendChild(questionCard(q, no++, { mode, answers, onAnswer, tid, group: wrap }));
    wrap.appendChild(col);
    container.appendChild(wrap);
  }
}

function questionCard(q, no, { mode, answers, onAnswer, tid, group }) {
  const card = document.createElement('article');
  card.className = 'question';
  card.dataset.qid = q.id;
  const short = q.options.every(o => plain(o).length <= 14);
  const draw = () => {
    const sel = answers[q.id];
    const reveal = mode === 'review' || (mode === 'instant' && sel != null);
    const lessonLink = q._lesson && tid ? `<a class="small muted" href="#/study/lesson/${tid}/${q._lesson}">${esc(q._lesson.toUpperCase())}</a>` : '';
    card.innerHTML = `
      <div class="q-head"><span class="q-num">${no}.</span><span class="pill">${esc(q.kind === 'passage' ? (tid === 'dokkai' ? '読解' : '文章の文法') : KIND[q.kind] || q.kind)}</span>
        ${reveal ? (sel == null ? '<span class="pill warn">Bỏ trống</span>' : sel === q.answer ? '<span class="pill good">Đúng</span>' : '<span class="pill bad">Sai</span>') : ''}
        <span class="spacer"></span>${reveal ? lessonLink : ''}</div>
      <div class="q-text">${ja(q.q, true)}</div>
      <div class="options ${short ? 'short' : ''}">${q.options.map((o, i) => {
        const cls = ['opt'];
        if (reveal) { if (i === q.answer) cls.push('correct'); else if (i === sel) cls.push('wrong'); }
        else if (i === sel) cls.push('selected');
        return `<button type="button" class="${cls.join(' ')}" data-i="${i}" ${reveal ? 'disabled' : ''}><span class="n">${LETTERS[i]}</span><span class="opt-body">${ja(o, true)}</span></button>`;
      }).join('')}</div>
      ${reveal ? `<div class="explain">
        ${q.kind === 'order' && q.order ? `<p><b>Thứ tự đúng:</b> <span class="jp">${q.order.map(i => `${LETTERS[i]} ${ja(q.options[i])}`).join(' → ')}</span></p>` : ''}
        ${q.vi ? `<h4>Dịch</h4><p>${esc(q.vi)}</p>` : ''}
        <h4>Giải thích</h4><div class="rich">${rich(q.why)}</div>
      </div>` : ''}`;
    if (!reveal) $$('.opt', card).forEach(b => b.onclick = () => {
      answers[q.id] = Number(b.dataset.i);
      draw();
      if (mode === 'instant') group?.querySelector('details.vi')?.removeAttribute('hidden');
      onAnswer?.(q);
    });
  };
  draw();
  return card;
}

function finishBox(el, idx, item, res, c, n) {
  const track = trackOf(idx, item.id.split(':')[0]);
  const next = scheduleOf(track).find(x => !store.studyOf(x.id)?.done);
  const p = pct(c, n);
  el.innerHTML = `<div class="finish ${p >= 80 ? 'good' : p >= 60 ? 'warn' : 'bad'}">
    <div class="score-big">${c}/${n} <span>${p}%</span></div>
    <div>${p >= 80 ? 'Tốt lắm! Bài này đã nắm khá chắc.' : p >= 60 ? 'Tạm ổn. Xem lại giải thích các câu sai.' : 'Nên đọc lại phần giải thích các mẫu bị sai trước khi học tiếp.'}
      ${res.best && res.tries > 1 ? `<div class="small muted">Tốt nhất: ${Math.round(res.best * 100)}% · ${res.tries} lần làm</div>` : ''}</div>
    <div class="row">
      <a class="btn btn-sm" href="#/study?t=${track.id}">Về lộ trình</a>
      ${next && next.ready && next.id !== item.id ? `<a class="btn btn-primary btn-sm" href="${itemHref(next)}">Tiếp: ${esc(next.label)} →</a>` : ''}
    </div></div>`;
}

/* ================= 練習 / まとめ問題 ================= */
async function runPage(app, idx, actId, params) {
  const item = findItem(idx, actId);
  if (!item) throw new Error('Không tìm thấy buổi học này');
  if (item.type === 'L') { location.hash = itemHref(item); return; }
  const tid = item.id.split(':')[0];
  const { groups: rawGroups } = await questionsFor(item);
  let groups = rawGroups.map(qs => ({ key: qs[0].pass ? `${qs[0]._lesson}/${qs[0].pass}` : null, passage: qs[0]._passage, qs }));
  const prevRes = store.studyOf(item.id);
  const onlyWrong = params.wrong === '1' && prevRes?.wrong?.length;
  if (onlyWrong) {
    const w = new Set(prevRes.wrong);
    groups = groups.map(g => ({ ...g, qs: g.qs.filter(q => w.has(q.id)) })).filter(g => g.qs.length);
  }
  const isExam = item.type === 'M' && !onlyWrong;
  groups = shuffle(groups); // trộn cả まとめ問題 để không đoán được câu thuộc bài nào
  const all = groups.flatMap(g => g.qs);
  const n = all.length;
  const perQ = tid === 'dokkai' ? 120 : tid === 'goi' ? 40 : 60; // giây gợi ý / câu
  const suggest = n * perQ;

  // bài thi: giữ bài làm dở (máy này)
  let draft = null;
  if (isExam) { try { draft = JSON.parse(localStorage.getItem(DRAFT_KEY(item.id)) || 'null'); } catch { draft = null; } }
  const answers = draft?.answers || {};
  const startedAt = draft?.startedAt || Date.now();
  const saveDraft = () => { if (isExam) localStorage.setItem(DRAFT_KEY(item.id), JSON.stringify({ answers, startedAt })); };

  app.innerHTML = `
    <div class="lesson-bar">
      <a href="#/study?t=${tid}" class="btn btn-sm btn-ghost">← Lộ trình</a>
      <span class="small muted">${esc(trackOf(idx, tid).title)} · tuần ${item.week + 1} · ${WEEKDAYS[item.slot]}</span>
      <span class="spacer"></span>
      <label class="check small"><input type="checkbox" id="furi" ${studySettings().furigana !== false ? 'checked' : ''}> Furigana</label>
    </div>
    <header class="lesson-head">
      <div class="small muted">${typeIcon[item.type]} ${typeName[item.type]}${prevRes?.done ? ` · lần trước <span class="pill ${scoreCls(prevRes)}">${esc(scoreText(prevRes))}</span>` : ''}</div>
      <h1>${esc(item.label)} ${onlyWrong ? '<span class="pill warn">chỉ câu sai lần trước</span>' : ''}</h1>
      <p class="muted" style="margin:0">${esc(item.title)} · ${n} câu · ${isExam ? `gợi ý ${Math.round(suggest / 60)} phút, làm hết rồi nộp bài` : 'chữa ngay từng câu'}</p>
      <div class="small mt">Ôn lại: ${item.units.map(u => `<a href="#/study/lesson/${tid}/${u.id}">${esc(u.label)} <span class="jp">${esc(u.title)}</span></a>`).join(' · ')}</div>
    </header>
    ${isExam ? `<div class="test-bar run-bar"><span id="prog"></span><span class="timer" id="timer"></span><button class="btn btn-primary btn-sm" id="submit">Nộp bài</button></div>` : `<div class="test-bar run-bar"><span id="prog"></span><span class="small muted" id="score"></span></div>`}
    <div id="qs"></div>
    <div id="done"></div>`;
  $('#furi', app).onchange = (e) => { setStudySettings({ furigana: e.target.checked }); applyFurigana(); };

  const prog = () => {
    const a = Object.keys(answers).filter(k => all.some(q => q.id === k)).length;
    $('#prog', app).textContent = `${a}/${n} câu`;
    if (!isExam) {
      const c = all.filter(q => answers[q.id] === q.answer).length;
      $('#score', app).textContent = a ? `đúng ${c}/${a}` : '';
    }
    return a;
  };

  const finish = () => {
    const c = all.filter(q => answers[q.id] === q.answer).length;
    const wrong = all.filter(q => answers[q.id] !== q.answer).map(q => q.id);
    let res = prevRes;
    if (!onlyWrong) res = store.setStudy(item.id, { c, n, wrong });
    localStorage.removeItem(DRAFT_KEY(item.id));
    renderGroups($('#qs', app), groups, { mode: 'review', answers, tid });
    const box = $('#done', app);
    finishBox(box, idx, item, res || { }, c, n);
    if (wrong.length && !onlyWrong) box.querySelector('.row').insertAdjacentHTML('afterbegin', `<a class="btn btn-sm" href="#/study/do/${encodeURIComponent(item.id)}?wrong=1">Làm lại ${wrong.length} câu sai</a>`);
    if (isExam) { $('#submit', app)?.remove(); clearInterval(timer); }
    (isExam ? $('.run-bar', app) : box).scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  renderGroups($('#qs', app), groups, {
    mode: isExam ? 'exam' : 'instant', answers, tid,
    onAnswer: () => { saveDraft(); if (prog() === n && !isExam) finish(); },
  });
  prog();

  let timer = null;
  if (isExam) {
    const tick = () => {
      const el = $('#timer', app);
      if (!el) { clearInterval(timer); return; }
      const sec = (Date.now() - startedAt) / 1000;
      el.textContent = `${fmtTime(sec)} / ${fmtTime(suggest)}`;
      el.classList.toggle('over', sec > suggest);
    };
    tick(); timer = setInterval(tick, 1000);
    $('#submit', app).onclick = async () => {
      const left = n - prog();
      if (left && !(await confirmDialog({ title: 'Nộp bài?', body: `<p>Còn <b>${left}</b> câu chưa làm.</p>`, ok: 'Nộp bài' }))) return;
      finish();
    };
  }
  return () => clearInterval(timer);
}
