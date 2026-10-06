/* ---------- Xem sau: SRS review ---------- */
import { $, $$, esc, pct, relDay, fmtDate, toast, confirmDialog } from '../util.js';
import * as store from '../store.js';
import { getQ, toItems, SECTIONS, typeLabel } from '../data.js';
import { renderItem, sectionPill } from '../question.js';
import { boxLabel, INTERVALS } from '../srs.js';
import { navigate } from '../app.js';

export async function render(app, route) {
  if (route.segs[0] === 'run') return runPage(app);
  return listPage(app, route.params);
}

function listPage(app, params) {
  let tab = params.tab || 'due';
  const draw = () => {
    const all = store.allCards().filter(c => getQ(c.qid));
    const due = all.filter(c => c.due <= Date.now());
    const flagged = all.filter(c => c.flagged);
    const list = tab === 'due' ? due : tab === 'flag' ? flagged : all;
    const bySec = {};
    for (const c of all) { const q = getQ(c.qid); bySec[q.section] = (bySec[q.section] || 0) + 1; }
    const learned = all.filter(c => c.box >= 4).length;

    app.innerHTML = `
      <div class="row between">
        <div><h1 style="margin-bottom:.1em">Xem sau</h1><p class="muted" style="margin:0">Câu bạn đã lưu cờ hoặc làm sai, ôn lại theo lịch ${INTERVALS.join(' → ')} ngày.</p></div>
        <button class="btn btn-primary btn-lg" id="start" ${due.length ? '' : 'disabled'}>Ôn ngay${due.length ? ` (${due.length})` : ''}</button>
      </div>
      <div class="grid-tiles mt">
        <div class="tile"><div class="label">Đến hạn hôm nay</div><div class="value" style="color:${due.length ? 'var(--bad)' : 'inherit'}">${due.length}</div></div>
        <div class="tile"><div class="label">Tổng trong lịch</div><div class="value">${all.length}</div><div class="sub">${Object.keys(SECTIONS).filter(s => bySec[s]).map(s => `${SECTIONS[s].short} ${bySec[s]}`).join(' · ')}</div></div>
        <div class="tile"><div class="label">Đã lưu cờ</div><div class="value">${flagged.length}</div></div>
        <div class="tile"><div class="label">Gần thuộc (≥ 1 tháng)</div><div class="value">${learned}</div></div>
      </div>
      <div class="tabs mt">
        <button class="${tab === 'due' ? 'active' : ''}" data-tab="due">Đến hạn (${due.length})</button>
        <button class="${tab === 'flag' ? 'active' : ''}" data-tab="flag">Đã cờ (${flagged.length})</button>
        <button class="${tab === 'all' ? 'active' : ''}" data-tab="all">Tất cả (${all.length})</button>
      </div>
      ${list.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Câu</th><th>Dạng</th><th>Mức</th><th>Hạn</th><th></th></tr></thead><tbody>
        ${list.slice(0, 200).map(c => { const q = getQ(c.qid); return `<tr>
          <td><a href="#/review/run?only=${esc(c.qid)}" class="ja">${esc(trunc(q.question, 60))}</a>${store.noteOf(c.qid) ? ' 📝' : ''}${c.flagged ? ' <span style="color:var(--flag)">★</span>' : ''}</td>
          <td>${sectionPill(q.section)} <span class="small muted">${esc(typeLabel(q.type))}</span></td>
          <td><span class="small">${esc(boxLabel(c.box))}</span>${c.lapses ? `<span class="small muted"> · quên ${c.lapses}</span>` : ''}</td>
          <td class="small ${c.due <= Date.now() ? '' : 'muted'}">${esc(relDay(c.due))}</td>
          <td><button class="btn btn-sm btn-ghost" data-rm="${esc(c.qid)}" title="Bỏ khỏi lịch">✕</button></td></tr>`; }).join('')}
      </tbody></table></div>${list.length > 200 ? `<p class="small muted">Hiển thị 200/${list.length}.</p>` : ''}`
        : `<p class="empty">${tab === 'due' ? 'Không có câu nào đến hạn. Tốt lắm! Làm thêm Luyện nhanh để có thêm câu cần ôn.' : 'Chưa có câu nào. Bấm ☆ ở bất kỳ câu nào để lưu vào đây.'}</p>`}`;

    $$('[data-tab]', app).forEach(b => b.onclick = () => { tab = b.dataset.tab; draw(); });
    $('#start', app).onclick = () => navigate('#/review/run');
    $$('[data-rm]', app).forEach(b => b.onclick = async () => {
      if (await confirmDialog({ title: 'Bỏ câu này khỏi lịch ôn?', body: 'Bạn vẫn có thể lưu lại sau bằng nút ☆.', ok: 'Bỏ', danger: true })) { store.removeFromSrs(b.dataset.rm); document.dispatchEvent(new CustomEvent('srs-changed')); draw(); }
    });
  };
  draw();
}

const trunc = (s, n) => (s || '').replace(/\s+/g, ' ').length > n ? (s || '').replace(/\s+/g, ' ').slice(0, n) + '…' : (s || '').replace(/\s+/g, ' ');

function runPage(app) {
  const only = new URLSearchParams(location.hash.split('?')[1] || '').get('only');
  const queue = only ? [only] : store.dueCards().filter(c => getQ(c.qid)).map(c => c.qid).slice(0, 50);
  if (!queue.length) { navigate('#/review'); return; }
  // nhóm theo đoạn văn để ôn cả đoạn một lần
  const items = toItems(queue);
  let idx = 0; let doneCount = 0, okCount = 0;
  const answers = {};

  const draw = () => {
    if (idx >= items.length) return summary();
    const item = items[idx];
    const answered = item.qids.every(q => answers[q] != null);
    app.innerHTML = `
      <div class="test-bar">
        <div><div class="small muted">Ôn lại · Xem sau</div><b>${idx + 1} / ${items.length}</b> <span class="small muted">· nhớ ${okCount}/${doneCount}</span></div>
        <div class="row"><a class="btn btn-sm" href="#/review">Dừng</a></div>
        <div class="progress-line"><i style="width:${pct(idx, items.length)}%"></i></div>
      </div>
      <div id="item"></div>
      <div class="card tight mt" id="grade" ${answered ? '' : 'hidden'}>
        <p class="small muted" style="margin:0 0 .5rem">Bạn nhớ câu này đến mức nào? (quyết định bao lâu nữa sẽ gặp lại)</p>
        <div class="row">
          <button class="btn btn-danger" data-g="again">Quên · ngày mai</button>
          <button class="btn" data-g="hard">Khó · 2 ngày</button>
          <button class="btn btn-primary" data-g="good">Nhớ</button>
          <button class="btn" data-g="easy">Dễ</button>
          <button class="btn btn-ghost btn-sm" data-g="drop">Bỏ khỏi lịch</button>
        </div>
      </div>`;
    const mount = () => {
      const el = $('#item', app); el.innerHTML = '';
      const reveal = item.qids.every(q => answers[q] != null);
      el.appendChild(renderItem(item, {
        startIndex: 1, answers, reveal, interactive: !reveal,
        onSelect: (qid, i) => {
          if (answers[qid] != null) return;
          answers[qid] = i;
          const q = getQ(qid); const ok = i === q.answer;
          store.recordAnswer(qid, ok, { mode: 'srs' });
          doneCount++; if (ok) okCount++;
          if (item.qids.every(q2 => answers[q2] != null)) {
            mount();
            const g = $('#grade', app); g.hidden = false;
            // gợi ý: sai → chỉ còn Quên/Khó nổi bật
            const allOk = item.qids.every(q2 => answers[q2] === getQ(q2).answer);
            if (!allOk) { $('[data-g="good"]', g).classList.remove('btn-primary'); $('[data-g="again"]', g).classList.add('btn-primary'); }
          }
        },
      }));
    };
    mount();
    $$('[data-g]', app).forEach(b => b.onclick = () => {
      const g = b.dataset.g;
      for (const qid of item.qids) {
        if (g === 'drop') store.removeFromSrs(qid);
        else store.gradeSrs(qid, g);
      }
      document.dispatchEvent(new CustomEvent('srs-changed'));
      idx++; draw(); window.scrollTo({ top: 0 });
    });
    document.onkeydown = (e) => {
      if (e.target.matches('input,textarea,select')) return;
      if (/^[1-4]$/.test(e.key) && item.qids.length === 1 && !answered) $(`#item .opt[data-i="${Number(e.key) - 1}"]:not(:disabled)`, app)?.click();
      if (!$('#grade', app).hidden) { if (e.key === 'Enter') $('[data-g="good"]', app).click(); if (e.key === 'a') $('[data-g="again"]', app).click(); }
    };
  };
  const summary = () => {
    document.onkeydown = null;
    const left = store.dueCards().length;
    app.innerHTML = `<div class="card" style="max-width:640px;margin:2rem auto">
      <h1>Xong phiên ôn</h1>
      <p>Nhớ ${okCount}/${doneCount} câu (${pct(okCount, doneCount)}%). ${left ? `Còn ${left} câu đến hạn.` : 'Không còn câu nào đến hạn hôm nay 🎉'}</p>
      <div class="row">${left ? '<a class="btn btn-primary" href="#/review/run">Ôn tiếp</a>' : ''}<a class="btn" href="#/review">Danh sách</a><a class="btn" href="#/drill">Luyện nhanh</a></div></div>`;
  };
  draw();
  return () => { document.onkeydown = null; };
}
