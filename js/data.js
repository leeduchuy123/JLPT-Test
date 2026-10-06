/* ---------- Static data: question bank, exams, references ---------- */
import { shuffle, pick, normJa, kanjiChars } from './util.js';

export const SECTIONS = {
  moji:    { label: 'Từ vựng · Chữ Hán', jp: '文字・語彙', short: 'Moji-Goi', minutes: 30 },
  bunpo:   { label: 'Ngữ pháp',          jp: '文法',       short: 'Bunpo',    minutes: 25 },
  dokkai:  { label: 'Đọc hiểu',          jp: '読解',       short: 'Dokkai',   minutes: 45 },
  choukai: { label: 'Nghe hiểu',         jp: '聴解',       short: 'Choukai',  minutes: 40 },
};
export const SECTION_ORDER = ['moji', 'bunpo', 'dokkai', 'choukai'];

/** JLPT N3 papers (what you actually sit, with official timings). */
export const PAPERS = [
  { id: 'moji',         label: 'Kiến thức ngôn ngữ (Từ vựng · Chữ Hán)', jp: '言語知識（文字・語彙）', sections: ['moji'],            minutes: 30 },
  { id: 'bunpo_dokkai', label: 'Ngữ pháp · Đọc hiểu',                    jp: '言語知識（文法）・読解', sections: ['bunpo', 'dokkai'], minutes: 70 },
  { id: 'choukai',      label: 'Nghe hiểu',                               jp: '聴解',                   sections: ['choukai'],         minutes: 40 },
];
export const paperOf = (id) => PAPERS.find(p => p.id === id);

/** Question types → JLPT 問題 blueprint (count = số câu trong đề thật N3). */
export const TYPES = {
  kanji_reading:  { section: 'moji',    mondai: 1, label: 'Cách đọc Kanji',        jp: '漢字読み',   count: 8 },
  orthography:    { section: 'moji',    mondai: 2, label: 'Viết chữ Hán',          jp: '表記',       count: 6 },
  context:        { section: 'moji',    mondai: 3, label: 'Từ theo ngữ cảnh',      jp: '文脈規定',   count: 11 },
  paraphrase:     { section: 'moji',    mondai: 4, label: 'Từ đồng nghĩa',         jp: '言い換え類義', count: 5 },
  usage:          { section: 'moji',    mondai: 5, label: 'Cách dùng từ',          jp: '用法',       count: 5 },
  grammar_form:   { section: 'bunpo',   mondai: 1, label: 'Chọn mẫu ngữ pháp',     jp: '文法形式',   count: 13 },
  sentence_order: { section: 'bunpo',   mondai: 2, label: 'Sắp xếp câu ★',         jp: '文の組み立て', count: 5 },
  text_grammar:   { section: 'bunpo',   mondai: 3, label: 'Ngữ pháp đoạn văn',     jp: '文章の文法', count: 5, passage: true },
  reading_short:  { section: 'dokkai',  mondai: 4, label: 'Đọc đoạn ngắn',         jp: '内容理解（短文）', count: 4, passage: true },
  reading_mid:    { section: 'dokkai',  mondai: 5, label: 'Đọc đoạn vừa',          jp: '内容理解（中文）', count: 6, passage: true },
  reading_long:   { section: 'dokkai',  mondai: 6, label: 'Đọc đoạn dài',          jp: '内容理解（長文）', count: 4, passage: true },
  info_retrieval: { section: 'dokkai',  mondai: 7, label: 'Tìm thông tin',         jp: '情報検索',   count: 2, passage: true },
  listening:      { section: 'choukai', mondai: null, label: 'Nghe hiểu',          jp: '聴解',       count: 28 },
  vocab_meaning:  { section: 'moji',    mondai: null, label: 'Nghĩa từ vựng',      jp: '語彙',       count: 0 },
  kanji_meaning:  { section: 'moji',    mondai: null, label: 'Nghĩa Kanji',        jp: '漢字',       count: 0 },
  grammar_misc:   { section: 'bunpo',   mondai: null, label: 'Ngữ pháp tổng hợp',  jp: '文法',       count: 0 },
};
export const typeLabel = (t) => TYPES[t]?.label || t;
export const typesOf = (section) => Object.keys(TYPES).filter(t => TYPES[t].section === section);

/* ----- loading ----- */
const cache = new Map();
async function fetchJSON(path) {
  if (cache.has(path)) return cache.get(path);
  const p = fetch(path).then(async r => {
    if (!r.ok) throw new Error(`Không tải được ${path} (${r.status})`);
    return r.json();
  });
  cache.set(path, p);
  try { return await p; } catch (e) { cache.delete(path); throw e; }
}

const bank = { loaded: false, byId: new Map(), passages: new Map(), bySection: {}, byType: {}, sources: {} };
let manifest = null;

