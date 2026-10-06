/* ---------- Đồng bộ đám mây (tuỳ chọn, 1 người dùng) ----------
   Máy chủ: /api/sync (Vercel Function + Upstash Redis), khoá bằng mật khẩu SYNC_PASSWORD.
   Mỗi bản trên máy chủ có số hiệu rev. Máy đẩy lên kèm baseRev = rev nó biết; nếu máy khác đã đẩy trước (409)
   thì tải bản mới về, gộp bằng merge.js rồi đẩy lại. localStorage vẫn là nơi lưu chính nên offline vẫn học được.
   Khi nào đồng bộ: mở app, quay lại tab, có mạng trở lại, 3 phút/lần khi đang mở, và 4 giây sau mỗi thay đổi.
*/
import * as store from './store.js';
import { mergeStates, differs } from './merge.js';

const CFG_KEY = 'jlpt-n3-sync';   // { pass, rev, dirty, lastAt, needPass } — riêng máy này, không nằm trong state
const PUSH_DELAY = 4000;
const POLL_MS = 3 * 60 * 1000;
const MIN_PULL_GAP = 10 * 1000;
const RETRY_MS = 60 * 1000;
const TIMEOUT_MS = 20000;

let cfg = readCfg();
let busy = false, started = false;
let again = null; // yêu cầu đồng bộ đến lúc đang bận: null | { pull }
let lastError = null, lastPullAt = 0, pushTimer = 0, retryTimer = 0;
let seq = 0; // tăng mỗi khi có thay đổi chưa đẩy lên

function readCfg() { try { return JSON.parse(localStorage.getItem(CFG_KEY)) || {}; } catch { return {}; } }
function saveCfg() {
  try { if (cfg.pass) localStorage.setItem(CFG_KEY, JSON.stringify(cfg)); else localStorage.removeItem(CFG_KEY); }
  catch { /* ignore */ }
}
const emit = (name = 'sync-status') => document.dispatchEvent(new CustomEvent(name));

export const enabled = () => !!cfg.pass;
export const status = () => ({ enabled: enabled(), busy, lastAt: cfg.lastAt || 0, error: lastError, dirty: !!cfg.dirty, needPass: !!cfg.needPass });

class SyncError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

const ERRORS = {
  401: 'Sai mật khẩu đồng bộ',
  404: 'Không tìm thấy /api/sync (đồng bộ chỉ chạy trên bản deploy Vercel)',
  413: 'Dữ liệu quá lớn để đồng bộ',
  429: 'Nhập sai mật khẩu quá nhiều lần, thử lại sau 15 phút',
  503: 'Máy chủ chưa cấu hình (thiếu SYNC_PASSWORD hoặc Upstash Redis)',
};

