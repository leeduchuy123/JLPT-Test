/* ---------- Home: hôm nay làm gì ---------- */
import { esc, pct, daysBetween, fmtDate, fmtDuration } from '../util.js';
import * as store from '../store.js';
import { SECTIONS, TYPES, PAPERS, bankStats, typeLabel, getQ } from '../data.js';

export async function render(app) {
  const s = store.get();
  const set = s.settings;
  const examTs = new Date(set.examDate + 'T09:00:00').getTime();
  const daysLeft = daysBetween(Date.now(), examTs);
  const today = store.todayStats();
  const due = store.dueCards();
  const sessions = store.listSessions();
  const stats = bankStats();
  const streak = store.streak();

  // weakest types (>=5 attempts)
  const byType = {};
  for (const [qid, st] of Object.entries(s.stats)) {
    const q = getQ(qid);
    if (!q) continue;
    const t = byType[q.type] || (byType[q.type] = { n: 0, c: 0 });
    t.n += st.n; t.c += st.c;
  }
  const weak = Object.entries(byType).filter(([, v]) => v.n >= 5).map(([t, v]) => ({ t, p: pct(v.c, v.n), n: v.n }))
    .sort((a, b) => a.p - b.p).slice(0, 3);

  const recent = s.history.slice(0, 3);
  const goal = set.dailyGoal || 20;
  const goalPct = Math.min(100, pct(today.answered, goal));

  app.innerHTML = `
    <div class="row between mb">
      <div>
        <h1 style="margin-bottom:.1em">Hôm nay, ${fmtDate(Date.now())}</h1>
        <p class="muted" style="margin:0">${daysLeft > 0 ? `Còn <b>${daysLeft} ngày</b> đến kỳ thi JLPT N3 (${fmtDate(examTs)}).` : daysLeft === 0 ? '<b>Hôm nay thi!</b> Chúc may mắn 🍀' : 'Kỳ thi đã qua. Cập nhật ngày thi mới trong Cài đặt.'}</p>
      </div>
      <div class="tile" style="min-width:160px">
        <div class="label">Mục tiêu hôm nay</div>
        <div class="value">${today.answered}<span class="muted" style="font-size:1rem"> / ${goal} câu</span></div>
        <div class="meter ${goalPct >= 100 ? 'good' : ''} mt" style="margin-top:.4rem"><i style="width:${goalPct}%"></i></div>
        <div class="sub">${today.answered ? `${pct(today.correct, today.answered)}% đúng · ${fmtDuration(today.secs)}` : 'Chưa làm câu nào'}${streak > 1 ? ` · 🔥 ${streak} ngày liên tiếp` : ''}</div>
      </div>
    </div>

    ${sessions.length ? `
    <div class="card" style="border-color:var(--primary)">
      <div class="card-title"><h2>Bài đang làm dở</h2></div>
      ${sessions.map(ss => `
        <div class="row between" style="padding:.4rem 0;border-top:1px solid var(--border)">
          <div><b>${esc(ss.title)}</b> <span class="pill">${ss.mode === 'strict' ? 'Có giờ' : 'Không giờ'}</span>
            <div class="small muted">${sessionProgress(ss)} · cập nhật ${fmtDate(ss.updatedAt, true)}</div></div>
          <a class="btn btn-primary btn-sm" href="#/test/run/${esc(ss.id)}">Tiếp tục</a>
        </div>`).join('')}
    </div>` : ''}

    <div class="grid mt">
      <a class="card" href="#/review">
        <h2>⟳ Xem sau ${due.length ? `<span class="pill bad">${due.length} câu đến hạn</span>` : ''}</h2>
        <p class="muted">${due.length ? `Ôn lại ${due.length} câu đã lưu / làm sai. Mất khoảng ${Math.ceil(due.length * 0.75)} phút.` : `Không có câu nào đến hạn. Tổng ${Object.keys(s.srs).length} câu trong lịch ôn.`}</p>
      </a>
      <a class="card" href="#/drill">
        <h2>⚡ Luyện nhanh</h2>
        <p class="muted">10–30 câu, chữa ngay từng câu. Hợp khi chỉ có vài phút.</p>
        ${weak.length ? `<p class="small">Yếu nhất: ${weak.map(w => `<a href="#/drill?type=${w.t}">${esc(typeLabel(w.t))} ${w.p}%</a>`).join(' · ')}</p>` : ''}
      </a>
      <a class="card" href="#/test">
        <h2>📝 Thi thử</h2>
        <p class="muted">Đề đầy đủ có giờ như thi thật, hoặc từng phần không giờ.</p>
      </a>
    </div>

    <div class="grid-2 mt">
      <div class="card">
        <div class="card-title"><h2>Kết quả gần đây</h2><a class="small" href="#/progress">Xem tiến độ →</a></div>
        ${recent.length ? `<table class="tbl"><tbody>${recent.map(h => `
          <tr><td><a href="#/test/result/${esc(h.id)}">${esc(h.title)}</a><div class="small muted">${fmtDate(h.t, true)} · ${h.mode === 'strict' ? 'có giờ' : h.mode === 'drill' ? 'luyện nhanh' : 'không giờ'}</div></td>
          <td class="num"><b>${pct(h.score.correct, h.score.total)}%</b><div class="small muted">${h.score.correct}/${h.score.total}</div></td></tr>`).join('')}</tbody></table>`
          : '<p class="empty">Chưa có bài nào. Bắt đầu với một bài Luyện nhanh 10 câu nhé.</p>'}
      </div>
      <div class="card">
        <div class="card-title"><h2>Ngân hàng câu hỏi</h2><a class="small" href="#/settings">Chi tiết →</a></div>
        <table class="tbl"><tbody>
          ${Object.keys(SECTIONS).map(k => `<tr><td><span class="pill ${k}">${esc(SECTIONS[k].short)}</span> ${esc(SECTIONS[k].label)}</td><td class="num">${(stats.sections[k] || 0).toLocaleString('vi')}</td></tr>`).join('')}
          <tr><th>Tổng</th><th class="num">${stats.total.toLocaleString('vi')}</th></tr>
        </tbody></table>
      </div>
    </div>

    <div class="card mt">
      <h2>Cách dùng hiệu quả trong ${daysLeft > 0 ? daysLeft : 60} ngày</h2>
      <ol style="margin:0 0 0 1.2rem;padding:0">
        <li><b>Mỗi ngày</b>: xử lý hết "Xem sau" (5–10 phút), rồi 1 bài Luyện nhanh ở phần yếu nhất.</li>
        <li><b>Khi sai</b>: đọc giải thích, bấm "Học lại" để xem từ vựng/ngữ pháp liên quan. Câu sai tự vào lịch ôn (1 → 3 → 7 → 14 → 30 ngày).</li>
        <li><b>Cuối tuần</b>: 1 đề thi thử có giờ (đủ 3 phần, ~140 phút) để quen áp lực thời gian.</li>
        <li><b>Đọc hiểu</b>: làm 1–2 đoạn/ngày ở chế độ không giờ, đọc bản dịch ngay sau khi làm xong.</li>
      </ol>
    </div>`;
}

function sessionProgress(ss) {
  let done = 0, total = 0;
  for (const p of ss.papers) { total += p.qids.length; done += Object.keys(p.answers).length; }
  const paper = PAPERS.find(p => p.id === ss.papers[ss.paperIdx]?.id);
  return `${done}/${total} câu · đang ở phần ${esc(paper?.jp || '')}`;
}
