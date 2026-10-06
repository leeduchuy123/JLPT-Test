/* ---------- App shell: router, theme, nav ---------- */
import { $, $$, esc } from './util.js';
import * as store from './store.js';
import { loadBank, bankAliases, getQ } from './data.js';

const pages = {
  '/': () => import('./pages/home.js'),
  '/test': () => import('./pages/test.js'),
  '/drill': () => import('./pages/drill.js'),
  '/review': () => import('./pages/review.js'),
  '/progress': () => import('./pages/progress.js'),
  '/ref': () => import('./pages/ref.js'),
  '/settings': () => import('./pages/settings.js'),
};

let cleanup = null;

export function parseRoute() {
  const hash = location.hash.replace(/^#/, '') || '/';
  const [path, qs] = hash.split('?');
  const segs = path.split('/').filter(Boolean);
  const base = '/' + (segs[0] || '');
  const params = Object.fromEntries(new URLSearchParams(qs || ''));
  return { base, segs: segs.slice(1), params, path };
}

export const navigate = (hash) => { location.hash = hash; };

async function render() {
  const app = $('#app');
  const route = parseRoute();
  const loader = pages[route.base];

  $$('#nav a').forEach(a => a.classList.toggle('active', a.dataset.route === route.base));

  if (typeof cleanup === 'function') { try { cleanup(); } catch { /* ignore */ } cleanup = null; }

  if (!loader) {
    app.innerHTML = `<div class="card"><h1>404</h1><p>Không có trang <code>${esc(route.path)}</code>. <a href="#/">Về trang chủ</a></p></div>`;
    return;
  }
  app.innerHTML = '<p class="muted">Đang tải...</p>';
  try {
    const firstLoad = !window.__bankReady;
    await loadBank();
    if (firstLoad) { window.__bankReady = true; store.migrateAliases(bankAliases(), (id) => !!getQ(id) && getQ(id).id === id); }
    const mod = await loader();
    const result = await mod.render(app, route);
    if (typeof result === 'function') cleanup = result;
  } catch (err) {
    console.error(err);
    app.innerHTML = `<div class="card"><h2>Có lỗi xảy ra</h2><p>${esc(err.message)}</p><a class="btn" href="#/">Về trang chủ</a></div>`;
  }
  if (!route.params.keepScroll) window.scrollTo({ top: 0 });
  updateNavBadge();
}

export function updateNavBadge() {
  const n = store.dueCards().length;
  const el = $('#nav-due');
  if (!el) return;
  el.textContent = n;
  el.hidden = n === 0;
}

/* ----- theme ----- */
const mq = window.matchMedia('(prefers-color-scheme: dark)');
export function applyTheme() {
  const t = store.settings().theme;
  const root = document.documentElement;
  if (t === 'light' || t === 'dark') root.setAttribute('data-theme', t); else root.removeAttribute('data-theme');
  root.classList.toggle('sys-dark', mq.matches);
  const dark = t === 'dark' || (t === 'system' && mq.matches);
  $('meta[name="theme-color"]')?.setAttribute('content', dark ? '#141c2f' : '#1c5cab');
}
mq.addEventListener('change', applyTheme);

/* ----- boot ----- */
applyTheme();
window.addEventListener('hashchange', render);
if (document.readyState === 'loading') window.addEventListener('DOMContentLoaded', render); else render();
document.addEventListener('srs-changed', updateNavBadge);
window.addEventListener('beforeunload', () => store.save(true));
