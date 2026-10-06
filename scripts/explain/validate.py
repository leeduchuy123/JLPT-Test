# -*- coding: utf-8 -*-
"""Validate crawl/explain/out/*.json against the batches. python -I scripts/explain/validate.py"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BATCH = os.path.join(ROOT, 'crawl', 'explain', 'batches')
OUT = os.path.join(ROOT, 'crawl', 'explain', 'out')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    problems = 0
    total = 0
    for bpath in sorted(glob.glob(os.path.join(BATCH, '*.json'))):
        name = os.path.basename(bpath)
        opath = os.path.join(OUT, name)
        if not os.path.exists(opath):
            print(f'MISSING  {name}')
            continue
        try:
            out = json.load(open(opath, encoding='utf-8'))
        except Exception as e:
            print(f'BADJSON  {name}: {e}')
            problems += 1
            continue
        batch = json.load(open(bpath, encoding='utf-8'))
        if 'passages' in name:
            missing = [k for k in batch if not (isinstance(out.get(k), str) and len(out[k]) > 20)]
            total += len(batch) - len(missing)
            if missing:
                print(f'PARTIAL  {name}: {len(missing)}/{len(batch)} passages missing/short')
                problems += len(missing)
            continue
        bad = []
        for q in batch:
            e = out.get(q['id'])
            if not isinstance(e, dict):
                bad.append((q['id'], 'missing')); continue
            opts = e.get('opts')
            if opts is not None and (not isinstance(opts, list) or len(opts) != len(q['options'])):
                bad.append((q['id'], f'opts len {len(opts) if isinstance(opts, list) else "?"} != {len(q["options"])}')); continue
            if not (e.get('trans') or e.get('note') or opts):
                bad.append((q['id'], 'empty')); continue
            total += 1
        if bad:
            problems += len(bad)
            print(f'PARTIAL  {name}: {len(bad)}/{len(batch)} bad -> ' + '; '.join(f'{i}:{r}' for i, r in bad[:5]))
    print(f'\nOK explanations: {total}, problems: {problems}')


if __name__ == '__main__':
    main()
