/* ---------- Persistent state (localStorage) ---------- */
import { todayKey, startOfDay } from './util.js';
import * as srs from './srs.js';

const KEY = 'jlpt-n3-state-v2';
const LEGACY_KEY = 'jlpt-n3-progress';

const DEFAULTS = () => ({
  version: 2,
  settings: {
    theme: 'system',          // system | light | dark
    examDate: '2026-12-07',
    autoSrsWrong: true,       // câu sai tự vào "Xem sau"
    showSourceExplain: true,
    dailyGoal: 20,            // số câu / ngày
    shuffleOptions: false,
  },
  stats: {},     // qid -> {n, c, last, wrong:[ts...]} (compact per-question stats)
  history: [],   // finished sessions
  srs: {},       // qid -> card
  notes: {},     // qid -> text
  inProgress: {},// sessionId -> session
  daily: {},     // 'YYYY-MM-DD' -> {answered, correct, secs}
});

let state = load();

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const s = JSON.parse(raw);
      return { ...DEFAULTS(), ...s, settings: { ...DEFAULTS().settings, ...(s.settings || {}) } };
    }
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

export const get = () => state;
export const settings = () => state.settings;
export function setSetting(k, v) { state.settings[k] = v; save(); }

/* ----- per-question attempt recording ----- */
export function recordAnswer(qid, correct, { mode = 'drill', secs = 0 } = {}) {
  const now = Date.now();
  const s = state.stats[qid] || (state.stats[qid] = { n: 0, c: 0, last: 0, w: 0 });
  s.n++; if (correct) s.c++; else s.w++;
  s.last = now;
  const d = state.daily[todayKey()] || (state.daily[todayKey()] = { answered: 0, correct: 0, secs: 0 });
  d.answered++; if (correct) d.correct++; d.secs += Math.round(secs);

  if (!correct && state.settings.autoSrsWrong && mode !== 'srs') {
    if (!state.srs[qid]) state.srs[qid] = srs.newCard(now, 'wrong');
    else if (state.srs[qid].box > 0) state.srs[qid] = srs.review(state.srs[qid], 'again', now);
  }
  save();
}

export const statOf = (qid) => state.stats[qid] || null;

/* ----- SRS ----- */
export function toggleFlag(qid) {
  const now = Date.now();
  const card = state.srs[qid];
  if (card && card.flagged) {
    // bỏ cờ: nếu thẻ chỉ tồn tại vì cờ (chưa ôn lần nào) thì xoá hẳn, không thì chỉ hạ cờ
    if (card.reps === 0 && card.reason === 'flag') delete state.srs[qid];
    else card.flagged = false;
  } else if (card) {
    card.flagged = true;
  } else {
    state.srs[qid] = srs.newCard(now, 'flag');
  }
  save();
  return !!(state.srs[qid] && state.srs[qid].flagged);
}
export const isFlagged = (qid) => !!(state.srs[qid] && state.srs[qid].flagged);
export const inSrs = (qid) => !!state.srs[qid];
export function removeFromSrs(qid) { delete state.srs[qid]; save(); }
export function gradeSrs(qid, grade) {
  const card = state.srs[qid] || srs.newCard();
  state.srs[qid] = srs.review(card, grade);
  save();
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
  if (text && text.trim()) state.notes[qid] = text.trim(); else delete state.notes[qid];
  save();
}

/* ----- sessions ----- */
export function saveSession(session) { state.inProgress[session.id] = session; save(); }
export function getSession(id) { return state.inProgress[id] || null; }
export function deleteSession(id) { delete state.inProgress[id]; save(); }
/** Mock-test sessions only (drill keeps its own single slot in inProgress). */
export function listSessions() { return Object.values(state.inProgress).filter(s => Array.isArray(s.papers)).sort((a, b) => b.updatedAt - a.updatedAt); }

export function addHistory(entry) {
  state.history.unshift(entry);
  if (state.history.length > 300) state.history.length = 300;
  save(true);
}
export function getHistory(id) { return state.history.find(h => h.id === id) || null; }
export function deleteHistory(id) { state.history = state.history.filter(h => h.id !== id); save(); }

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
  for (const [oldId, newId] of Object.entries(aliases || {})) {
    if (exists(oldId) || !exists(newId)) continue;
    const st = state.stats[oldId];
    if (st) {
      const t = state.stats[newId] || (state.stats[newId] = { n: 0, c: 0, last: 0, w: 0 });
      t.n += st.n; t.c += st.c; t.w = (t.w || 0) + (st.w || 0); t.last = Math.max(t.last || 0, st.last || 0);
      delete state.stats[oldId]; moved++;
    }
    if (state.srs[oldId]) {
      if (!state.srs[newId] || state.srs[oldId].due < state.srs[newId].due) state.srs[newId] = state.srs[oldId];
      delete state.srs[oldId]; moved++;
    }
    if (state.notes[oldId]) {
      state.notes[newId] = [state.notes[newId], state.notes[oldId]].filter(Boolean).join(' / ');
      delete state.notes[oldId]; moved++;
    }
  }
  if (moved) save(true);
  return moved;
}

/* ----- import / export ----- */
export function exportState() { return JSON.parse(JSON.stringify(state)); }
export function importState(obj) {
  if (!obj || typeof obj !== 'object' || !obj.version) throw new Error('File không đúng định dạng');
  state = { ...DEFAULTS(), ...obj, settings: { ...DEFAULTS().settings, ...(obj.settings || {}) } };
  save(true);
}
export function resetAll() { state = DEFAULTS(); save(true); }
