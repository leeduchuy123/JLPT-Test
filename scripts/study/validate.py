"""Kiểm tra file bài học N2 (data/study/<track>/<id>.json) theo scripts/study/GUIDE.md.

python -I scripts/study/validate.py data/study/bunpo/b01.json [...]   # hoặc không tham số = mọi file
In ERROR (phải sửa) và WARN (nên xem). Mã thoát 1 nếu có ERROR.
"""
import json, re, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KINDS = {
    'bunpo': {'form', 'order', 'usage', 'passage'},
    'goi': {'read', 'write', 'formation', 'context', 'paraphrase', 'usage', 'form', 'order'},
    'dokkai': {'passage'},
}
SIZES = {  # bộ: (tối thiểu, track)
    'bunpo': {'quiz': 4, 'practice': 8, 'test': 5},
    'goi': {'quiz': 6, 'practice': 10, 'test': 8},
    'dokkai': {'quiz': 2, 'practice': 4, 'test': 3},
}
RUBY = re.compile(r'\{([^{}|]+)\|([^{}|]+)\}')


def check_text(s, where, errs):
    if not isinstance(s, str):
        errs.append(f'{where}: không phải chuỗi'); return
    rest = RUBY.sub('', s)
    if any(c in rest for c in '{}|'):
        errs.append(f'{where}: furigana sai cú pháp {{漢字|かな}}: {s[:60]}')
    if re.search(r'<[a-zA-Z/]', s):
        errs.append(f'{where}: có thẻ HTML')
    if rest.count('[[') != rest.count(']]'):
        errs.append(f'{where}: [[u:…]] không khép')


def walk_texts(obj, where, errs):
    if isinstance(obj, str): check_text(obj, where, errs)
    elif isinstance(obj, list):
        for i, x in enumerate(obj): walk_texts(x, f'{where}[{i}]', errs)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('id', 'kind', 'ref', 'pass', 'track'): continue
            walk_texts(v, f'{where}.{k}', errs)


def check_q(q, where, track, refs, passages, errs, warns):
    for k in ('id', 'kind', 'q', 'options', 'answer', 'why'):
        if k not in q or q[k] in (None, ''): errs.append(f'{where}: thiếu {k}')
    kind = q.get('kind')
    if kind and kind not in KINDS[track]: errs.append(f'{where}: kind "{kind}" không hợp với {track}')
    opts = q.get('options') or []
    if len(opts) != 4: errs.append(f'{where}: cần đúng 4 phương án (có {len(opts)})')
    if len(set(map(str, opts))) != len(opts): errs.append(f'{where}: phương án trùng nhau')
    if any(not str(o).strip() for o in opts): errs.append(f'{where}: phương án rỗng')
    a = q.get('answer')
    if not isinstance(a, int) or not 0 <= a < max(1, len(opts)): errs.append(f'{where}: answer không hợp lệ')
    if kind == 'order':
        o = q.get('order')
        if not isinstance(o, list) or sorted(o) != [0, 1, 2, 3]: errs.append(f'{where}: order phải là hoán vị của 0..3')
        else:
            slots = re.findall(r'＿＿＿|★', q.get('q', ''))
            if len(slots) != 4 or slots.count('★') != 1:
                errs.append(f'{where}: câu 並べ替え cần đúng 4 ô (3 ＿＿＿ + 1 ★), có {slots}')
            elif a != o[slots.index('★')]:
                errs.append(f'{where}: answer ({a}) ≠ mảnh ở vị trí ★ ({o[slots.index("★")]})')
    if q.get('ref') and q['ref'] not in refs: warns.append(f'{where}: ref "{q["ref"]}" không tồn tại')
    if q.get('pass') and q['pass'] not in passages: errs.append(f'{where}: pass "{q["pass"]}" không có trong passages')
    if kind == 'passage' and not q.get('pass'): errs.append(f'{where}: câu passage thiếu pass')
    if track != 'dokkai' and not q.get('vi') and kind not in ('usage',): warns.append(f'{where}: thiếu vi (dịch câu)')


