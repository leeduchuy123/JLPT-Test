/* ---------- Cài đặt & dữ liệu ---------- */
import { $, $$, esc, toast, confirmDialog, modal, downloadJSON, fmtDate } from '../util.js';
import * as store from '../store.js';
import { bankStats, loadManifest, bankAliases, getQ, SECTIONS, TYPES, typeLabel } from '../data.js';
import { applyTheme } from '../app.js';
import * as sync from '../sync.js';

export async function render(app) {
  const s = store.settings();
  const bank = bankStats();
  const manifest = await loadManifest();

  const mine = store.summarize(store.get());
  const lastExp = store.lastExportAt();

  app.innerHTML = `
    <h1>Cài đặt</h1>
    <div class="card" id="transfer">
      <h2>Chuyển tiến độ sang máy khác</h2>
      <p class="small muted">Một file JSON chứa <b>tất cả</b>: kết quả từng câu, "Xem sau" cùng lịch ôn lặp lại, ghi chú, lịch sử thi thử, bài đang làm dở, số câu mỗi ngày, cài đặt.</p>
      <ol class="small">
        <li>Máy đang dùng: bấm <b>Xuất file tiến độ</b> → file được tải về.</li>
        <li>Gửi file sang máy kia (Zalo, email, USB, Google Drive…).</li>
        <li>Máy kia: mở trang này → <b>Nhập file tiến độ</b> → chọn <b>Gộp</b>.</li>
      </ol>
      <p class="small">Máy này: ${mine.answered.toLocaleString('vi')} câu đã làm · ${mine.srs} câu "Xem sau" · ${mine.notes} ghi chú · ${mine.tests} bài thi.
        <span class="muted" id="last-exp">${lastExp ? `Lần xuất gần nhất: ${fmtDate(lastExp, true)}.` : 'Chưa xuất file lần nào.'}</span></p>
      <div class="row">
        <button class="btn btn-primary" id="export">⬇ Xuất file tiến độ</button>
        <label class="btn">⬆ Nhập file tiến độ <input type="file" id="import" accept=".json,application/json" hidden></label>
      </div>
    </div>
    <div class="card">
      <h2>Hiển thị</h2>
      <label class="field"><span>Giao diện</span>
        <div class="seg">${[['system', 'Theo hệ thống'], ['light', 'Sáng'], ['dark', 'Tối']].map(([v, l]) => `<button data-theme="${v}" class="${s.theme === v ? 'active' : ''}">${l}</button>`).join('')}</div></label>
      <label class="check"><input type="checkbox" id="showSrc" ${s.showSourceExplain ? 'checked' : ''}> Hiện cả giải thích gốc từ nguồn (nếu có)</label>
    </div>
    <div class="card">
      <h2>Học tập</h2>
      <label class="field"><span>Ngày thi</span><input class="input" type="date" id="examDate" value="${esc(s.examDate)}" style="max-width:220px"></label>
      <label class="field"><span>Mục tiêu mỗi ngày (số câu)</span><input class="input" type="number" min="5" max="200" id="dailyGoal" value="${s.dailyGoal}" style="max-width:220px"></label>
      <label class="check"><input type="checkbox" id="autoSrs" ${s.autoSrsWrong ? 'checked' : ''}> Câu làm sai tự động vào "Xem sau" (ôn lại ngày mai → 3 → 7 → 14 → 30 → 60 ngày)</label>
    </div>
    <details class="card" ${sync.enabled() ? 'open' : ''}>
      <summary><b>Nâng cao:</b> đồng bộ tự động qua máy chủ <span class="small muted">(cần tự cài Vercel + Upstash; không bắt buộc)</span></summary>
      <div id="sync-card" class="mt"></div>
    </details>
    <div class="card">
      <h2>Xoá dữ liệu</h2>
      <p class="small muted">Xoá mọi kết quả, lịch ôn, ghi chú trên máy này. Nên xuất file tiến độ trước.</p>
      <button class="btn btn-danger" id="reset">Xoá toàn bộ tiến độ</button>
    </div>
    <div class="card">
      <h2>Ngân hàng câu hỏi</h2>
      <p class="small muted">${bank.total.toLocaleString('vi')} câu · ${manifest.exams || 0} bộ đề${manifest.built ? ` · cập nhật ${fmtDate(new Date(manifest.built).getTime())}` : ''}${manifest.explained != null ? ` · ${manifest.explained.toLocaleString('vi')} câu có giải thích chi tiết` : ''}</p>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Dạng</th><th class="num">Số câu</th></tr></thead><tbody>
        ${Object.keys(SECTIONS).map(sec => `<tr><th colspan="2">${esc(SECTIONS[sec].label)} · ${bank.sections[sec] || 0}</th></tr>` + Object.keys(TYPES).filter(t => TYPES[t].section === sec && bank.types[t]).map(t => `<tr><td>${TYPES[t].mondai ? `問題${TYPES[t].mondai} · ` : ''}${esc(typeLabel(t))}</td><td class="num">${bank.types[t]}</td></tr>`).join('')).join('')}
      </tbody></table></div>
      <h3 class="mt">Nguồn</h3>
      <p class="small">${Object.entries(bank.sources).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<span class="pill">${esc(k)} · ${v}</span>`).join(' ')}</p>
      ${manifest.notes ? `<p class="small muted">${esc(manifest.notes)}</p>` : ''}
    </div>`;

  $$('[data-theme]', app).forEach(b => b.onclick = () => { store.setSetting('theme', b.dataset.theme); applyTheme(); $$('[data-theme]', app).forEach(x => x.classList.toggle('active', x === b)); });
  $('#showSrc', app).onchange = (e) => store.setSetting('showSourceExplain', e.target.checked);
  $('#autoSrs', app).onchange = (e) => store.setSetting('autoSrsWrong', e.target.checked);
  $('#examDate', app).onchange = (e) => { if (e.target.value) { store.setSetting('examDate', e.target.value); toast('Đã lưu ngày thi'); } };
  $('#dailyGoal', app).onchange = (e) => { const v = Math.max(5, Math.min(200, Number(e.target.value) || 20)); store.setSetting('dailyGoal', v); e.target.value = v; };
  $('#export', app).onclick = () => {
    const d = new Date();
    const stamp = `${d.toISOString().slice(0, 10)}_${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`;
    downloadJSON(store.exportState(), `jlpt-n3-tien-do-${stamp}.json`);
    toast('Đã xuất file tiến độ');
    $('#last-exp', app).textContent = `Lần xuất gần nhất: ${fmtDate(store.lastExportAt(), true)}.`;
  };
  $('#import', app).onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    e.target.value = '';
    let obj;
    try { obj = JSON.parse(await f.text()); store.checkFile(obj); }
    catch (err) { toast('Không đọc được file: ' + (err instanceof SyntaxError ? 'không phải JSON' : err.message), 4000); return; }
    const fs = store.summarize(obj);
    const mode = await importDialog(f.name, fs, mine);
    if (!mode) return;
    try {
      if (mode === 'merge') store.mergeImport(obj); else store.importState(obj);
      store.migrateAliases(bankAliases(), (id) => !!getQ(id) && getQ(id).id === id);
      toast(mode === 'merge' ? 'Đã gộp tiến độ từ file' : 'Đã thay bằng tiến độ trong file', 3000);
      applyTheme(); render(app); document.dispatchEvent(new CustomEvent('srs-changed'));
    } catch (err) { toast('Không nhập được: ' + err.message, 4000); }
  };
  $('#reset', app).onclick = async () => {
    if (await confirmDialog({ title: 'Xoá toàn bộ tiến độ?', body: `<p>Mọi kết quả, lịch ôn, ghi chú sẽ bị xoá. Hãy xuất file sao lưu trước nếu cần.</p>${ALL_DEVICES()}`, ok: 'Xoá hết', danger: true })) {
      store.resetAll(); applyTheme(); toast('Đã xoá'); render(app); document.dispatchEvent(new CustomEvent('srs-changed'));
    }
  };

  drawSync(app);
  document.addEventListener('sync-status', onSyncStatus);
  return () => document.removeEventListener('sync-status', onSyncStatus);
}

/** Hỏi cách nhập file: 'merge' | 'replace' | null (huỷ). */
function importDialog(name, fs, mine) {
  const line = (s) => `${s.answered.toLocaleString('vi')} câu đã làm · ${s.srs} câu "Xem sau" · ${s.notes} ghi chú · ${s.tests} bài thi · ${s.days} ngày học`;
  const { el, close } = modal(`
    <h3>Nhập file tiến độ</h3>
    <p class="small"><b>${esc(name)}</b>${fs.exportedAt ? ` · xuất lúc ${fmtDate(fs.exportedAt, true)}` : ''}</p>
    <p class="small">File: ${line(fs)}<br>Máy này: ${line(mine)}</p>
    <p class="small"><b>Gộp</b> (nên dùng): giữ tiến độ trên máy này và thêm tiến độ trong file; câu nào làm ở cả hai nơi thì lấy lần làm sau cùng.<br>
      <b>Thay thế</b>: xoá tiến độ trên máy này, dùng đúng như trong file.</p>
    ${ALL_DEVICES()}
    <div class="row" style="justify-content:flex-end">
      <button class="btn" data-act="cancel">Huỷ</button>
      <button class="btn btn-danger" data-act="replace">Thay thế</button>
      <button class="btn btn-primary" data-act="merge">Gộp</button>
    </div>`);
  return new Promise((resolve) => {
    const done = (v) => { close(); resolve(v); };
    $$('[data-act]', el).forEach(b => b.onclick = () => done(b.dataset.act === 'cancel' ? null : b.dataset.act));
    el.parentElement.onclick = (e) => { if (e.target === e.currentTarget) done(null); };
    $('[data-act="merge"]', el).focus();
  });
}

const ALL_DEVICES = () => (sync.enabled() ? '<p><b>Đang bật đồng bộ:</b> thao tác này áp dụng cho mọi thiết bị.</p>' : '');

function onSyncStatus() {
  const el = document.getElementById('sync-card');
  if (el && !el.contains(document.activeElement)) drawSync(el.closest('#app'));
}

function drawSync(app) {
  const el = $('#sync-card', app);
  if (!el) return;
  const st = sync.status();
  const head = '<h2>Đồng bộ giữa các thiết bị</h2>';

  if (!st.enabled || st.needPass) {
    el.innerHTML = `${head}
      <p class="small muted">Lưu tiến độ, "Xem sau", ghi chú lên máy chủ để học tiếp trên điện thoại hoặc máy khác.
        Nhập mật khẩu đồng bộ (biến <code>SYNC_PASSWORD</code> đặt trên Vercel) ở mỗi máy.
        Dữ liệu trên máy này được <b>gộp</b> với dữ liệu đã có trên máy chủ, không ghi đè.</p>
      ${st.needPass ? `<p class="small" style="color:var(--bad)">⚠ ${esc(st.error || 'Mật khẩu không còn đúng')}. Hãy nhập lại.</p>` : ''}
      <form class="row" id="sync-form">
        <input class="input" type="password" id="sync-pass" placeholder="Mật khẩu đồng bộ" autocomplete="current-password" required style="max-width:260px">
        <button class="btn btn-primary" type="submit">${st.needPass ? 'Lưu mật khẩu' : 'Bật đồng bộ'}</button>
        ${st.needPass ? '<button class="btn" type="button" id="sync-off">Tắt đồng bộ</button>' : ''}
      </form>
      <p class="small" id="sync-msg" hidden></p>`;
    const msg = $('#sync-msg', el);
    $('#sync-form', el).onsubmit = async (e) => {
      e.preventDefault();
      const btn = e.submitter || $('button[type="submit"]', el);
      btn.disabled = true; msg.hidden = false; msg.style.color = ''; msg.textContent = 'Đang kiểm tra và gộp dữ liệu…';
      try {
        await sync.enable($('#sync-pass', el).value);
        toast('Đã bật đồng bộ');
        render(app);
        document.dispatchEvent(new CustomEvent('srs-changed'));
      } catch (err) {
        msg.style.color = 'var(--bad)'; msg.textContent = err.message;
        btn.disabled = false;
      }
    };
  } else {
    const line = st.error ? `<span style="color:var(--bad)">⚠ ${esc(st.error)}</span>`
      : st.busy ? 'Đang đồng bộ…'
      : st.lastAt ? `☁ Đã đồng bộ lúc ${fmtDate(st.lastAt, true)}` : '☁ Đã bật đồng bộ';
    el.innerHTML = `${head}
      <p>${line}${st.dirty && !st.busy ? ' <span class="pill">có thay đổi đang chờ</span>' : ''}</p>
      <p class="small muted">Tự đồng bộ khi mở app, khi quay lại tab và vài giây sau mỗi câu trả lời. Mất mạng vẫn học bình thường, có mạng lại sẽ tự đẩy lên. Mật khẩu được lưu trong trình duyệt này.</p>
      <div class="row">
        <button class="btn btn-primary" id="sync-now" ${st.busy ? 'disabled' : ''}>Đồng bộ ngay</button>
        <button class="btn" id="sync-off">Tắt đồng bộ trên máy này</button>
      </div>`;
    $('#sync-now', el).onclick = () => sync.syncNow({ manual: true });
  }
  const off = $('#sync-off', el);
  if (off) off.onclick = async () => {
    if (await confirmDialog({ title: 'Tắt đồng bộ trên máy này?', body: '<p>Dữ liệu trên máy này và trên máy chủ vẫn giữ nguyên; chỉ là máy này thôi gửi / nhận thay đổi.</p>', ok: 'Tắt' })) {
      sync.disable(); toast('Đã tắt đồng bộ'); drawSync(app);
    }
  };
}
