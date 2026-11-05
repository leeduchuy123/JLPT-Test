"""Gộp khung khoá học (scripts/study/courses.json) + các bài đã viết → data/study/index.json cho app.

python -I scripts/study/build_index.py
Bài chưa có file vẫn nằm trong lộ trình (ready: false) để app hiện "đang soạn".
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import check_file  # noqa: E402


def main():
    courses = json.loads((ROOT / 'scripts' / 'study' / 'courses.json').read_text(encoding='utf-8'))
    out = {'tracks': []}
    total = ready = 0
    for t in courses['tracks']:
        units = []
        for u in t['units']:
            total += 1
            f = ROOT / 'data' / 'study' / t['id'] / f"{u['id']}.json"
            unit = {k: u[k] for k in ('id', 'label', 'part', 'title', 'title_vi') if k in u}
            unit['items'] = list(u.get('items') or [])
            unit['ready'] = False
            if f.exists():
                errs, _ = check_file(f)
                if errs:
                    print(f'! {f.name}: {len(errs)} lỗi, bỏ qua (chạy validate.py để xem)')
                else:
                    d = json.loads(f.read_text(encoding='utf-8'))
                    unit['ready'] = True
                    ready += 1
                    if t['id'] == 'bunpo':
                        unit['items'] = [p['pattern'] for p in d['points']]
                        unit['n'] = len(d['points'])
                    elif t['id'] == 'goi':
                        words = [w for s in d['sections'] for w in s.get('words', [])]
                        unit['items'] = [w['w'] for w in words if w.get('key')] or [w['w'] for w in words][:30]
                        unit['n'] = len(words)
                    else:
                        unit['items'] = [s['title'] for s in d.get('strategy', [])][:6]
                        unit['n'] = len(d.get('passages', {}))
                    unit['q'] = {k: len(d.get(k) or []) for k in ('quiz', 'practice', 'test')}
            units.append(unit)
        out['tracks'].append({'id': t['id'], 'title': t['title'], 'book': t['book'], 'units': units})
    dst = ROOT / 'data' / 'study' / 'index.json'
    dst.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'index.json: {ready}/{total} bài sẵn sàng')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
