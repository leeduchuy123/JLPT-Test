/* ---------- Shared question renderer (test, drill, review, result) ---------- */
import { esc, escText, renderStem, toast, debounce } from './util.js';
import { getQ, getPassage, relatedRefs, TYPES, SECTIONS } from './data.js';
import * as store from './store.js';
import { boxLabel } from './srs.js';

const LETTERS = ['1', '2', '3', '4', '5', '6'];

export function sectionPill(section) {
  return `<span class="pill ${section}">${esc(SECTIONS[section]?.short || section)}</span>`;
}
export function typePill(type) {
  const t = TYPES[type];
  return t ? `<span class="pill">${t.mondai ? `問題${t.mondai} · ` : ''}${esc(t.label)}</span>` : '';
}

/** Passage block (Japanese + translation once revealed). */
export function renderPassage(pid, { reveal = false } = {}) {
  const p = getPassage(pid);
  const div = document.createElement('div');
  div.className = 'passage';
  if (!p) { div.textContent = '(Không tìm thấy đoạn văn)'; return div; }
  div.innerHTML = `<div class="ja">${renderStem(p.text)}</div>` +
    (reveal ? `<div class="vi">${p.vi
      ? `<details open><summary style="cursor:pointer;font-weight:600">Bản dịch tiếng Việt</summary>${escText(p.vi)}</details>`
      : '<i class="muted">Chưa có bản dịch cho đoạn này.</i>'}</div>` : '');
  return div;
}

/**
 * Render one question card.
 * opts: { index, selected, reveal, interactive, onSelect, compact, showMeta }
 */
export function renderQuestion(q, opts = {}) {
  const { index = null, selected = null, reveal = false, interactive = true, onSelect = null, showMeta = true, compact = false } = opts;
  const card = document.createElement('article');
  card.className = 'question';
  card.dataset.qid = q.id;

  const correct = q.answer;
  const isShort = (q.options || []).every(o => o.length <= 12);
  const ex = q.ex || null;

  const head = `
    <div class="q-head">
      ${index != null ? `<span class="q-num">${esc(index)}</span>` : ''}
      ${showMeta ? sectionPill(q.section) + typePill(q.type) : ''}
      ${reveal && selected != null ? (selected === correct ? '<span class="pill good">Đúng</span>' : '<span class="pill bad">Sai</span>') : ''}
      ${reveal && selected == null ? '<span class="pill warn">Bỏ trống</span>' : ''}
      ${q.suspect ? '<span class="pill warn" title="Câu gốc có thể sai đáp án, có 2 đáp án hợp lý hoặc có lỗi đánh máy. Xem phần giải thích. Câu này không được chọn vào bài luyện mới.">⚠ câu gốc có vấn đề</span>' : ''}
      ${store.inSrs(q.id) ? `<span class="srs-tag">⟳ ${esc(boxLabel(store.get().srs[q.id].box))}</span>` : ''}
    </div>`;

  const audio = q.audio ? audioHTML(q.audio) : '';
  const image = q.image ? `<p><img src="${esc(q.image)}" alt="" style="max-width:100%;border-radius:8px"></p>` : '';

  const options = (q.options || []).map((o, i) => {
    const cls = ['opt'];
    if (reveal) {
      if (i === correct) cls.push('correct');
      else if (i === selected) cls.push('wrong');
    } else if (i === selected) cls.push('selected');
    const exOpt = reveal && ex && ex.opts && ex.opts[i] ? `<span class="opt-ex">${esc(ex.opts[i])}</span>` : '';
    return `<button type="button" class="${cls.join(' ')}" data-i="${i}" ${(!interactive || reveal) ? 'disabled' : ''}>
      <span class="n">${LETTERS[i]}</span><span class="opt-body">${renderStem(o)}${exOpt}</span></button>`;
  }).join('');

  card.innerHTML = `
    ${head}
    ${audio}${image}
    <div class="q-text">${q.type === 'listening' && /^(\d+番|（音声.*）|音声を聞いて.*)$/.test(q.question.trim())
      ? `<span class="muted" style="font-size:.95rem">🎧 ${esc(q.question.trim().match(/^\d+番$/) ? q.question.trim() + ' · ' : '')}Nghe audio rồi chọn đáp án đúng nhất.</span>`
      : renderStem(q.question)}</div>
    <div class="options ${isShort ? 'short' : ''}">${options}</div>
    ${reveal ? explainHTML(q) : ''}
    ${reveal && !compact ? actionsHTML(q) : ''}
  `;

  if (interactive && !reveal && onSelect) {
    card.querySelectorAll('.opt').forEach(b => b.addEventListener('click', () => {
      card.querySelectorAll('.opt').forEach(x => x.classList.remove('selected'));
      b.classList.add('selected');
      onSelect(Number(b.dataset.i));
    }));
  }
  if (reveal && !compact) wireActions(card, q);
  return card;
}

