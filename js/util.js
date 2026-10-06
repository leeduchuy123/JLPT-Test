/* ---------- DOM & string helpers ---------- */
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export const esc = (s) => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** Escape but keep \n as <br> and underline markers. */
export const escText = (s) => esc(s).replace(/\n/g, '<br>');

export const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

export function shuffle(arr, rnd = Math.random) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export const pick = (arr, n) => shuffle(arr).slice(0, n);

export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export const pct = (c, t) => (t ? Math.round((c / t) * 100) : 0);

/* ---------- time ---------- */
export const DAY = 86400000;
export const todayKey = (d = new Date()) => {
  const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};
export const startOfDay = (ts = Date.now()) => { const d = new Date(ts); d.setHours(0, 0, 0, 0); return d.getTime(); };
export const daysBetween = (a, b) => Math.round((startOfDay(b) - startOfDay(a)) / DAY);

export function fmtTime(sec) {
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return (h ? h + ':' : '') + String(m).padStart(h ? 2 : 1, '0') + ':' + String(s).padStart(2, '0');
}
export function fmtDuration(sec) {
  sec = Math.round(sec);
  if (sec < 60) return `${sec} giây`;
  const m = Math.floor(sec / 60), s = sec % 60;
  if (m < 60) return s ? `${m} phút ${s} giây` : `${m} phút`;
  const h = Math.floor(m / 60);
  return `${h} giờ ${m % 60} phút`;
}
export function fmtDate(ts, withTime = false) {
  const d = new Date(ts);
  const date = `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
  if (!withTime) return date;
  return `${date} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
export function relDay(ts) {
  const diff = daysBetween(Date.now(), ts);
  if (diff <= 0) return diff === 0 ? 'hôm nay' : `quá hạn ${-diff} ngày`;
  if (diff === 1) return 'ngày mai';
  return `sau ${diff} ngày`;
}

/* ---------- UI primitives ---------- */
let toastTimer;
export function toast(msg, ms = 2200) {
  const el = $('#toast');
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, ms);
}

/** Simple confirm modal. Returns Promise<boolean>. */
export function confirmDialog({ title = 'Xác nhận', body = '', ok = 'Đồng ý', cancel = 'Huỷ', danger = false } = {}) {
  return new Promise((resolve) => {
    const root = $('#modal-root');
    root.innerHTML = `
      <div class="modal-back" role="dialog" aria-modal="true">
        <div class="modal">
          <h3>${esc(title)}</h3>
          <div class="mb">${body}</div>
          <div class="row" style="justify-content:flex-end">
            <button class="btn" data-act="cancel">${esc(cancel)}</button>
            <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-act="ok">${esc(ok)}</button>
          </div>
        </div>
      </div>`;
    const close = (v) => { root.innerHTML = ''; resolve(v); };
    root.querySelector('[data-act="ok"]').onclick = () => close(true);
    root.querySelector('[data-act="cancel"]').onclick = () => close(false);
    root.querySelector('.modal-back').onclick = (e) => { if (e.target === e.currentTarget) close(false); };
    root.querySelector('[data-act="ok"]').focus();
  });
}

export function modal(html) {
  const root = $('#modal-root');
  root.innerHTML = `<div class="modal-back" role="dialog" aria-modal="true"><div class="modal">${html}</div></div>`;
  const close = () => { root.innerHTML = ''; };
  root.querySelector('.modal-back').onclick = (e) => { if (e.target === e.currentTarget) close(); };
  $$('[data-close]', root).forEach(b => b.onclick = close);
  return { el: root.querySelector('.modal'), close };
}

/* ---------- Japanese text helpers ---------- */
const KANJI_RE = /[一-龯㐀-䶿]/;
export const hasKanji = (s) => KANJI_RE.test(s || '');
export const kanjiChars = (s) => Array.from(new Set((s || '').match(/[一-龯㐀-䶿]/g) || []));
export const isKana = (s) => /^[぀-ヿー　-〿\s]+$/.test(s || '');
export const normJa = (s) => (s || '')
  .replace(/[\s　]/g, '')
  .replace(/[〜～~]/g, '')
  .replace(/[（）()「」『』【】]/g, '')
  .replace(/[。、．，…・]/g, '');

/** Render stem: turn ___ / ＿＿＿ blanks into a styled blank; ★ highlighted. */
export function renderStem(text) {
  let h = esc(text || '');
  h = h.replace(/\n/g, '<br>');
  // ＿từ＿ = gạch chân từ được hỏi; ＿＿＿ = chỗ trống
  h = h.replace(/＿([^＿\s]{1,25}?)＿/g, '<u>$1</u>');
  h = h.replace(/[＿_]{2,}/g, '<u>　　　</u>');
  h = h.replace(/(^|[^<])_([^_<]{1,25}?)_(?!\w)/g, '$1<u>$2</u>');
  h = h.replace(/（\s*）/g, '（　　）');
  h = h.replace(/★/g, '<b style="color:var(--accent)">★</b>');
  return h;
}

export function avg(arr) { return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0; }

export function debounce(fn, ms = 200) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export function downloadJSON(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 1)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
}
