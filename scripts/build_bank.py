# -*- coding: utf-8 -*-
"""
Build the deployable question bank from crawl/raw/*.json.

  crawl/raw/<source>.json      -> normalized questions (see scripts/crawl/SCHEMA.md)
  crawl/explain/*.json         -> { qid: {opts:[..], trans:"..", note:".."} }  (teacher explanations, Vietnamese)
  crawl/explain/passages*.json -> { passage_id: "bản dịch tiếng Việt" }
  crawl/raw/ref_*.json         -> reference lists

Outputs:
  data/bank/{moji,bunpo,dokkai,choukai}.json  { passages: {pid: {text, vi}}, questions: [...] }
  data/exams.json                              [{id, name, source, parts: {section: [qid...]}}]
  data/ref/{vocab,kanji,grammar}.json
  data/manifest.json

Run from repo root:  python -I scripts/build_bank.py
"""
import glob
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'crawl', 'raw')
EXPLAIN = os.path.join(ROOT, 'crawl', 'explain')
OUT = os.path.join(ROOT, 'data')

# sources that are not N3 or otherwise excluded from the bank
EXCLUDE_SOURCES = {'ubiq'}
# tier A = derived from mock exams / curated by schools; tier B = auto-generated or level-uncertain drills
TIER_B = {'japanesequizzes', 'gyanmirai'}
# sources whose exams are reproductions of real JLPT sessions
OFFICIAL_SOURCES = {'jlptpt', 'nihonez'}
# sources whose ruby flattening left spaces between Japanese characters
FIX_SPACING = {'nihongopro'}
CJK = '぀-ヿ㐀-鿿'
SPACE_RE = re.compile('(?<=[' + CJK + '])[ ]+(?=[' + CJK + '])')


def fix_spacing(s):
    if not s:
        return s
    prev = None
    while prev != s:
        prev = s
        s = SPACE_RE.sub('', s)
    return s
SECTIONS = ['moji', 'bunpo', 'dokkai', 'choukai']
TYPE_SECTION = {
    'kanji_reading': 'moji', 'orthography': 'moji', 'context': 'moji', 'paraphrase': 'moji', 'usage': 'moji',
    'vocab_meaning': 'moji', 'kanji_meaning': 'moji',
    'grammar_form': 'bunpo', 'sentence_order': 'bunpo', 'text_grammar': 'bunpo', 'grammar_misc': 'bunpo',
    'reading_short': 'dokkai', 'reading_mid': 'dokkai', 'reading_long': 'dokkai', 'info_retrieval': 'dokkai',
    'listening': 'choukai',
}
TYPE_MONDAI = {'kanji_reading': 1, 'orthography': 2, 'context': 3, 'paraphrase': 4, 'usage': 5,
               'grammar_form': 1, 'sentence_order': 2, 'text_grammar': 3,
               'reading_short': 4, 'reading_mid': 5, 'reading_long': 6, 'info_retrieval': 7}

PUNCT_RE = re.compile(r'[\s　＿_「」『』（）()【】。、．，…・?？!！:：;；\-ー〜～~*＊★☆]+')


def norm(s):
    s = unicodedata.normalize('NFKC', s or '')
    return PUNCT_RE.sub('', s).lower()


def media_key(q):
    # listening / picture questions share generic stems ("1番", "Question 1") and numeric options:
    # the audio/image URL is what makes them distinct
    if q.get('type') == 'listening' or q.get('image'):
        return '|' + (q.get('audio') or '') + '|' + (q.get('image') or '') + '|' + (q.get('transcript') or '')[:80]
    return ''


def dedupe_key(q):
    opts = sorted(norm(o) for o in q['options'])
    return norm(q['question'])[:160] + '|' + '|'.join(opts) + media_key(q)


def loose_key(q):
    """Same stem + same correct option, ignoring distractors: catches re-typed copies."""
    return norm(q['question']) + '|' + norm(q['options'][q['answer']]) + media_key(q)


