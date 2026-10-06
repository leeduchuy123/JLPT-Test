/* ---------- Persistent state (localStorage) ----------
   Mọi thay đổi đi qua các hàm ở đây: chúng ghi mốc thời gian (u / updatedAt / meta.*) và đánh dấu mục đã xoá
   (meta.del) để merge.js gộp được khi đồng bộ nhiều thiết bị, rồi báo cho sync.js qua onChange().
*/
import { todayKey, startOfDay, uid } from './util.js';
import * as srs from './srs.js';
import { normMeta, totals } from './merge.js';

const KEY = 'jlpt-n3-state-v2';
const LEGACY_KEY = 'jlpt-n3-progress';
const DEVICE_KEY = 'jlpt-n3-device';

const DEFAULTS = () => ({
  version: 2,
  settings: {
    theme: 'system',          // system | light | dark (riêng từng máy, không đồng bộ)
    examDate: '2026-12-07',
    autoSrsWrong: true,       // câu sai tự vào "Xem sau"
    showSourceExplain: true,
    dailyGoal: 20,            // số câu / ngày
    shuffleOptions: false,
  },
  stats: {},     // qid -> {n, c, last, w, u?} (compact per-question stats)
  history: [],   // finished sessions
  srs: {},       // qid -> card (+ u: lúc sửa cuối)
  notes: {},     // qid -> text
  inProgress: {},// sessionId -> session
  daily: {},     // 'YYYY-MM-DD' -> {answered, correct, secs, by: {deviceId: {a, c, s}}}
  meta: normMeta(), // epoch, del ('coll/id' -> lúc xoá), noteAt (qid -> lúc sửa), settingsAt
});

/** Id cố định của trình duyệt này (tách khỏi state để không bị đồng bộ / nhập file ghi đè). */
export const deviceId = (() => {
  try {
    let id = localStorage.getItem(DEVICE_KEY);
    if (!id) { id = 'd' + uid(); localStorage.setItem(DEVICE_KEY, id); }
    return id;
  } catch { return 'd' + uid(); }
})();

function normalize(s) {
  const d = DEFAULTS();
  return { ...d, ...s, settings: { ...d.settings, ...(s.settings || {}) }, meta: normMeta(s.meta) };
}

let state = load();

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return normalize(JSON.parse(raw));
  } catch { /* ignore */ }
  try { localStorage.removeItem(LEGACY_KEY); } catch { /* ignore */ }
  return DEFAULTS();
}

let saveTimer;
export function save(immediate = false) {
  const doSave = () => {
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (e) { console.warn('Không lưu được state', e); }
  };
  if (immediate) { clearTimeout(saveTimer); doSave(); return; }
  clearTimeout(saveTimer);
  saveTimer = setTimeout(doSave, 150);
}

/* ----- change notification (cho đồng bộ) ----- */
const listeners = new Set();
export function onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
/** Lưu một thay đổi của người dùng và báo cho các listener. */
function commit(immediate = false) {
  save(immediate);
  for (const fn of listeners) { try { fn(); } catch (e) { console.warn(e); } }
}
const tomb = (coll, id) => { state.meta.del[`${coll}/${id}`] = Date.now(); };
const putCard = (qid, card) => { card.u = Date.now(); state.srs[qid] = card; };

export const get = () => state;
export const settings = () => state.settings;
export function setSetting(k, v) {
  state.settings[k] = v;
  if (k === 'theme') { save(); return; }
  state.meta.settingsAt = Date.now();
  commit();
}

/** Thay toàn bộ state bằng bản đã gộp từ máy chủ (không tính là thay đổi mới của người dùng). */
export function replaceState(next) { state = normalize(next); save(true); }

/* ----- per-question attempt recording ----- */
export function recordAnswer(qid, correct, { mode = 'drill', secs = 0 } = {}) {
  const now = Date.now();
  const s = state.stats[qid] || (state.stats[qid] = { n: 0, c: 0, last: 0, w: 0 });
  s.n++; if (correct) s.c++; else s.w++;
  s.last = now;

  const day = todayKey();
  const d = state.daily[day] || { answered: 0, correct: 0, secs: 0 };
  const by = d.by || { [deviceId]: { a: d.answered || 0, c: d.correct || 0, s: d.secs || 0 } };
  const me = by[deviceId] || (by[deviceId] = { a: 0, c: 0, s: 0 });
  me.a++; if (correct) me.c++; me.s += Math.round(secs);
  state.daily[day] = totals(by);

  if (!correct && state.settings.autoSrsWrong && mode !== 'srs') {
    if (!state.srs[qid]) putCard(qid, srs.newCard(now, 'wrong'));
    else if (state.srs[qid].box > 0) putCard(qid, srs.review(state.srs[qid], 'again', now));
  }
  commit();
}

export const statOf = (qid) => state.stats[qid] || null;

