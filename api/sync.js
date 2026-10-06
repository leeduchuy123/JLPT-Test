/* ---------- Vercel Function: kho đồng bộ tiến độ (1 người dùng) ----------
   GET /api/sync?rev=N   → { rev, same: true } nếu máy chủ vẫn ở rev N; ngược lại { rev, blob } (blob null = chưa có dữ liệu)
   GET /api/sync?probe=1 → { rev }  (chỉ kiểm tra mật khẩu / cấu hình)
   PUT /api/sync  { baseRev, blob } → { rev }, hoặc 409 { rev } nếu máy khác đã đẩy trước (client tải về, gộp, đẩy lại)
   Xác thực: "Authorization: Bearer <SYNC_PASSWORD>". Sai 20 lần trong 15 phút từ một IP → khoá IP đó (429).
   Lưu trữ: Upstash Redis qua REST API (không cần thư viện). Nhận UPSTASH_REDIS_REST_URL/_TOKEN hoặc
   <PREFIX>_REST_API_URL/_TOKEN (biến do tích hợp Upstash trên Vercel Marketplace tạo, mặc định KV_).
   blob là chuỗi do trình duyệt tạo ("gz:" + base64 gzip JSON, hoặc "js:" + JSON); máy chủ không đọc nội dung.
*/
import { createHash, timingSafeEqual } from 'node:crypto';

const K_STATE = 'jlpt:sync:state';
const K_REV = 'jlpt:sync:rev';
const FAIL_PREFIX = 'jlpt:sync:fail:';
const MAX_FAILS = 20;
const FAIL_WINDOW_S = 900;
const MAX_BLOB = 3_500_000; // giới hạn body của Vercel Functions là 4.5 MB

// Lua chạy nguyên tử trong Redis. KEYS: state, rev, fail-counter của IP. Trả {-1} nếu IP đang bị khoá.
const READ_SCRIPT = `
if tonumber(redis.call('GET', KEYS[3]) or '0') >= tonumber(ARGV[2]) then return {-1} end
local rev = tonumber(redis.call('GET', KEYS[2]) or '0')
if ARGV[1] == 'probe' or tonumber(ARGV[1]) == rev then return {rev} end
return {rev, redis.call('GET', KEYS[1]) or ''}
`;
const WRITE_SCRIPT = `
if tonumber(redis.call('GET', KEYS[3]) or '0') >= tonumber(ARGV[3]) then return {-1} end
local rev = tonumber(redis.call('GET', KEYS[2]) or '0')
if rev ~= tonumber(ARGV[1]) then return {0, rev} end
redis.call('SET', KEYS[1], ARGV[2])
return {1, redis.call('INCR', KEYS[2])}
`;

function redisEnv() {
  const env = process.env;
  if (env.UPSTASH_REDIS_REST_URL && env.UPSTASH_REDIS_REST_TOKEN) return [env.UPSTASH_REDIS_REST_URL, env.UPSTASH_REDIS_REST_TOKEN];
  for (const k of Object.keys(env)) {
    if (!k.endsWith('_REST_API_URL')) continue;
    const token = env[k.replace(/_URL$/, '_TOKEN')];
    if (env[k] && token) return [env[k], token];
  }
  return null;
}

async function redis(cmds) {
  const [url, token] = redisEnv();
  const r = await fetch(`${url.replace(/\/+$/, '')}/pipeline`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(cmds),
  });
  if (!r.ok) throw new Error(`Upstash HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return (await r.json()).map(x => { if (x.error) throw new Error(`Upstash: ${x.error}`); return x.result; });
}

const reply = (status, body) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } });

const failKey = (req) => FAIL_PREFIX + ((req.headers.get('x-forwarded-for') || '').split(',')[0].trim() || req.headers.get('x-real-ip') || 'unknown');

/** Client gửi encodeURIComponent(mật khẩu dạng NFC) vì header chỉ nhận ASCII; so sánh băm để không lộ thời gian. */
function passwordOk(req) {
  const h = req.headers.get('authorization') || '';
  const given = h.startsWith('Bearer ') ? h.slice(7) : '';
  const expected = encodeURIComponent(process.env.SYNC_PASSWORD.normalize('NFC').trim());
  const digest = (s) => createHash('sha256').update(s).digest();
  return given !== '' && timingSafeEqual(digest(given), digest(expected));
}

/** null nếu được phép; ngược lại là Response lỗi. Mật khẩu đúng vẫn bị chặn trong script nếu IP đang bị khoá. */
async function guard(req) {
  if (!(process.env.SYNC_PASSWORD || '').trim() || !redisEnv()) return reply(503, { error: 'not-configured' });
  if (passwordOk(req)) return null;
  const key = failKey(req);
  const [n] = await redis([['INCR', key], ['EXPIRE', key, String(FAIL_WINDOW_S)]]);
  return n >= MAX_FAILS ? reply(429, { error: 'locked' }) : reply(401, { error: 'unauthorized' });
}

export async function GET(req) {
  try {
    const denied = await guard(req);
    if (denied) return denied;
    const q = new URL(req.url).searchParams;
    const want = q.has('probe') ? 'probe' : (q.get('rev') || '');
    const [res] = await redis([['EVAL', READ_SCRIPT, '3', K_STATE, K_REV, failKey(req), want, String(MAX_FAILS)]]);
    if (res[0] === -1) return reply(429, { error: 'locked' });
    const rev = res[0];
    if (res.length === 1) return reply(200, want === 'probe' ? { rev } : { rev, same: true });
    return reply(200, { rev, blob: res[1] || null });
  } catch (e) {
    console.error(e);
    return reply(500, { error: 'server' });
  }
}

export async function PUT(req) {
  try {
    const denied = await guard(req);
    if (denied) return denied;
    let body;
    try { body = await req.json(); } catch { return reply(400, { error: 'bad-json' }); }
    const { baseRev, blob } = body || {};
    if (!Number.isInteger(baseRev) || baseRev < 0 || typeof blob !== 'string' || !/^(gz|js):/.test(blob)) {
      return reply(400, { error: 'bad-request' });
    }
    if (blob.length > MAX_BLOB) return reply(413, { error: 'too-large' });
    const [res] = await redis([['EVAL', WRITE_SCRIPT, '3', K_STATE, K_REV, failKey(req), String(baseRev), blob, String(MAX_FAILS)]]);
    if (res[0] === -1) return reply(429, { error: 'locked' });
    if (res[0] === 0) return reply(409, { rev: res[1] });
    return reply(200, { rev: res[1] });
  } catch (e) {
    console.error(e);
    return reply(500, { error: 'server' });
  }
}