export async function loadManifest() {
  if (manifest) return manifest;
  try { manifest = await fetchJSON('/data/manifest.json'); } catch { manifest = { sections: {}, exams: 0, built: null }; }
  return manifest;
}

/** Load all four section files once. */
export async function loadBank() {
  if (bank.loaded) return bank;
  const parts = await Promise.all(SECTION_ORDER.map(async s => {
    try { return await fetchJSON(`/data/bank/${s}.json`); }
    catch (e) { console.warn(e.message); return { passages: {}, questions: [] }; }
  }));
  for (const part of parts) {
    for (const [pid, p] of Object.entries(part.passages || {})) bank.passages.set(pid, p);
    for (const q of part.questions || []) {
      bank.byId.set(q.id, q);
      (bank.bySection[q.section] ||= []).push(q);
      (bank.byType[q.type] ||= []).push(q);
      bank.sources[q.source] = (bank.sources[q.source] || 0) + 1;
    }
  }
  try { bank.aliases = await fetchJSON('/data/aliases.json'); } catch { bank.aliases = {}; }
  bank.loaded = true;
  return bank;
}
/** Questions dropped as duplicates in a later build resolve to the copy that was kept. */
export const resolveId = (id) => (bank.byId.has(id) ? id : (bank.aliases?.[id] && bank.byId.has(bank.aliases[id]) ? bank.aliases[id] : id));
export const getQ = (id) => bank.byId.get(id) || bank.byId.get(bank.aliases?.[id]) || null;
export const bankAliases = () => bank.aliases || {};
export const getPassage = (pid) => (pid ? bank.passages.get(pid) : null) || null;
export const questionsOf = (section) => bank.bySection[section] || [];
export const questionsOfType = (type) => bank.byType[type] || [];
export const bankStats = () => ({
  total: bank.byId.size,
  sections: Object.fromEntries(SECTION_ORDER.map(s => [s, (bank.bySection[s] || []).length])),
  types: Object.fromEntries(Object.keys(TYPES).map(t => [t, (bank.byType[t] || []).length])),
  sources: bank.sources,
});

let examsCache = null;
export async function loadExams() {
  if (examsCache) return examsCache;
  try { examsCache = await fetchJSON('/data/exams.json'); } catch { examsCache = []; }
  return examsCache;
}
export const getExam = async (id) => (await loadExams()).find(e => e.id === id) || null;

/* ----- references ----- */
const refs = {};
export async function loadRef(name) {
  if (refs[name]) return refs[name];
  try { refs[name] = await fetchJSON(`/data/ref/${name}.json`); } catch { refs[name] = []; }
  return refs[name];
}
export async function loadRefs() {
  const [vocab, kanji, grammar] = await Promise.all([loadRef('vocab'), loadRef('kanji'), loadRef('grammar')]);
  return { vocab, kanji, grammar };
}

