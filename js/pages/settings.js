/* ---------- Cài đặt & dữ liệu ---------- */
import { $, $$, esc, toast, confirmDialog, downloadJSON, fmtDate } from '../util.js';
import * as store from '../store.js';
import { bankStats, loadManifest, SECTIONS, TYPES, typeLabel } from '../data.js';
import { applyTheme } from '../app.js';
import * as sync from '../sync.js';

export async function render(app) {
  const s = store.settings();
  const bank = bankStats();
  const manifest = await loadManifest();

  app.innerHTML = `
    <h1>Cài đặt</h1>
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
    <div class="card" id="sync-card"></div>
    <div class="card">
      <h2>Sao lưu dữ liệu</h2>
      <p class="small muted">Tiến độ, lịch ôn, ghi chú lưu trong trình duyệt này${sync.enabled() ? ' và trên máy chủ đồng bộ' : ''}. Xuất file JSON để giữ một bản sao lưu riêng.</p>
      <div class="row">
        <button class="btn btn-primary" id="export">⬇ Xuất file sao lưu</button>
        <label class="btn">⬆ Nhập từ file <input type="file" id="import" accept="application/json" hidden></label>
        <button class="btn btn-danger" id="reset">Xoá toàn bộ tiến độ</button>
      </div>
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
  $('#export', app).onclick = () => { downloadJSON(store.exportState(), `jlpt-n3-backup-${new Date().toISOString().slice(0, 10)}.json`); toast('Đã xuất file sao lưu'); };
  $('#import', app).onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const obj = JSON.parse(await f.text());
      if (await confirmDialog({ title: 'Nhập dữ liệu?', body: `<p>Sẽ <b>thay thế</b> toàn bộ tiến độ hiện tại bằng dữ liệu trong file (${Object.keys(obj.stats || {}).length} câu đã làm, ${(obj.history || []).length} bài).</p>${ALL_DEVICES()}`, ok: 'Nhập' })) {
        store.importState(obj); toast('Đã nhập dữ liệu'); applyTheme(); render(app); document.dispatchEvent(new CustomEvent('srs-changed'));
      }
    } catch (err) { toast('Không đọc được file: ' + err.message, 4000); }
    e.target.value = '';
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
