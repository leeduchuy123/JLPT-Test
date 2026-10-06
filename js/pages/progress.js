/* ---------- Tiến độ ---------- */
import { $, $$, esc, pct, fmtDate, fmtDuration, daysBetween, todayKey, DAY, confirmDialog } from '../util.js';
import * as store from '../store.js';
import { SECTIONS, TYPES, getQ, typeLabel, bankStats } from '../data.js';
import { columns, hbars, lines } from '../charts.js';
import { sectionPill } from '../question.js';

export async function render(app) {
  const s = store.get();
  const examTs = new Date(s.settings.examDate + 'T09:00:00').getTime();
  const daysLeft = daysBetween(Date.now(), examTs);
  const bank = bankStats();

  // tổng hợp theo dạng/section từ stats
  const byType = {}, bySec = {};
  let total = 0, correct = 0, seen = 0;
  for (const [qid, st] of Object.entries(s.stats)) {
    const q = getQ(qid); if (!q) continue;
    seen++; total += st.n; correct += st.c;
    (byType[q.type] ||= { n: 0, c: 0 }).n += st.n; byType[q.type].c += st.c;
    (bySec[q.section] ||= { n: 0, c: 0 }).n += st.n; bySec[q.section].c += st.c;
  }
  // 7 ngày gần nhất
  let a7 = 0, c7 = 0, secs7 = 0;
  for (let i = 0; i < 7; i++) { const d = s.daily[todayKey(new Date(Date.now() - i * DAY))]; if (d) { a7 += d.answered; c7 += d.correct; secs7 += d.secs; } }
  const tests = s.history.filter(h => h.kind !== 'drill');
  const streak = store.streak();

  // chart: 30 ngày
  const days = [];
  for (let i = 29; i >= 0; i--) { const dt = new Date(Date.now() - i * DAY); const k = todayKey(dt); const d = s.daily[k] || { answered: 0, correct: 0 }; days.push({ label: `${dt.getDate()}/${dt.getMonth() + 1}`, value: d.correct, value2: d.answered, tip: k }); }

  // chart: theo dạng
  const typeRows = Object.keys(TYPES).filter(t => bank.types[t]).map(t => { const v = byType[t] || { n: 0, c: 0 }; return { label: typeLabel(t), pct: pct(v.c, v.n), n: v.n, c: v.c, t }; });
  const weak = typeRows.filter(r => r.n >= 5).sort((a, b) => a.pct - b.pct).slice(0, 4);

  // chart: điểm thi thử theo thời gian
  const recentTests = tests.slice(0, 12).reverse();
  const labels = recentTests.map(h => fmtDate(h.t).slice(0, 5));
  const series = Object.keys(SECTIONS).map((sec, i) => ({ name: SECTIONS[sec].short, color: `var(--s${i + 1})`, points: recentTests.map(h => h.bySection[sec] ? pct(h.bySection[sec].c, h.bySection[sec].n) : null) })).filter(sr => sr.points.some(p => p != null));

  app.innerHTML = `
    <h1>Tiến độ</h1>
    <div class="grid-tiles">
      <div class="tile"><div class="label">Còn lại đến kỳ thi</div><div class="value">${daysLeft > 0 ? daysLeft + ' ngày' : '—'}</div><div class="sub">${fmtDate(examTs)}</div></div>
      <div class="tile"><div class="label">Câu đã làm</div><div class="value">${total.toLocaleString('vi')}</div><div class="sub">${seen.toLocaleString('vi')} câu khác nhau · ${pct(seen, bank.total)}% ngân hàng</div></div>
      <div class="tile"><div class="label">Tỉ lệ đúng (tổng)</div><div class="value">${total ? pct(correct, total) + '%' : '—'}</div><div class="sub">7 ngày: ${a7 ? pct(c7, a7) + '%' : '—'} (${a7} câu)</div></div>
      <div class="tile"><div class="label">Thời gian 7 ngày</div><div class="value">${fmtDuration(secs7).replace(' giây', 's')}</div><div class="sub">🔥 chuỗi ${streak} ngày</div></div>
      <div class="tile"><div class="label">Đề thi thử</div><div class="value">${tests.length}</div><div class="sub">${tests.length ? `gần nhất ${pct(tests[0].score.correct, tests[0].score.total)}%` : 'chưa làm'}</div></div>
      <div class="tile"><div class="label">Lịch ôn (Xem sau)</div><div class="value">${Object.keys(s.srs).length}</div><div class="sub">${store.dueCards().length} đến hạn</div></div>
    </div>

    <div class="card mt">
      <div class="card-title"><h2>30 ngày gần đây</h2><span class="small muted">cột đậm = câu đúng, cột nhạt = tổng câu</span></div>
      <div id="c-days"></div>
    </div>

    <div class="grid-2 mt">
      <div class="card">
        <div class="card-title"><h2>Theo phần</h2></div>
        <table class="tbl"><tbody>${Object.keys(SECTIONS).map(sec => { const v = bySec[sec] || { n: 0, c: 0 }; const p = pct(v.c, v.n); return `
          <tr><td>${sectionPill(sec)} ${esc(SECTIONS[sec].label)}</td><td class="num">${v.n ? p + '%' : '—'}</td><td style="width:40%"><div class="meter ${!v.n ? '' : p >= 75 ? 'good' : p >= 55 ? 'warn' : 'bad'}"><i style="width:${v.n ? p : 0}%"></i></div></td></tr>`; }).join('')}</tbody></table>
        ${weak.length ? `<h3 class="mt">Cần luyện thêm</h3><div class="stack">${weak.map(w => `<div class="row between"><span>${esc(w.label)} <span class="muted small">${w.pct}% · ${w.n} lượt</span></span><a class="btn btn-sm" href="#/drill?type=${w.t}">Luyện 10 câu</a></div>`).join('')}</div>` : ''}
      </div>
      <div class="card">
        <div class="card-title"><h2>Điểm thi thử theo thời gian</h2></div>
        ${recentTests.length >= 2 ? '<div id="c-tests"></div>' : '<p class="empty">Cần ít nhất 2 bài thi thử để vẽ biểu đồ.</p>'}
      </div>
    </div>

    <div class="card mt">
      <div class="card-title"><h2>Độ chính xác theo dạng bài</h2><span class="small muted">rê chuột để xem số liệu</span></div>
      <div id="c-types"></div>
    </div>

    <div class="card mt">
      <div class="card-title"><h2>Lịch sử</h2><span class="small muted">${s.history.length} bài</span></div>
      ${s.history.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Ngày</th><th>Bài</th><th>Chế độ</th><th class="num">Kết quả</th><th class="num">Thời gian</th><th></th></tr></thead><tbody>
        ${s.history.slice(0, 60).map(h => `<tr>
          <td class="small">${fmtDate(h.t, true)}</td>
          <td><a href="#/test/result/${esc(h.id)}">${esc(h.title)}</a></td>
          <td class="small">${h.mode === 'strict' ? '⏱ có giờ' : h.mode === 'drill' ? '⚡ luyện' : '☕ không giờ'}</td>
          <td class="num"><b>${pct(h.score.correct, h.score.total)}%</b> <span class="small muted">${h.score.correct}/${h.score.total}</span></td>
          <td class="num small">${fmtDuration(h.secs || 0)}</td>
          <td><button class="btn btn-sm btn-ghost" data-del="${esc(h.id)}" title="Xoá">✕</button></td></tr>`).join('')}
      </tbody></table></div>` : '<p class="empty">Chưa có lịch sử.</p>'}
    </div>`;

  columns($('#c-days', app), days, { yLabel: ' câu' });
  hbars($('#c-types', app), typeRows);
  if (recentTests.length >= 2) lines($('#c-tests', app), labels, series);
  $$('[data-del]', app).forEach(b => b.onclick = async () => {
    if (await confirmDialog({ title: 'Xoá bài này khỏi lịch sử?', body: 'Thống kê từng câu vẫn được giữ.', ok: 'Xoá', danger: true })) { store.deleteHistory(b.dataset.del); render(app); }
  });
}
