/* ---------- Học N2: dữ liệu khoá học, lịch tuần, render văn bản ----------
   Lộ trình mỗi track (文法 / 語彙 / 読解) chia theo tuần, mỗi tuần 4 bài:
     T2 課a · T3 課b · T4 練習(a,b) · T5 課c · T6 課d · T7 練習(c,d) · CN まとめ問題(a–d)
   Tiến độ lưu ở store.study[activityId]; activityId = `<track>:L:<unit>` | `<track>:P:<u1>+<u2>` | `<track>:M:<u1>+…`.
*/
import { esc, todayKey, daysBetween, DAY } from './util.js';
import * as store from './store.js';

let indexP = null;
const lessonCache = new Map();

export function loadIndex() {
  if (!indexP) indexP = fetch('/data/study/index.json').then(r => {
    if (!r.ok) throw new Error('Không tải được khoá học N2 (data/study/index.json)');
    return r.json();
  }).catch(e => { indexP = null; throw e; });
  return indexP;
}
export function loadLesson(track, id) {
  const key = `${track}/${id}`;
  if (!lessonCache.has(key)) {
    lessonCache.set(key, fetch(`/data/study/${key}.json`).then(r => {
      if (!r.ok) throw new Error(`Bài ${id} chưa có nội dung`);
      return r.json();
    }).catch(e => { lessonCache.delete(key); throw e; }));
  }
  return lessonCache.get(key);
}

export const TRACK_SHORT = { bunpo: 'Ngữ pháp', goi: 'Từ vựng', dokkai: 'Đọc hiểu' };
export const WEEKDAYS = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật'];

/** Các buổi của một track theo lịch tuần. Mỗi phần tử: {id, type L|P|M, units:[unit], week, slot (0=T2…6=CN), label, title, seq}. */
export function scheduleOf(track) {
  const out = [];
  const units = track.units;
  let practiceNo = 0;
  for (let w = 0; w * 4 < units.length; w++) {
    const chunk = units.slice(w * 4, w * 4 + 4);
    const [a, b, c, d] = chunk;
    const push = (slot, type, us) => {
      if (!us.length || us.some(u => !u)) return;
      const id = `${track.id}:${type}:${us.map(u => u.id).join('+')}`;
      let label, title;
      if (type === 'L') { label = us[0].label; title = us[0].title; }
      else if (type === 'P') { practiceNo++; label = `練習 ${practiceNo}`; title = `Luyện tập ${us.map(u => u.label).join(' + ')}`; }
      else { label = `まとめ問題 ${w + 1}`; title = `Kiểm tra tổng hợp ${us.map(u => u.label).join(', ')}`; }
      out.push({ id, type, units: us, week: w, slot, label, title });
    };
    push(0, 'L', [a]);
    push(1, 'L', b ? [b] : []);
    push(2, 'P', [a, b].filter(Boolean));
    push(3, 'L', c ? [c] : []);
    push(4, 'L', d ? [d] : []);
    push(5, 'P', [c, d].filter(Boolean));
    push(6, 'M', chunk);
  }
  out.forEach((x, i) => { x.seq = i; x.ready = x.units.every(u => u.ready); });
  return out;
}

/* ----- kế hoạch (ngày bắt đầu) lưu trong settings.study ----- */
export function studySettings() {
  const s = store.settings().study || {};
  return { plans: {}, furigana: true, ...s, plans: { ...(s.plans || {}) } };
}
export function setStudySettings(patch) {
  store.setSetting('study', { ...studySettings(), ...patch });
}
export function setPlan(trackId, start) {
  const cur = studySettings();
  const plans = { ...cur.plans };
  if (start) plans[trackId] = start; else delete plans[trackId];
  setStudySettings({ plans });
}
export const planOf = (trackId) => studySettings().plans[trackId] || null;

/** Thứ 2 của tuần chứa ts (hoặc tuần sau nếu next). Trả về 'YYYY-MM-DD'. */
export function mondayOf(ts = Date.now(), next = false) {
  const d = new Date(ts); d.setHours(12, 0, 0, 0);
  const dow = (d.getDay() + 6) % 7; // 0 = thứ 2
  d.setDate(d.getDate() - dow + (next ? 7 : 0));
  return todayKey(d);
}
export const keyToTs = (k) => new Date(k + 'T12:00:00').getTime();

