# -*- coding: utf-8 -*-
"""
Split the built bank into small batches for writing teacher explanations.

  python -I scripts/explain/make_batches.py [--size 80]

Writes crawl/explain/batches/<section>-<NNN>.json, each a list of compact question dicts
(id, type, question, options, answer, source_explanation, passage (for text_grammar/dokkai), transcript (choukai)).
Also writes crawl/explain/batches/passages-<NNN>.json with passages that have no Vietnamese translation yet.
Skips questions that already have an entry in crawl/explain/out/*.json.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BANK = os.path.join(ROOT, 'data', 'bank')
OUT_DIR = os.path.join(ROOT, 'crawl', 'explain', 'out')
BATCH_DIR = os.path.join(ROOT, 'crawl', 'explain', 'batches')
PRIORITY = ['moji', 'bunpo', 'dokkai', 'choukai']


def main():
    size = 80
    if '--size' in sys.argv:
        size = int(sys.argv[sys.argv.index('--size') + 1])
    done = set()
    done_passages = set()
    for p in glob.glob(os.path.join(OUT_DIR, '*.json')):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        if 'passages' in os.path.basename(p):
            done_passages.update(k for k, v in d.items() if v)
        else:
            done.update(d.keys())
    os.makedirs(BATCH_DIR, exist_ok=True)
    prefix = ''
    if '--prefix' in sys.argv:
        prefix = sys.argv[sys.argv.index('--prefix') + 1]
    # ids already assigned to an existing batch (pending or done) are not re-batched
    for p in glob.glob(os.path.join(BATCH_DIR, '*.json')):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        if os.path.basename(p).startswith(prefix) and prefix:
            os.remove(p)  # re-generating this same prefix
            continue
        if isinstance(d, list):
            done.update(x['id'] for x in d)
        elif isinstance(d, dict):
            done_passages.update(d.keys())

    total = 0
    passages_todo = {}
    for section in PRIORITY:
        path = os.path.join(BANK, f'{section}.json')
        if not os.path.exists(path):
            continue
        bank = json.load(open(path, encoding='utf-8'))
        passages = bank['passages']
        # every passage still lacking a translation is batched, even if all its questions are explained
        for pid, pv in passages.items():
            if not pv.get('vi') and pid not in done_passages:
                passages_todo[pid] = pv['text']
        items = []
        for q in bank['questions']:
            if q['id'] in done:
                continue
            ex = q.get('ex') or {}
            # already explained in the bank (e.g. carried over from a merged duplicate)
            if ex.get('opts') or (q['section'] in ('dokkai', 'choukai') and ex.get('trans')):
                continue
            item = {'id': q['id'], 'type': q['type'], 'question': q['question'], 'options': q['options'], 'answer': q['answer'], 'tier': q.get('tier', 'A'), '_tier': q.get('tier', 'A')}
            if q.get('explanation'):
                item['source_explanation'] = q['explanation'][:600]
            if q.get('passage_id') and q['passage_id'] in passages:
                item['passage'] = passages[q['passage_id']]['text'][:1800]
                if not passages[q['passage_id']].get('vi') and q['passage_id'] not in done_passages:
                    passages_todo[q['passage_id']] = passages[q['passage_id']]['text']
            if q.get('transcript'):
                item['transcript'] = q['transcript'][:1500]
            items.append(item)
        # tier A first (exam-derived), tier B (auto-generated drills) in separate batches; passages kept together
        tiers = {'A': [x for x in items if x.pop('tier', 'A') != 'B'], 'B': [x for x in items if x.get('_tier') == 'B']}
        for tier, lst in tiers.items():
            lst.sort(key=lambda x: (x.get('passage') is None, x['id'] if x.get('passage') is None else x['id'].rsplit('-q', 1)[0]))
            for i in range(0, len(lst), size):
                n = i // size + 1
                name = f'{prefix}{section}-{n:03d}.json' if tier == 'A' else f'{prefix}{section}-B-{n:03d}.json'
                with open(os.path.join(BATCH_DIR, name), 'w', encoding='utf-8') as f:
                    json.dump([{k: v for k, v in x.items() if k != '_tier'} for x in lst[i:i + size]], f, ensure_ascii=False, indent=0)
            total += len(lst)
            print(f'{section} tier {tier}: {len(lst)} questions -> {(len(lst) + size - 1) // size} batches')

    plist = list(passages_todo.items())
    psize = 20
    for i in range(0, len(plist), psize):
        n = i // psize + 1
        with open(os.path.join(BATCH_DIR, f'{prefix}passages-{n:03d}.json'), 'w', encoding='utf-8') as f:
            json.dump(dict(plist[i:i + psize]), f, ensure_ascii=False, indent=0)
    print(f'passages: {len(plist)} -> {(len(plist) + psize - 1) // psize} batches')
    print(f'total questions to explain: {total}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