async function api(method, { pass = cfg.pass, query = '', body } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let r;
  try {
    r = await fetch('/api/sync' + query, {
      method, cache: 'no-store', signal: ctrl.signal,
      // header HTTP chỉ nhận ASCII → mã hoá để mật khẩu có dấu tiếng Việt vẫn dùng được
      headers: { Authorization: `Bearer ${encodeURIComponent(pass)}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new SyncError('network', navigator.onLine === false ? 'Đang offline, sẽ đồng bộ khi có mạng' : 'Không kết nối được máy chủ đồng bộ');
  } finally { clearTimeout(timer); }
  let data = {};
  try { data = await r.json(); } catch { /* không phải JSON (vd. 404 của server tĩnh) */ }
  if (r.ok || r.status === 409) return { status: r.status, ...data };
  throw new SyncError(r.status, ERRORS[r.status] || `Lỗi máy chủ đồng bộ (${r.status})`);
}

/* ----- nén: "gz:" + base64(gzip(JSON)), hoặc "js:" + JSON nếu trình duyệt không có CompressionStream ----- */
async function encode(obj) {
  const json = JSON.stringify(obj); // chạy đồng bộ ngay khi gọi → chụp đúng state lúc này
  if (typeof CompressionStream !== 'function') return 'js:' + json;
  const buf = await new Response(new Blob([json]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer();
  return 'gz:' + toB64(new Uint8Array(buf));
}
async function decode(blob) {
  if (blob.startsWith('js:')) return JSON.parse(blob.slice(3));
  if (!blob.startsWith('gz:')) throw new SyncError('format', 'Dữ liệu đồng bộ không đúng định dạng');
  if (typeof DecompressionStream !== 'function') throw new SyncError('format', 'Trình duyệt quá cũ để đọc dữ liệu đồng bộ');
  const stream = new Blob([fromB64(blob.slice(3))]).stream().pipeThrough(new DecompressionStream('gzip'));
  return JSON.parse(await new Response(stream).text());
}
function toB64(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
function fromB64(b64) {
  const s = atob(b64), out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

function markDirty() {
  seq++;
  if (!cfg.dirty) { cfg.dirty = true; saveCfg(); emit(); }
}

/** Tải bản trên máy chủ (nếu khác rev đang biết) và gộp vào máy này. */
async function pull() {
  const r = await api('GET', { query: cfg.rev != null ? `?rev=${cfg.rev}` : '' });
  lastPullAt = Date.now();
  if (!r.same) {
    const remote = r.blob ? await decode(r.blob) : null;
    if (remote) {
      const local = store.get();
      const merged = mergeStates(local, remote, { device: store.deviceId });
      if (differs(merged, local)) { store.replaceState(merged); emit('sync-applied'); }
      if (differs(merged, remote)) markDirty();
      else if (cfg.dirty) cfg.dirty = false; // máy chủ đã có đủ mọi thay đổi của máy này
    } else {
      markDirty(); // máy chủ trống → đẩy dữ liệu máy này lên
    }
  }
  cfg.rev = r.rev;
  saveCfg();
}

async function run(withPull) {
  let fresh = withPull || cfg.rev == null;
  for (let attempt = 0; attempt < 4; attempt++) {
    if (fresh) await pull();
    if (!cfg.dirty) return;
    const mark = seq;
    const blob = await encode(store.get());
    const res = await api('PUT', { body: { baseRev: cfg.rev, blob } });
    if (res.status === 409) { fresh = true; continue; } // máy khác vừa đẩy → tải về, gộp, đẩy lại
    cfg.rev = res.rev;
    if (seq === mark) cfg.dirty = false;
    saveCfg();
    return;
  }
  throw new SyncError('conflict', 'Xung đột đồng bộ liên tục, sẽ thử lại sau');
}

/** Đồng bộ ngay. pull=false: chỉ đẩy thay đổi (vẫn tự tải về nếu máy chủ đã có bản mới hơn). */
export async function syncNow({ pull: withPull = true, manual = false } = {}) {
  if (!enabled() || (cfg.needPass && !manual)) return;
  if (busy) { again = { pull: withPull || !!(again && again.pull) }; return; }
  busy = true;
  clearTimeout(pushTimer); clearTimeout(retryTimer);
  emit();
  try {
    await run(withPull);
    lastError = null;
    cfg.lastAt = Date.now();
    saveCfg();
  } catch (e) {
    lastError = e.message || String(e);
    if (e.code === 401) { cfg.needPass = true; saveCfg(); }
    else if (e.code !== 429 && e.code !== 503 && e.code !== 404) retryTimer = setTimeout(() => syncNow(), RETRY_MS);
    if (!(e instanceof SyncError)) console.error(e);
  } finally {
    busy = false;
    emit();
    const next = again; again = null;
    if (next && !lastError) setTimeout(() => syncNow(next), 0);
    else if (cfg.dirty && !lastError) schedulePush();
  }
}

function schedulePush() {
  clearTimeout(pushTimer);
  pushTimer = setTimeout(() => syncNow({ pull: false }), PUSH_DELAY);
}

/** Bật đồng bộ trên máy này: kiểm tra mật khẩu rồi gộp dữ liệu máy này với máy chủ. */
export async function enable(pass) {
  pass = String(pass || '').normalize('NFC').trim();
  if (!pass) throw new Error('Hãy nhập mật khẩu đồng bộ');
  await api('GET', { pass, query: '?probe=1' });
  cfg = { pass, rev: null, dirty: true, lastAt: 0 };
  lastError = null;
  saveCfg();
  await syncNow({ manual: true });
  if (lastError) throw new Error(lastError);
}

/** Tắt đồng bộ trên máy này (dữ liệu trên máy và trên máy chủ vẫn giữ nguyên). */
export function disable() {
  clearTimeout(pushTimer); clearTimeout(retryTimer);
  cfg = {}; lastError = null;
  saveCfg();
  emit();
}

export function start() {
  if (started) return;
  started = true;
  store.onChange(() => { if (enabled()) { markDirty(); schedulePush(); } });
  document.addEventListener('visibilitychange', () => {
    if (!enabled()) return;
    if (document.visibilityState === 'hidden') { if (cfg.dirty) syncNow({ pull: false }); }
    else if (Date.now() - lastPullAt > MIN_PULL_GAP) syncNow();
  });
  window.addEventListener('online', () => syncNow());
  setInterval(() => { if (document.visibilityState === 'visible') syncNow(); }, POLL_MS);
  syncNow();
}
