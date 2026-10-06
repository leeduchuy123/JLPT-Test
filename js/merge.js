/* ---------- Gộp hai bản tiến độ (đồng bộ nhiều thiết bị) ----------
   Hàm thuần, không dùng DOM, nên chạy được cả trong Node để test.
   - stats / srs / notes / inProgress: mỗi mục giữ bản sửa sau cùng; mục đã xoá (meta.del) chỉ sống lại
     nếu được sửa sau lúc xoá.
   - history: hợp theo id, bỏ bài đã xoá, giữ HISTORY_CAP bài mới nhất.
   - daily: mỗi thiết bị một bộ đếm riêng (by[device]) → lấy bản lớn nhất của từng thiết bị rồi cộng lại,
     nên học cùng một ngày trên hai máy không mất số câu.
   - settings: bản sửa sau cùng thắng, riêng theme giữ theo từng máy.
   - meta.epoch: "Xoá toàn bộ" / "Nhập file" tạo epoch mới; phía epoch cũ chỉ giữ những gì sửa sau mốc đó.
   Hoà (cùng thời điểm) thì lấy bản remote, để mọi máy hội tụ về cùng một kết quả.
*/
export const HISTORY_CAP = 300;
const TOMB_TTL = 180 * 86400000;
const GENESIS = { id: '0', at: 0 };

/** Thời điểm sửa cuối của một mục, theo từng loại dữ liệu. */
const timeOf = {
  stats: (s) => Math.max(s.u || 0, s.last || 0),
  srs: (c) => c.u || Math.max(c.last || 0, c.added || 0),
  notes: (_, id, meta) => meta.noteAt[id] || 0,
  inProgress: (s) => s.updatedAt || s.createdAt || s.startedAt || 0,
};
const COLLS = Object.keys(timeOf);

export function normMeta(m) {
  return {
    epoch: m && m.epoch && m.epoch.id != null ? m.epoch : { ...GENESIS },
    del: { ...(m && m.del) },
    noteAt: { ...(m && m.noteAt) },
    settingsAt: (m && m.settingsAt) || 0,
  };
}

/** Bộ đếm theo thiết bị của một ngày; bản ghi cũ (chưa có by) được tính là của `owner`. */
export const byOf = (d, owner) => (!d ? {} : d.by || { [owner]: { a: d.answered || 0, c: d.correct || 0, s: d.secs || 0 } });
export function totals(by) {
  let a = 0, c = 0, s = 0;
  for (const v of Object.values(by)) { a += v.a || 0; c += v.c || 0; s += v.s || 0; }
  return { answered: a, correct: c, secs: s, by };
}

/**
 * @param local  state trên máy này
 * @param remote state tải từ máy chủ (null = máy chủ chưa có gì)
 * @param opts.device id thiết bị này (để gán bộ đếm ngày cũ)
 * @returns state mới; không sửa đầu vào
 */
export function mergeStates(local, remote, { device = '_', now = Date.now() } = {}) {
  if (!remote) return local;
  const theme = local.settings && local.settings.theme;
  let a = local, b = remote;
  const ea = normMeta(a.meta).epoch, eb = normMeta(b.meta).epoch;
  if (ea.id !== eb.id) {
    const bNewer = eb.at > ea.at || (eb.at === ea.at && String(eb.id) > String(ea.id));
    if (bNewer) a = since(a, eb); else b = since(b, ea);
  }
  const out = mergeSame(a, b, { device, now });
  if (theme !== undefined) out.settings = { ...out.settings, theme };
  return out;
}

/** Phần của `s` còn hiệu lực sau mốc `epoch` (bên kia đã xoá toàn bộ / nhập file lúc epoch.at). */
function since(s, epoch) {
  const meta = normMeta(s.meta), cut = epoch.at;
  const out = { ...s, daily: {}, settings: meta.settingsAt > cut ? s.settings : undefined };
  for (const name of COLLS) {
    out[name] = Object.fromEntries(Object.entries(s[name] || {}).filter(([id, v]) => timeOf[name](v, id, meta) > cut));
  }
  out.history = (s.history || []).filter(h => (h.t || 0) > cut);
  const after = (obj) => Object.fromEntries(Object.entries(obj).filter(([, t]) => t > cut));
  out.meta = { epoch, del: after(meta.del), noteAt: after(meta.noteAt), settingsAt: meta.settingsAt > cut ? meta.settingsAt : 0 };
  return out;
}

function mergeSame(a, b, { device, now }) {
  const ma = normMeta(a.meta), mb = normMeta(b.meta);

  const del = {};
  for (const [k, t] of [...Object.entries(ma.del), ...Object.entries(mb.del)]) {
    if (t > now - TOMB_TTL && !(del[k] >= t)) del[k] = t;
  }

  const out = { ...b, ...a, version: Math.max(a.version || 2, b.version || 2) };

  for (const name of COLLS) {
    const A = a[name] || {}, B = b[name] || {}, res = {};
    const time = timeOf[name];
    for (const id of new Set([...Object.keys(A), ...Object.keys(B)])) {
      const x = A[id], y = B[id];
      const tx = x === undefined ? -1 : time(x, id, ma);
      const ty = y === undefined ? -1 : time(y, id, mb);
      const [win, t] = tx > ty ? [x, tx] : [y, ty];
      const d = del[`${name}/${id}`];
      if (d != null && t <= d) continue;
      res[id] = win;
    }
    out[name] = res;
  }

  const noteAt = {};
  for (const id of Object.keys(out.notes)) {
    const t = Math.max(ma.noteAt[id] || 0, mb.noteAt[id] || 0);
    if (t) noteAt[id] = t;
  }

  const seen = new Map();
  for (const h of [...(b.history || []), ...(a.history || [])]) {
    const id = h.id != null ? h.id : `t${h.t}`;
    if (!seen.has(id) && del[`history/${id}`] == null) seen.set(id, h);
  }
  out.history = [...seen.values()].sort((x, y) => (y.t || 0) - (x.t || 0)).slice(0, HISTORY_CAP);

  out.daily = {};
  const DA = a.daily || {}, DB = b.daily || {};
  for (const day of new Set([...Object.keys(DA), ...Object.keys(DB)])) {
    const ba = byOf(DA[day], device), bb = byOf(DB[day], '_');
    const by = {};
    for (const dev of new Set([...Object.keys(ba), ...Object.keys(bb)])) {
      const x = ba[dev], y = bb[dev];
      by[dev] = !x ? y : !y ? x : (x.a > y.a || (x.a === y.a && (x.s || 0) > (y.s || 0))) ? x : y;
    }
    out.daily[day] = totals(by);
  }

  const settingsFromA = b.settings === undefined || (a.settings !== undefined && ma.settingsAt > mb.settingsAt);
  out.settings = { ...(settingsFromA ? a.settings : b.settings) };

  out.meta = {
    epoch: ma.epoch,
    del,
    noteAt,
    settingsAt: Math.max(ma.settingsAt, mb.settingsAt),
  };
  return out;
}

/** JSON chuẩn hoá (khoá sắp xếp) để so sánh hai state bất kể thứ tự khoá. */
export function canon(v) {
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']';
  if (v && typeof v === 'object') {
    return '{' + Object.keys(v).filter(k => v[k] !== undefined).sort().map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}';
  }
  return JSON.stringify(v) ?? 'null';
}

/** Hai state có khác nhau không (bỏ qua theme vì theme không đồng bộ). */
export function differs(x, y) {
  const strip = (s) => ({ ...s, settings: { ...(s.settings || {}), theme: undefined } });
  return canon(strip(x)) !== canon(strip(y));
}