/** Google Drive "preview" links can only be embedded as an iframe; everything else uses <audio>. */
export function audioHTML(url) {
  const m = url.match(/drive\.google\.com\/file\/d\/([^/]+)/);
  if (m) {
    return `<div class="audio-box"><iframe src="https://drive.google.com/file/d/${esc(m[1])}/preview" width="100%" height="64" allow="autoplay" style="max-width:420px;border:0;border-radius:8px" loading="lazy" title="Audio"></iframe>
      <span class="small muted">Audio của cả 問題 (nhiều câu dùng chung một file).</span></div>`;
  }
  return `<div class="audio-box"><audio controls preload="none" src="${esc(url)}"></audio></div>`;
}

function explainHTML(q) {
  const ex = q.ex || {};
  const s = store.settings();
  const parts = [];
  if (q.section === 'choukai' && q.transcript) parts.push(`<h4>Script</h4><p class="ja">${escText(q.transcript)}</p>`);
  if (ex.trans) parts.push(`<h4>${q.section === 'choukai' ? 'Dịch' : 'Dịch câu'}</h4><p>${escText(ex.trans)}</p>`);
  if (ex.note) parts.push(`<h4>Giải thích</h4><p>${escText(ex.note)}</p>`);
  if (!ex.opts && !ex.trans && !ex.note && q.explanation && s.showSourceExplain)
    parts.push(`<h4>Giải thích (nguồn)</h4><p class="src">${escText(q.explanation)}</p>`);
  else if (q.explanation && s.showSourceExplain)
    parts.push(`<details><summary class="small muted">Giải thích gốc từ nguồn</summary><p class="src">${escText(q.explanation)}</p></details>`);
  if (!parts.length && !(ex.opts && ex.opts.length))
    parts.push(`<p class="muted">Chưa có giải thích chi tiết cho câu này. Đáp án đúng: <b>${LETTERS[q.answer]}</b>. Xem phần "Học lại" bên dưới.</p>`);
  return `<div class="explain">${parts.join('')}</div>`;
}

function actionsHTML(q) {
  const flagged = store.isFlagged(q.id);
  const note = store.noteOf(q.id);
  return `
    <div class="q-actions">
      <button type="button" class="btn btn-sm flag-btn ${flagged ? 'on' : ''}" data-act="flag" title="Lưu vào Xem sau (ôn lại theo lịch)">
        ${flagged ? '★ Đã lưu Xem sau' : '☆ Lưu Xem sau'}
      </button>
      <button type="button" class="btn btn-sm" data-act="note">${note ? '📝 Ghi chú' : '＋ Ghi chú'}</button>
      <button type="button" class="btn btn-sm" data-act="related">📚 Học lại (từ vựng · ngữ pháp · kanji)</button>
      ${q.source_url ? `<a class="btn btn-sm btn-ghost muted" href="${esc(q.source_url)}" target="_blank" rel="noopener">nguồn: ${esc(q.source)}</a>` : ''}
    </div>
    <div class="note-box" ${note ? '' : 'hidden'}>
      <textarea class="input" rows="2" placeholder="Ghi chú của bạn cho câu này…">${esc(note)}</textarea>
    </div>
    <div class="related" hidden></div>`;
}