/* ----- SRS ----- */
export function toggleFlag(qid) {
  const now = Date.now();
  const card = state.srs[qid];
  if (card && card.flagged) {
    // bỏ cờ: nếu thẻ chỉ tồn tại vì cờ (chưa ôn lần nào) thì xoá hẳn, không thì chỉ hạ cờ
    if (card.reps === 0 && card.reason === 'flag') { delete state.srs[qid]; tomb('srs', qid); }
    else { card.flagged = false; card.u = now; }
  } else if (card) {
    card.flagged = true; card.u = now;
  } else {
    putCard(qid, srs.newCard(now, 'flag'));
  }
  commit();
  return !!(state.srs[qid] && state.srs[qid].flagged);
}
export const isFlagged = (qid) => !!(state.srs[qid] && state.srs[qid].flagged);
export const inSrs = (qid) => !!state.srs[qid];
export function removeFromSrs(qid) { delete state.srs[qid]; tomb('srs', qid); commit(); }
export function gradeSrs(qid, grade) {
  const card = state.srs[qid] || srs.newCard();
  putCard(qid, srs.review(card, grade));
  commit();
  return state.srs[qid];
}
export function dueCards(now = Date.now()) {
  return Object.entries(state.srs).filter(([, c]) => srs.isDue(c, now)).map(([qid, c]) => ({ qid, ...c }))
    .sort((a, b) => a.due - b.due);
}
export function allCards() {
  return Object.entries(state.srs).map(([qid, c]) => ({ qid, ...c })).sort((a, b) => a.due - b.due);
}

/* ----- notes ----- */
export const noteOf = (qid) => state.notes[qid] || '';
export function setNote(qid, text) {
  if (text && text.trim()) {
    state.notes[qid] = text.trim(); state.meta.noteAt[qid] = Date.now();
  } else if (qid in state.notes) {
    delete state.notes[qid]; delete state.meta.noteAt[qid]; tomb('notes', qid);
  } else return;
  commit();
}

/* ----- sessions ----- */
export function saveSession(session) { session.updatedAt = Date.now(); state.inProgress[session.id] = session; commit(); }
export function getSession(id) { return state.inProgress[id] || null; }
export function deleteSession(id) { delete state.inProgress[id]; tomb('inProgress', id); commit(); }
/** Mock-test sessions only (drill keeps its own single slot in inProgress). */
export function listSessions() { return Object.values(state.inProgress).filter(s => Array.isArray(s.papers)).sort((a, b) => b.updatedAt - a.updatedAt); }

export function addHistory(entry) {
  state.history.unshift(entry);
  if (state.history.length > 300) state.history.length = 300;
  commit(true);
}
export function getHistory(id) { return state.history.find(h => h.id === id) || null; }
export function deleteHistory(id) { state.history = state.history.filter(h => h.id !== id); tomb('history', id); commit(); }

/* ----- aggregates ----- */
export function streak() {
  let n = 0; let day = startOfDay();
  const has = (ts) => { const k = todayKey(new Date(ts)); return (state.daily[k]?.answered || 0) > 0; };
  if (!has(day)) day -= 86400000; // hôm nay chưa học thì tính từ hôm qua
  while (has(day)) { n++; day -= 86400000; }
  return n;
}
export function todayStats() { return state.daily[todayKey()] || { answered: 0, correct: 0, secs: 0 }; }

/* ----- migrate progress keyed by question ids that were merged into another id ----- */
export function migrateAliases(aliases, exists) {
  let moved = 0;
  const now = Date.now();
  for (const [oldId, newId] of Object.entries(aliases || {})) {
    if (exists(oldId) || !exists(newId)) continue;
    const st = state.stats[oldId];
    if (st) {
      const t = state.stats[newId] || (state.stats[newId] = { n: 0, c: 0, last: 0, w: 0 });
      t.n += st.n; t.c += st.c; t.w = (t.w || 0) + (st.w || 0); t.last = Math.max(t.last || 0, st.last || 0); t.u = now;
      delete state.stats[oldId]; tomb('stats', oldId); moved++;
    }
    if (state.srs[oldId]) {
      if (!state.srs[newId] || state.srs[oldId].due < state.srs[newId].due) putCard(newId, { ...state.srs[oldId] });
      delete state.srs[oldId]; tomb('srs', oldId); moved++;
    }
    if (state.notes[oldId]) {
      state.notes[newId] = [state.notes[newId], state.notes[oldId]].filter(Boolean).join(' / ');
      state.meta.noteAt[newId] = now;
      delete state.notes[oldId]; delete state.meta.noteAt[oldId]; tomb('notes', oldId); moved++;
    }
  }
  if (moved) commit(true);
  return moved;
}

/* ----- import / export ----- */
export function exportState() { return JSON.parse(JSON.stringify(state)); }
/** Nhập file = thay thế toàn bộ, kể cả trên các máy đang đồng bộ (epoch mới). */
export function importState(obj) {
  if (!obj || typeof obj !== 'object' || !obj.version) throw new Error('File không đúng định dạng');
  state = normalize(obj);
  state.meta.epoch = { id: uid(), at: Date.now() };
  commit(true);
}
export function resetAll() {
  state = DEFAULTS();
  state.meta.epoch = { id: uid(), at: Date.now() };
  commit(true);
}