/** Ngày dự kiến của một buổi theo kế hoạch. */
export function dateOf(item, start) {
  if (!start) return null;
  return keyToTs(start) + (item.week * 7 + item.slot) * DAY;
}

/** Trạng thái track: buổi tiếp theo cần làm, buổi theo lịch hôm nay, số buổi chậm. */
export function trackStatus(track) {
  const items = scheduleOf(track);
  const start = planOf(track.id);
  const done = items.filter(x => store.studyOf(x.id)?.done).length;
  const next = items.find(x => !store.studyOf(x.id)?.done) || null;
  let today = null, behind = 0, dayNo = null;
  if (start) {
    dayNo = daysBetween(keyToTs(start), Date.now());
    today = items.find(x => x.week * 7 + x.slot === dayNo) || null;
    behind = items.filter(x => x.week * 7 + x.slot < dayNo && !store.studyOf(x.id)?.done).length;
  }
  return { items, start, done, total: items.length, next, today, behind, dayNo };
}

/* ----- câu hỏi của một buổi ----- */
/** Gom câu hỏi (kèm đoạn văn) của các bài cho buổi luyện / kiểm tra. */
export async function questionsFor(item) {
  const set = item.type === 'P' ? 'practice' : item.type === 'M' ? 'test' : 'quiz';
  const track = item.id.split(':')[0];
  const lessons = await Promise.all(item.units.map(u => loadLesson(track, u.id)));
  const groups = []; // giữ câu cùng đoạn văn liền nhau
  for (const L of lessons) {
    const byPass = new Map();
    for (const q of L[set] || []) {
      const qq = { ...q, _lesson: L.id, _passage: q.pass ? L.passages?.[q.pass] : null };
      if (q.pass) {
        const k = L.id + '/' + q.pass;
        if (!byPass.has(k)) { byPass.set(k, []); groups.push(byPass.get(k)); }
        byPass.get(k).push(qq);
      } else groups.push([qq]);
    }
  }
  return { lessons, groups };
}

/* ----- render văn bản ----- */
const RUBY = /\{([^{}|]+)\|([^{}|]+)\}/g;

/** Câu tiếng Nhật: furigana {漢字|かな}, gạch chân [[u:…]] / [[u1:…]]; stem = câu hỏi (vẽ ô ＿＿＿ / ★ / （　　）). */
export function ja(text, stem = false) {
  let h = esc(text || '');
  h = h.replace(RUBY, '<ruby>$1<rt>$2</rt></ruby>');
  h = h.replace(/\[\[u(\d*):([\s\S]*?)\]\]/g, (_, n, t) => n ? `<span class="u-num">${n}</span><u>${t}</u>` : `<u>${t}</u>`);
  if (stem) {
    h = h.replace(/＿＿＿/g, '<span class="blank"></span>');
    h = h.replace(/★/g, '<span class="blank star">★</span>');
    h = h.replace(/（[\s　]*）/g, '（<span class="paren-blank"></span>）');
  }
  return h.replace(/\n/g, '<br>');
}

/** Văn bản giải thích: đoạn (\n\n), gạch đầu dòng (- ), **đậm**, furigana, ✗ / ○. */
export function rich(text) {
  if (!text) return '';
  const paras = String(text).split(/\n{2,}/);
  let html = '';
  for (const p of paras) {
    let text = [], list = [];
    const flushText = () => { if (text.length) html += `<p>${text.join('<br>')}</p>`; text = []; };
    const flushList = () => { if (list.length) html += `<ul>${list.map(x => `<li>${x}</li>`).join('')}</ul>`; list = []; };
    for (const line of p.split('\n')) {
      const m = line.match(/^\s*[-•]\s+(.*)$/);
      if (m) { flushText(); list.push(inline(m[1])); }
      else if (line.trim()) { flushList(); text.push(inline(line)); }
    }
    flushText(); flushList();
  }
  return html;
}
function inline(s) {
  return ja(s)
    .replace(/\*\*([^*]+?)\*\*/g, '<b>$1</b>')
    .replace(/✗/g, '<span class="x-mark">✗</span>')
    .replace(/○/g, '<span class="o-mark">○</span>');
}

/** Bỏ furigana / đánh dấu → chữ thường (cho tìm kiếm, tiêu đề). */
export const plain = (s) => String(s || '').replace(RUBY, '$1').replace(/\[\[u\d*:([\s\S]*?)\]\]/g, '$1');

export function applyFurigana() {
  document.documentElement.classList.toggle('no-furi', studySettings().furigana === false);
}