let refIndex = null;
async function buildRefIndex() {
  if (refIndex) return refIndex;
  const { vocab, kanji, grammar } = await loadRefs();
  const vocabByWord = new Map(), vocabByReading = new Map();
  for (const v of vocab) {
    if (v.word) { const k = normJa(v.word); if (!vocabByWord.has(k)) vocabByWord.set(k, []); vocabByWord.get(k).push(v); }
    if (v.reading) { const k = normJa(v.reading); if (!vocabByReading.has(k)) vocabByReading.set(k, []); vocabByReading.get(k).push(v); }
  }
  const kanjiMap = new Map(kanji.map(k => [k.kanji, k]));
  // grammar: core string to search for inside sentences
  const grammarCores = grammar.map(g => {
    const raw = (g.pattern || '').split(/[（(]/)[0].split(/[／/]|、|\s\/\s/)[0];
    const core = normJa(raw).replace(/^(V|N|Aい|Aな|い|な|普通形|ます形|て形|た形|ない形|辞書形|意向形|名詞|動詞)+/g, '');
    return { g, core };
  }).filter(x => x.core.length >= 2).sort((a, b) => b.core.length - a.core.length);
  refIndex = { vocab, kanji, grammar, vocabByWord, vocabByReading, kanjiMap, grammarCores };
  return refIndex;
}

/** Find reference entries related to a question (grammar patterns, vocab, kanji). */
export async function relatedRefs(q) {
  const idx = await buildRefIndex();
  const texts = [q.question, ...(q.options || [])].filter(Boolean);
  const all = texts.join('\n');

  // grammar
  const grammar = [];
  const seenG = new Set();
  if (q.section === 'bunpo' || q.section === 'dokkai') {
    for (const { g, core } of idx.grammarCores) {
      if (grammar.length >= 5) break;
      if (all.includes(core) && !seenG.has(g.pattern)) { seenG.add(g.pattern); grammar.push(g); }
    }
  }
  // vocab: exact option matches first, then words appearing in the stem
  const vocab = [];
  const seenV = new Set();
  const addV = (list) => { for (const v of list || []) { if (!seenV.has(v.word + v.reading)) { seenV.add(v.word + v.reading); vocab.push(v); } } };
  for (const o of q.options || []) { const k = normJa(o); addV(idx.vocabByWord.get(k)); addV(idx.vocabByReading.get(k)); }
  if (vocab.length < 6 && q.section !== 'dokkai') {
    const stem = normJa(q.question);
    for (const [k, list] of idx.vocabByWord) {
      if (vocab.length >= 6) break;
      if (k.length >= 2 && /[一-龯]/.test(k) && stem.includes(k)) addV(list);
    }
  }
  // kanji
  const kanji = [];
  for (const ch of kanjiChars(q.section === 'dokkai' ? (q.options || []).join('') : all)) {
    const k = idx.kanjiMap.get(ch); if (k) kanji.push(k);
    if (kanji.length >= 10) break;
  }
  return { grammar, vocab: vocab.slice(0, 6), kanji };
}

/* ----- exam composition ----- */
/** Group a list of question ids into pages (one passage = one page). */
export function toItems(qids) {
  const items = [];
  for (const id of qids) {
    const q = getQ(id); if (!q) continue;
    const pid = q.passage_id || null;
    const last = items[items.length - 1];
    if (pid && last && last.pid === pid) last.qids.push(id);
    else items.push({ pid, qids: [id] });
  }
  return items;
}

/** Build a random JLPT-shaped set for a section, avoiding recently seen ids. */
export function composeSection(section, { statsOf = () => null, scale = 1, exclude = new Set() } = {}) {
  const out = [];
  const typeList = typesOf(section).filter(t => TYPES[t].count > 0);
  for (const t of typeList) {
    const want = Math.max(1, Math.round(TYPES[t].count * scale));
    // đề ngẫu nhiên: ưu tiên nguồn hạng A (lấy từ đề mô phỏng); chỉ bù bằng hạng B khi thiếu
    let pool = questionsOfType(t).filter(q => !exclude.has(q.id) && q.tier !== 'B' && !q.suspect);
    if (pool.length < want * 2) pool = questionsOfType(t).filter(q => !exclude.has(q.id) && !q.suspect);
    if (!pool.length) continue;
    if (TYPES[t].passage) {
      // choose whole passages until we reach `want` questions
      const byP = new Map();
      for (const q of pool) { const k = q.passage_id || q.id; (byP.get(k) || byP.set(k, []).get(k)).push(q); }
      const groups = shuffle(Array.from(byP.values())).sort((a, b) => freshness(a, statsOf) - freshness(b, statsOf));
      let n = 0;
      for (const g of groups) { if (n >= want) break; out.push(...g.map(q => q.id)); n += g.length; }
    } else {
      // prefer unseen, then wrong, then anything
      const ranked = shuffle(pool).sort((a, b) => freshness([a], statsOf) - freshness([b], statsOf));
      out.push(...ranked.slice(0, want).map(q => q.id));
    }
  }
  return out;
}
/** lower = more deserving: unseen (0) < wrong before (1) < seen & correct (2 + n) */
function freshness(group, statsOf) {
  let score = 0;
  for (const q of group) {
    const s = statsOf(q.id);
    if (!s) score += 0;
    else if (s.w > 0 && s.c === 0) score += 1;
    else score += 2 + s.c;
  }
  return score / group.length + Math.random() * 0.5;
}

/** Drill pool by types with simple strategy. */
export function composeDrill({ types, count, strategy = 'mixed', statsOf = () => null, exclude = new Set(), includeB = true }) {
  let pool = [];
  for (const t of types) pool.push(...questionsOfType(t));
  pool = pool.filter(q => !exclude.has(q.id) && !TYPES[q.type].passage && (includeB || q.tier !== 'B') && !q.suspect);
  if (strategy === 'unseen') { const u = pool.filter(q => !statsOf(q.id)); if (u.length >= Math.min(count, 5)) pool = u; }
  if (strategy === 'wrong') { const w = pool.filter(q => { const s = statsOf(q.id); return s && s.w > 0; }); if (w.length) pool = w; }
  if (strategy === 'mixed') pool = shuffle(pool).sort((a, b) => freshness([a], statsOf) - freshness([b], statsOf)).slice(0, count * 3);
  return pick(pool, count).map(q => q.id);
}

/** Drill on passages (dokkai / text grammar): returns ids of `count` passages' questions. */
export function composePassageDrill({ types, count, statsOf = () => null, includeB = true }) {
  const byP = new Map();
  for (const t of types) for (const q of questionsOfType(t)) { if (!includeB && q.tier === 'B') continue; const k = q.passage_id || q.id; (byP.get(k) || byP.set(k, []).get(k)).push(q); }
  const groups = shuffle(Array.from(byP.values())).sort((a, b) => freshness(a, statsOf) - freshness(b, statsOf));
  return groups.slice(0, count).flatMap(g => g.map(q => q.id));
}
