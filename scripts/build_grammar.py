# -*- coding: utf-8 -*-
"""
Build data/grammar.json (mẫu ngữ pháp + ví dụ lấy từ câu hỏi) từ kết quả phân loại của sub agent ngữ pháp.

  python -I scripts/build_grammar.py

Đầu vào : crawl/grammar/out/catalog.json  (danh mục mẫu: pattern, formula, meaning_vi, explain_vi, group, examples_qids…)
          crawl/grammar/out/map.json      (qid -> [pattern_id, …], mẫu chính đứng đầu)
          data/bank/bunpo.json            (câu hỏi + đoạn văn)
          data/exams.json                 (đề thi chính thức: official=true → mẫu nào đã xuất hiện trong đề thật)
Đầu ra  : data/grammar.json
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'crawl', 'grammar', 'out')
BANK = os.path.join(ROOT, 'data', 'bank', 'bunpo.json')
DEST = os.path.join(ROOT, 'data', 'grammar.json')
EXAMS = os.path.join(ROOT, 'data', 'exams.json')
MAX_EX = 6
SKIP_GROUP = 'Văn bản/Ngữ cảnh'


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def sentence(q, passages):
    """Câu hoàn chỉnh (đã điền đáp án đúng) của một câu hỏi, hoặc None."""
    ans = q['options'][q['answer']]
    t = q['type']
    if t == 'grammar_form':
        s = re.sub(r'[（(][\s　]*[）)]', ans, q['question'], count=1)
        return s.replace('\n', ' ').strip() if s != q['question'] else None
    if t == 'sentence_order':
        m = re.search(r'Câu đúng:\s*(.+?)(?:\s*★|$)', (q.get('ex') or {}).get('note') or '')
        return m.group(1).strip() if m else None
    if t == 'text_grammar':
        p = passages.get(q.get('passage_id') or '')
        m = re.search(r'【(\d+)】', q['question'])
        if not p or not m:
            return None
        mark = '【%s】' % m.group(1)
        for sent in re.split(r'(?<=[。！？\n])', p['text']):
            if mark in sent:
                return sent.replace(mark, ans).strip()
    return None


def main():
    catalog = load(os.path.join(OUT_DIR, 'catalog.json'))
    qmap = load(os.path.join(OUT_DIR, 'map.json'))
    bank = load(BANK)
    qs = {q['id']: q for q in bank['questions']}
    passages = bank['passages']

    # đề thi chính thức: qid -> id đề; nhãn "2019/12" cho từng đề
    off_exams = [e for e in load(EXAMS) if e.get('official')]
    q2exam = {qid: e['id'] for e in off_exams for qid in e['parts'].get('bunpo', [])}
    exam_label = {}
    for e in off_exams:
        m = re.search(r'(\d{4})年(\d+)月', e['name'])
        exam_label[e['id']] = '%s/%02d' % (m.group(1), int(m.group(2))) if m else e['name']

    by_id = {}
    for c in catalog:
        if c['id'] in by_id:
            sys.exit('id mẫu trùng: ' + c['id'])
        by_id[c['id']] = c

    qids = {pid: [] for pid in by_id}
    for qid, pids in qmap.items():
        if qid not in qs:
            continue
        for i, pid in enumerate(pids):
            if pid in qids:
                qids[pid].append(qid)

    def example(qid):
        q = qs.get(qid)
        if not q:
            return None
        ja = sentence(q, passages)
        if not ja or len(ja) < 6:
            return None
        vi = (q.get('ex') or {}).get('trans')
        e = {'ja': ja, 'vi': vi, 'qid': qid}
        if qid in q2exam:
            e['src'] = exam_label[q2exam[qid]]
        return e

    points = []
    for pid, c in by_id.items():
        ids = qids[pid]
        if not ids or c.get('group') == SKIP_GROUP:  # 'bunmyaku' = chọn từ theo mạch văn, không phải mẫu để học thuộc
            continue
        exs, seen = [], set()
        off_ids = [x for x in ids if x in q2exam]
        # ví dụ lấy từ đề thi chính thức trước, rồi tới ví dụ agent chọn, rồi các câu còn lại
        for qid in off_ids + list(c.get('examples_qids') or []) + ids:
            e = example(qid)
            if e and e['ja'] not in seen:
                seen.add(e['ja'])
                exs.append(e)
            if len(exs) >= MAX_EX:
                break
        off_exam_ids = sorted({q2exam[x] for x in off_ids}, key=lambda i: exam_label[i])
        points.append({
            'id': pid,
            'pattern': c['pattern'],
            'reading': c.get('reading') or '',
            'formula': c.get('formula') or '',
            'meaning_vi': c.get('meaning_vi') or '',
            'explain_vi': c.get('explain_vi') or '',
            'group': c.get('group') or 'Khác',
            'confusable': [x for x in (c.get('confusable') or []) if x in by_id and x != pid],
            'n': len(ids),
            'ex': exs,
            'qids': ids,
            'off': {'n': len(off_ids), 'exams': [exam_label[i] for i in off_exam_ids]},
        })
    points.sort(key=lambda p: (-len(p['off']['exams']), -p['n'], p['id']))
    groups = sorted({p['group'] for p in points})
    out = {'built': __import__('datetime').date.today().isoformat(), 'questions': len(qmap), 'groups': groups,
           'official_exams': sorted(exam_label.values()), 'points': points}
    with open(DEST, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    no_ex = [p['id'] for p in points if not p['ex']]
    print('mẫu trong đề chính thức: %d (%d đề)' % (sum(1 for p in points if p['off']['n']), len(exam_label)))
    print('mẫu: %d · câu gán: %d · nhóm: %d · mẫu thiếu ví dụ: %d · %.0f KB' % (
        len(points), len(qmap), len(groups), len(no_ex), os.path.getsize(DEST) / 1024))


if __name__ == '__main__':
    main()