def check_file(path):
    errs, warns = [], []
    try:
        d = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as e:
        return [f'JSON lỗi: {e}'], []
    stem = Path(path).stem
    track = d.get('track') or Path(path).parent.name
    if d.get('id') != stem: errs.append(f'id "{d.get("id")}" ≠ tên file "{stem}"')
    if track not in KINDS: return errs + [f'track lạ: {track}'], warns
    if not d.get('intro'): errs.append('thiếu intro')
    refs = set()
    passages = d.get('passages') or {}
    for pid, p in passages.items():
        if not p.get('ja'): errs.append(f'passages.{pid}: thiếu ja')
        if not p.get('vi'): errs.append(f'passages.{pid}: thiếu vi (bản dịch)')

    if track == 'bunpo':
        pts = d.get('points') or []
        if not pts: errs.append('thiếu points')
        for i, p in enumerate(pts):
            w = f'points[{i}]'
            for k in ('id', 'pattern', 'meaning', 'structure', 'explain', 'examples'):
                if not p.get(k): errs.append(f'{w}: thiếu {k}')
            refs.add(p.get('id'))
            ex = p.get('examples') or []
            if len(ex) < 3: errs.append(f'{w} {p.get("pattern")}: cần ≥ 3 ví dụ (có {len(ex)})')
            elif len(ex) < 4: warns.append(f'{w} {p.get("pattern")}: nên có 4–6 ví dụ')
            for j, e in enumerate(ex):
                if not e.get('ja') or not e.get('vi'): errs.append(f'{w}.examples[{j}]: thiếu ja/vi')
            if not p.get('compare'): warns.append(f'{w} {p.get("pattern")}: chưa có compare')
            if not p.get('tip'): warns.append(f'{w} {p.get("pattern")}: chưa có tip')
            if len(p.get('explain', '')) < 150: warns.append(f'{w} {p.get("pattern")}: explain hơi ngắn')
    elif track == 'goi':
        secs = d.get('sections') or []
        if not secs: errs.append('thiếu sections')
        nw = 0
        for i, s in enumerate(secs):
            for j, wd in enumerate(s.get('words') or []):
                nw += 1
                w = f'sections[{i}].words[{j}]'
                for k in ('id', 'w', 'r', 'vi'):
                    if not wd.get(k): errs.append(f'{w}: thiếu {k}')
                if wd.get('id') in refs: errs.append(f'{w}: id trùng {wd.get("id")}')
                refs.add(wd.get('id'))
                if wd.get('key') and not (wd.get('ex') or wd.get('senses')): errs.append(f'{w} {wd.get("w")}: từ key cần ex')
                if wd.get('ex') and (not wd['ex'].get('ja') or not wd['ex'].get('vi')): errs.append(f'{w}: ex thiếu ja/vi')
        if nw < 15: warns.append(f'chỉ có {nw} từ')
        if not d.get('focus'): warns.append('chưa có focus')
    else:
        if not d.get('strategy'): errs.append('thiếu strategy')
        if not d.get('signals'): warns.append('chưa có signals')
        if not passages: errs.append('thiếu passages')
        if not d.get('worked'): errs.append('thiếu worked')
        for i, q in enumerate(d.get('worked') or []):
            if not q.get('walkthrough'): errs.append(f'worked[{i}]: thiếu walkthrough')

    ids = collections.Counter()
    pass_sets = collections.defaultdict(set)
    sets = ['quiz', 'practice', 'test'] + (['worked'] if track == 'dokkai' else [])
    for name in sets:
        qs = d.get(name) or []
        mn = SIZES[track].get(name, 1)
        if len(qs) < mn: errs.append(f'{name}: cần ≥ {mn} câu (có {len(qs)})')
        for i, q in enumerate(qs):
            check_q(q, f'{name}[{i}] {q.get("id", "")}', track, refs, passages, errs, warns)
            ids[q.get('id')] += 1
            if q.get('pass'): pass_sets[q['pass']].add(name)
        if len(qs) >= 8:
            c = collections.Counter(q.get('answer') for q in qs)
            if c.most_common(1)[0][1] / len(qs) > 0.45: warns.append(f'{name}: đáp án dồn vào vị trí {c.most_common(1)[0][0]} ({dict(c)})')
        if track == 'bunpo' and name in ('practice', 'test') and not any(q.get('kind') == 'order' for q in qs):
            warns.append(f'{name}: chưa có câu 並べ替え (order)')
    for k, n in ids.items():
        if n > 1: errs.append(f'id câu hỏi trùng: {k}')
    for pid, s in pass_sets.items():
        if len(s) > 1: warns.append(f'đoạn {pid} dùng ở nhiều bộ: {sorted(s)}')
    walk_texts(d, d.get('id', '?'), errs)
    return errs, warns


def main():
    files = sys.argv[1:] or sorted(str(p) for p in (ROOT / 'data' / 'study').glob('*/*.json'))
    bad = 0
    for f in files:
        errs, warns = check_file(f)
        status = 'OK' if not errs else 'ERROR'
        print(f'== {Path(f).name}: {status} ({len(errs)} lỗi, {len(warns)} cảnh báo)')
        for e in errs: print('  ERROR', e)
        for w in warns: print('  WARN ', w)
        bad += bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