function wireActions(card, q) {
  const flagBtn = card.querySelector('[data-act="flag"]');
  flagBtn?.addEventListener('click', () => {
    const on = store.toggleFlag(q.id);
    flagBtn.classList.toggle('on', on);
    flagBtn.textContent = on ? '★ Đã lưu Xem sau' : '☆ Lưu Xem sau';
    toast(on ? 'Đã lưu vào Xem sau · ôn lại ngày mai' : 'Đã bỏ khỏi Xem sau');
    document.dispatchEvent(new CustomEvent('srs-changed'));
  });
  const noteBox = card.querySelector('.note-box');
  card.querySelector('[data-act="note"]')?.addEventListener('click', () => {
    noteBox.hidden = !noteBox.hidden;
    if (!noteBox.hidden) noteBox.querySelector('textarea').focus();
  });
  noteBox?.querySelector('textarea').addEventListener('input', debounce((e) => store.setNote(q.id, e.target.value), 300));

  const rel = card.querySelector('.related');
  card.querySelector('[data-act="related"]')?.addEventListener('click', async () => {
    rel.hidden = !rel.hidden;
    if (!rel.hidden && !rel.dataset.loaded) {
      rel.innerHTML = '<p class="muted small">Đang tìm…</p>';
      rel.innerHTML = relatedHTML(await relatedRefs(q));
      rel.dataset.loaded = '1';
    }
  });
}

export function relatedHTML({ grammar, vocab, kanji }) {
  const out = [];
  if (grammar.length) out.push(`<details open><summary>Ngữ pháp liên quan (${grammar.length})</summary>${grammar.map(g => `
    <div class="ref-item"><span class="ref-ja">${esc(g.pattern)}</span> — ${esc(g.meaning_vi || g.meaning_en || '')}
      ${g.structure ? `<div class="small muted">Cấu trúc: ${esc(g.structure)}</div>` : ''}
      ${g.examples?.[0] ? `<div class="small"><span class="ja">${esc(g.examples[0].ja)}</span>${(g.examples[0].vi || g.examples[0].en) ? ` — ${esc(g.examples[0].vi || g.examples[0].en)}` : ''}</div>` : ''}
    </div>`).join('')}</details>`);
  if (vocab.length) out.push(`<details open><summary>Từ vựng (${vocab.length})</summary>${vocab.map(v => `
    <div class="ref-item"><span class="ref-ja">${esc(v.word)}</span> <span class="muted ja">${esc(v.reading || '')}</span> — ${esc(v.meaning_vi || v.meaning_en || '')}</div>`).join('')}</details>`);
  if (kanji.length) out.push(`<details><summary>Kanji trong câu (${kanji.length})</summary>${kanji.map(k => `
    <div class="ref-item"><span class="ref-ja" style="font-size:1.4rem">${esc(k.kanji)}</span>
      ${k.hanviet ? `<b>${esc(k.hanviet)}</b>` : ''} — ${esc(k.meaning_vi || k.meaning_en || '')}
      <div class="small muted ja">音 ${esc((k.on || []).join('・'))}　訓 ${esc((k.kun || []).join('・'))}</div>
      ${k.examples?.length ? `<div class="small ja">${k.examples.slice(0, 3).map(e => `${esc(e.word)}（${esc(e.reading || '')}）${e.meaning_vi ? ' ' + esc(e.meaning_vi) : ''}`).join('　')}</div>` : ''}
    </div>`).join('')}</details>`);
  if (!out.length) return '<p class="muted small">Không tìm thấy mục tra cứu liên quan.</p>';
  return out.join('');
}

/** Render an item (passage + its questions) for a test page. answers: {qid: idx} */
export function renderItem(item, { startIndex = 1, answers = {}, reveal = false, interactive = true, onSelect = null, compact = false } = {}) {
  const wrap = document.createElement('div');
  wrap.className = 'q-layout' + (item.pid ? ' with-passage' : '');
  if (item.pid) wrap.appendChild(renderPassage(item.pid, { reveal }));
  const col = document.createElement('div');
  item.qids.forEach((qid, i) => {
    const q = getQ(qid);
    if (!q) return;
    col.appendChild(renderQuestion(q, {
      index: `${startIndex + i}.`, selected: answers[qid] ?? null, reveal, interactive, compact,
      onSelect: onSelect ? (idx) => onSelect(qid, idx) : null,
    }));
  });
  wrap.appendChild(col);
  return wrap;
}