def slug(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return s or hashlib.sha1(s.encode()).hexdigest()[:8]


def clean_text(s):
    if s is None:
        return None
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'[ \t]+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def load_raw():
    questions = []
    # tier A sources first so that, when a duplicate exists, the exam-derived copy is the one kept
    paths = sorted(glob.glob(os.path.join(RAW, '*.json')),
                   key=lambda p: (os.path.basename(p)[:-5] in TIER_B, os.path.basename(p)[:-5] not in OFFICIAL_SOURCES, os.path.basename(p)))
    for path in paths:
        name = os.path.basename(path)[:-5]
        if name.startswith('ref_'):
            continue
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:  # noqa
            print(f'!! skip {name}: {e}')
            continue
        if not isinstance(data, list):
            continue
        n = 0
        for q in data:
            if not isinstance(q, dict) or q.get('source') in EXCLUDE_SOURCES or name in EXCLUDE_SOURCES:
                continue
            if q.get('level') and str(q['level']).upper() not in ('N3', '3'):
                continue
            if q.get('source') == 'jlptpt' and q.get('type') == 'listening':
                continue  # site's own AI-voiced samples, not official
            questions.append(q)
            n += 1
        print(f'   {name}: {n}')
    return questions


def validate(q):
    sp = q.get('source') in FIX_SPACING
    fx = fix_spacing if sp else (lambda x: x)
    opts = [clean_text(fx(o)) for o in (q.get('options') or [])]
    if not (2 <= len(opts) <= 4) or any(not o for o in opts):
        return None
    # "all of the above" style options do not exist in the JLPT format
    if any(re.match(r'^(すべて|全て|いずれも|どれも|上記)(が|は)?(正しい|可能|関連|当てはまる|間違い|すべて)', o) for o in opts):
        return None
    if not isinstance(q.get('answer'), int) or not (0 <= q['answer'] < len(opts)):
        return None
    stem = clean_text(fx(q.get('question') or ''))
    t = q.get('type') or 'grammar_misc'
    section = q.get('section') or TYPE_SECTION.get(t)
    if section not in SECTIONS:
        return None
    if t not in TYPE_SECTION:
        t = {'moji': 'vocab_meaning', 'bunpo': 'grammar_misc', 'dokkai': 'reading_short', 'choukai': 'listening'}[section]
    if TYPE_SECTION[t] != section:
        # trust the type over the section when they disagree, unless type is generic
        section = TYPE_SECTION[t]
    if not stem and section != 'choukai':
        return None
    # passage questions need a passage
    needs_passage = t in ('text_grammar', 'reading_short', 'reading_mid', 'reading_long', 'info_retrieval')
    if needs_passage and not (q.get('passage') or '').strip():
        return None
    if t == 'listening' and not q.get('audio'):
        return None
    out = {
        'id': q['id'], 'source': q['source'], 'source_url': q.get('source_url'), 'exam': q.get('exam'),
        'section': section, 'mondai': q.get('mondai') or TYPE_MONDAI.get(t), 'type': t,
        'tier': 'B' if q['source'] in TIER_B else 'A',
        'passage_id': q.get('passage_id') if needs_passage or q.get('passage') else None,
        'question': stem or '（音声を聞いて答えてください）', 'options': opts, 'answer': q['answer'],
        'explanation': clean_text(q.get('explanation')) or None,
        'audio': q.get('audio') or None, 'image': q.get('image') or None,
        'transcript': clean_text(q.get('transcript')) or None,
    }
    if q.get('passage') and not out['passage_id']:
        out['passage_id'] = q['source'] + ':p:' + hashlib.sha1(q['passage'].encode('utf-8')).hexdigest()[:10]
    return out, clean_text(fx(q.get('passage')))


def load_explanations():
    ex, pvi = {}, {}
    if not os.path.isdir(EXPLAIN):
        return ex, pvi
    for path in sorted(glob.glob(os.path.join(EXPLAIN, '*.json')) + glob.glob(os.path.join(EXPLAIN, 'out', '*.json'))):
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:  # noqa
            print(f'!! bad explain file {path}: {e}')
            continue
        if not isinstance(data, dict):
            continue
        if 'passages' in os.path.basename(path):
            for k, v in data.items():
                if isinstance(v, str) and v.strip():
                    pvi[k] = v.strip()
                elif isinstance(v, dict) and v.get('vi'):
                    pvi[k] = v['vi'].strip()
        else:
            for k, v in data.items():
                if isinstance(v, dict):
                    ex[k] = v
    return ex, pvi


def main():
    print('Loading raw…')
    raw = load_raw()
    print(f'   raw total: {len(raw)}')
    explain, passage_vi = load_explanations()
    print(f'   explanations: {len(explain)} questions, {len(passage_vi)} passages')

    seen, seen_loose = {}, {}
    passages = {}       # pid -> {text, vi}
    passage_by_hash = {}  # normalized passage text -> pid (dedupe passages across sources)
    pid_map = {}
    out = []
    dropped = Counter()
    dup_of = {}
    by_id_kept = {}

    for q in raw:
        v = validate(q)
        if not v:
            dropped['invalid'] += 1
            continue
        nq, ptext = v
        # passage dedupe
        if nq['passage_id'] and ptext:
            h = norm(ptext)[:200]
            if h in passage_by_hash:
                pid = passage_by_hash[h]
            else:
                pid = nq['passage_id']
                passage_by_hash[h] = pid
                passages[pid] = {'text': ptext, 'vi': passage_vi.get(pid)}
            pid_map[nq['passage_id']] = pid
            nq['passage_id'] = pid
        k = dedupe_key(nq)
        lk = loose_key(nq)
        if k in seen or lk in seen_loose:
            dropped['duplicate'] += 1
            keep = seen.get(k) or seen_loose.get(lk)
            dup_of[nq['id']] = keep['id']
            e = explain.get(nq['id'])
            if e and not keep.get('ex') and keep['id'] not in explain:
                same_order = [norm(o) for o in keep['options']] == [norm(o) for o in nq['options']]
                fields = ('opts', 'trans', 'note') if same_order else ('trans', 'note')
                keep['ex'] = {f: e[f] for f in fields if e.get(f)}
                if '(?)' in (e.get('note') or '') and not re.search(r'\(\?\)\s*Đề gắn nhãn', e.get('note') or ''):
                    keep['suspect'] = True
            # merge: keep explanation / audio from the duplicate if the kept one lacks it
            if not keep.get('explanation') and nq.get('explanation'):
                keep['explanation'] = nq['explanation']
            if not keep.get('exam') and nq.get('exam'):
                keep['exam'] = nq['exam']
            continue
        seen[k] = nq
        seen_loose[lk] = nq
        by_id_kept[nq['id']] = nq
        if nq['id'] in explain:
            e = explain[nq['id']]
            nq['ex'] = {k2: e[k2] for k2 in ('opts', 'trans', 'note') if e.get(k2)}
            note = e.get('note') or ''
            # teacher flagged: wrong/ambiguous key or a typo that breaks the stem (type-mislabel flags are harmless)
            if '(?)' in note and not re.search(r'\(\?\)\s*Đề gắn nhãn', note):
                nq['suspect'] = True
        out.append(nq)

    # passage translation via alias ids
    for alias, pid in pid_map.items():
        if alias in passage_vi and not passages[pid].get('vi'):
            passages[pid]['vi'] = passage_vi[alias]

    # ---- write bank per section
    os.makedirs(os.path.join(OUT, 'bank'), exist_ok=True)
    os.makedirs(os.path.join(OUT, 'ref'), exist_ok=True)
    by_sec = defaultdict(list)
    for q in out:
        by_sec[q['section']].append(q)
    used_passages = set(q['passage_id'] for q in out if q['passage_id'])
    for s in SECTIONS:
        qs = by_sec.get(s, [])
        pids = set(q['passage_id'] for q in qs if q['passage_id'])
        data = {'passages': {pid: passages[pid] for pid in pids if pid in passages}, 'questions': qs}
        with open(os.path.join(OUT, 'bank', f'{s}.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        print(f'   bank/{s}.json: {len(qs)} q, {len(data["passages"])} passages')

    # ---- exams
    raw_exam_size = Counter(q.get('exam') for q in raw if q.get('exam'))
    exams = defaultdict(lambda: defaultdict(list))
    exam_src = {}
    for q in out:
        if q.get('exam'):
            exams[q['exam']][q['section']].append(q)
            exam_src[q['exam']] = q['source']
    exam_list = []
    for name, parts in sorted(exams.items(), key=lambda kv: natural(kv[0]), reverse=False):
        total = sum(len(v) for v in parts.values())
        # hide exams that are mostly duplicates of another (more complete) exam
        if total < 10 or total < 0.6 * raw_exam_size.get(name, total):
            continue
        p = {}
        for s in SECTIONS:
            qs = parts.get(s, [])
            qs.sort(key=lambda q: (q.get('mondai') or 99, natural(q['id'])))
            if qs:
                p[s] = [q['id'] for q in qs]
        official = bool(re.search(r'(19|20)\d{2}\s*年', name)) or exam_src[name] in OFFICIAL_SOURCES
        exam_list.append({'id': slug(name), 'name': name, 'source': exam_src[name], 'parts': p, 'total': total, 'official': official})
    with open(os.path.join(OUT, 'exams.json'), 'w', encoding='utf-8') as f:
        json.dump(exam_list, f, ensure_ascii=False, separators=(',', ':'))
    print(f'   exams.json: {len(exam_list)} exams')

    # ---- references
    ref_counts = {}
    for name in ('vocab', 'kanji', 'grammar'):
        src = os.path.join(RAW, f'ref_{name}.json')
        items = []
        if os.path.exists(src):
            with open(src, encoding='utf-8') as f:
                items = json.load(f)
        with open(os.path.join(OUT, 'ref', f'{name}.json'), 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, separators=(',', ':'))
        ref_counts[name] = len(items)
    print(f'   refs: {ref_counts}')

    # ---- manifest
    types = Counter(q['type'] for q in out)
    sources = Counter(q['source'] for q in out)
    explained = sum(1 for q in out if q.get('ex'))
    manifest = {
        'built': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'total': len(out),
        'sections': {s: len(by_sec.get(s, [])) for s in SECTIONS},
        'types': dict(types), 'sources': dict(sources), 'exams': len(exam_list),
        'passages': len(used_passages), 'passages_translated': sum(1 for pid in used_passages if passages.get(pid, {}).get('vi')),
        'explained': explained, 'suspect': sum(1 for q in out if q.get('suspect')), 'refs': ref_counts,
        'dropped': dict(dropped),
        'notes': 'Câu hỏi được gom từ nhiều trang luyện thi miễn phí, đã lọc trùng. Dùng cho mục đích học cá nhân.',
    }
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, 'crawl', 'dedupe_map.json'), 'w', encoding='utf-8') as f:
        json.dump(dup_of, f, ensure_ascii=False, indent=0)
    with open(os.path.join(OUT, 'aliases.json'), 'w', encoding='utf-8') as f:
        json.dump(dup_of, f, ensure_ascii=False, separators=(',', ':'))

    print('\nSummary')
    print(f'   kept {len(out)}  dropped {dict(dropped)}')
    print(f'   sections {manifest["sections"]}')
    print(f'   types {dict(types)}')
    print(f'   sources {dict(sources)}')
    print(f'   explained {explained}/{len(out)}, passages translated {manifest["passages_translated"]}/{len(used_passages)}')


def natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s or '')]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
