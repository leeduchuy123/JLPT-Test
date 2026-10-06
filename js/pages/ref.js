/* ---------- Tra cứu: từ vựng / kanji / ngữ pháp N3 ---------- */
import { $, $$, esc, debounce, normJa } from '../util.js';
import { loadRefs } from '../data.js';

export async function render(app, route) {
  const refs = await loadRefs();
  let tab = route.params.tab || 'grammar';
  let query = route.params.q || '';
  let limit = 60;

  const draw = () => {
    const list = filtered(refs[tab], tab, query);
    app.innerHTML = `
      <h1>Tra cứu</h1>
      <div class="tabs">
        <button class="${tab === 'grammar' ? 'active' : ''}" data-tab="grammar">Ngữ pháp (${refs.grammar.length})</button>
        <button class="${tab === 'vocab' ? 'active' : ''}" data-tab="vocab">Từ vựng (${refs.vocab.length.toLocaleString('vi')})</button>
        <button class="${tab === 'kanji' ? 'active' : ''}" data-tab="kanji">Kanji (${refs.kanji.length})</button>
      </div>
      <div class="search-bar">
        <input class="input" id="q" type="search" placeholder="${tab === 'grammar' ? 'Tìm mẫu ngữ pháp hoặc nghĩa, ví dụ: ばかり, chỉ toàn' : tab === 'vocab' ? 'Tìm từ, cách đọc hoặc nghĩa tiếng Việt' : 'Tìm kanji, âm Hán Việt, nghĩa'}" value="${esc(query)}" autofocus>
        <span class="small muted" style="align-self:center">${list.length.toLocaleString('vi')} kết quả</span>
      </div>
      <div class="ref-list" id="list">${list.slice(0, limit).map(x => card(x, tab)).join('')}</div>
      ${list.length > limit ? `<button class="btn mt" id="more">Xem thêm (${list.length - limit})</button>` : ''}`;
    $$('[data-tab]', app).forEach(b => b.onclick = () => { tab = b.dataset.tab; limit = 60; draw(); });
    const inp = $('#q', app);
    inp.oninput = debounce(() => { query = inp.value; limit = 60; const l = filtered(refs[tab], tab, query); $('#list', app).innerHTML = l.slice(0, limit).map(x => card(x, tab)).join(''); $('.search-bar .muted', app).textContent = `${l.length.toLocaleString('vi')} kết quả`; $('#more', app)?.toggleAttribute('hidden', l.length <= limit); }, 150);
    $('#more', app)?.addEventListener('click', () => { limit += 100; draw(); $('#q', app).blur(); });
  };
  draw();
}

function filtered(list, tab, q) {
  if (!q.trim()) return list;
  const n = normJa(q).toLowerCase(), raw = q.trim().toLowerCase();
  return list.filter(x => {
    if (tab === 'grammar') return normJa(x.pattern).includes(n) || (x.meaning_vi || '').toLowerCase().includes(raw) || (x.meaning_en || '').toLowerCase().includes(raw);
    if (tab === 'vocab') return (x.word || '').includes(q.trim()) || (x.reading || '').includes(q.trim()) || (x.meaning_vi || '').toLowerCase().includes(raw) || (x.meaning_en || '').toLowerCase().includes(raw);
    return x.kanji === q.trim() || (x.hanviet || '').toLowerCase().includes(raw) || (x.meaning_vi || '').toLowerCase().includes(raw) || (x.meaning_en || '').toLowerCase().includes(raw) || (x.on || []).some(r => r.includes(q.trim())) || (x.kun || []).some(r => r.includes(q.trim()));
  });
}

function card(x, tab) {
  if (tab === 'grammar') return `<div class="ref-card">
    <span class="ref-ja">${esc(x.pattern)}</span><span>${esc(x.meaning_vi || x.meaning_en || '')}${x.meaning_vi && x.meaning_en ? `<span class="muted small"> · ${esc(x.meaning_en)}</span>` : ''}</span>
    <div class="meta">${x.structure ? `<div><b>Cấu trúc:</b> <span class="ja">${esc(x.structure)}</span></div>` : ''}
      ${(x.examples || []).slice(0, 2).map(e => `<div><span class="ja">${esc(e.ja)}</span>${(e.vi || e.en) ? `<br><span class="small">${esc(e.vi || e.en)}</span>` : ''}</div>`).join('')}
      ${x.notes ? `<div class="small muted">${esc(x.notes)}</div>` : ''}</div></div>`;
  if (tab === 'vocab') return `<div class="ref-card">
    <span class="ref-ja">${esc(x.word)}</span><span><span class="ja muted">${esc(x.reading || '')}</span> ${esc(x.meaning_vi || x.meaning_en || '')}${x.pos ? ` <span class="pill">${esc(x.pos)}</span>` : ''}</span>
    ${x.meaning_vi && x.meaning_en ? `<div class="meta small">${esc(x.meaning_en)}</div>` : ''}</div>`;
  return `<div class="ref-card">
    <span class="ref-ja kanji">${esc(x.kanji)}</span><span>${x.hanviet ? `<b>${esc(x.hanviet)}</b> · ` : ''}${esc(x.meaning_vi || x.meaning_en || '')}${x.strokes ? ` <span class="pill">${x.strokes} nét</span>` : ''}</span>
    <div class="meta"><span class="ja">音 ${esc((x.on || []).join('・') || '—')}　訓 ${esc((x.kun || []).join('・') || '—')}</span>
      ${(x.examples || []).length ? `<div class="ja small">${x.examples.slice(0, 4).map(e => `${esc(e.word)}（${esc(e.reading || '')}）${e.meaning_vi ? ' ' + esc(e.meaning_vi) : ''}`).join('　')}</div>` : ''}</div></div>`;
}
