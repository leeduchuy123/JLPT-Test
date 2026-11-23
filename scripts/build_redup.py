# -*- coding: utf-8 -*-
"""Từ láy (畳語・擬音語/擬態語 dạng lặp) trong các đề JLPT đã thi -> data/redup.json

  crawl/redup/exams_<N3|N2>.json   các đề đã tải (scripts/crawl/masceron.py)
  crawl/redup/lexicon.json         danh mục soạn tay: nghĩa tiếng Việt, cách đọc, nhóm, các dạng viết;
                                   "skip" = dạng lặp do máy bắt được nhưng không phải từ láy
  -> data/redup.json               từ + số đề xuất hiện + câu ví dụ lấy từ đề + câu hỏi đề thật có từ láy

Định dạng data/redup.json:
  levels.<N3|N2> = {exams: ["2010-07", ...], questions: [{id, exam, type, stem, options, answer (0-based), words: [mã từ],
                    ow: [[mã từ trong lựa chọn 1], ...], target: mã từ mà câu thực sự kiểm tra | ""}]}
  words[] = {id (= cách đọc), w, read, forms, vi, group, note?, near?, x?: {ja, vi} (ví dụ tự soạn),
             lv: {<N3|N2>: {n: số lần gặp, exams: [...], tested: số câu hỏi từ vựng có từ này, ex: [{ja, f: chữ cần tô đậm, src}]}}}

Chạy từ thư mục gốc:
  python -I scripts/build_redup.py                          # build
  python -I scripts/build_redup.py --candidates [N3] [--new]  # liệt kê dạng lặp bắt được (để soạn lexicon)

Máy chỉ tìm ứng viên (AB+AB, có biến âm đục; X々; cụm kanji+kana lặp); từ nào được tính là từ láy
và nghĩa là gì do lexicon quyết định. Dạng chưa có trong lexicon lẫn skip được in ra cuối để không sót.
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "crawl", "redup")
OUT = os.path.join(ROOT, "data", "redup.json")
LEVELS = ("N3", "N2")
MAX_EX = 5          # số câu ví dụ giữ lại cho mỗi từ ở mỗi cấp
MAX_EX_LEN = 110    # câu dài hơn thì chỉ dùng khi không có câu nào ngắn hơn

# ---------------------------------------------------------------- nhận dạng dạng lặp
KANA = re.compile(r"[ぁ-ゖァ-ヺー]")
KANJI = "一-龯"
SMALL = set("ぁぃぅぇぉっゃゅょゎーんァィゥェォッャュョヮン")
VOICED = dict(zip("がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ", "かきくけこさしすせそたちつてとはひふへほはひふへほ"))
RENDAKU = {k: v for k, v in VOICED.items() if k not in "ぱぴぷぺぽ"}


def hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def base(s):
    """Bỏ dấu đục / bán đục: đề gõ nhầm ペらべら -> へら|へら."""
    return "".join(VOICED.get(c, c) for c in s)


def is_kana(s):
    return bool(s) and all(KANA.match(c) for c in s)


ADJ = r"し[いくさげ]|しかっ|しけれ"      # đuôi tính từ: 騒々しい, ずうずうしく ...
RE_NOMA = re.compile(rf"([{KANJI}])々({ADJ})?")
RE_ADJ = re.compile(rf"＿?(?:{ADJ})")   # ＿そうぞう＿しく: phần gạch chân có thể dừng trước đuôi
RE_MIXED = re.compile(rf"((?=[ぁ-ん]{{0,3}}[{KANJI}])[{KANJI}ぁ-ん]{{2,4}})\1")
SPECIAL = ["一人ひとり", "ひとり一人", "一つひとつ", "ひとつ一つ", "1人1人", "1つ1つ", "１人１人", "１つ１つ"]


def find_redup(text, fuzzy=False, extra=()):
    """-> [(start, end, surface, form)] không chồng nhau, theo thứ tự xuất hiện.
    surface = đúng đoạn chữ trong câu (騒々しく); form = dạng để tra lexicon (騒々しい, katakana -> hiragana).
    fuzzy: chấp nhận hai nửa chỉ khác dấu đục (lỗi gõ của đề), chỉ nên bật cho lựa chọn ngắn.
    extra: các dạng viết khai trong lexicon mà quy tắc lặp không tự bắt được (vd. 徐々に), tìm nguyên văn."""
    hits = []
    for sp in (*SPECIAL, *extra):
        for m in re.finditer(re.escape(sp), text):
            hits.append((m.start(), m.end(), sp, hira(sp)))
    for m in RE_NOMA.finditer(text):
        hits.append((m.start(), m.end(), m.group(0), m.group(1) + "々" + ("しい" if m.group(2) else "")))
    for m in RE_MIXED.finditer(text):
        hits.append((m.start(), m.end(), m.group(0), m.group(0)))
    i, n = 0, len(text)
    while i < n:
        if not KANA.match(text[i]) or text[i] in SMALL:
            i += 1
            continue
        for L in (4, 3, 2):
            a, b = text[i:i + L], text[i + L:i + 2 * L]
            if len(b) < L or not is_kana(a + b) or len(set(a)) == 1:
                continue
            ha, hb = hira(a), hira(b)
            if hb == ha or (hb[1:] == ha[1:] and RENDAKU.get(hb[0]) == ha[0]) or (fuzzy and base(hb) == base(ha)):
                adj = RE_ADJ.match(text, i + 2 * L)
                end = adj.end() if adj else i + 2 * L
                hits.append((i, end, text[i:end].replace("＿", ""), ha + hb + ("しい" if adj else "")))
                i = end - 1
                break
        i += 1
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out, end = [], -1
    for h in hits:
        if h[0] >= end:
            out.append(h)
            end = h[1]
    return out


def norm_form(surface):
    """Khoá so khớp với lexicon: katakana -> hiragana."""
    return hira(surface)


def forms_in(text, **kw):
    """Các dạng chuẩn hoá tìm thấy trong một đoạn ngắn."""
    return [h[3] for h in find_redup(text, **kw)]


# ---------------------------------------------------------------- đọc đề thành các đơn vị văn bản
RE_NUM = re.compile(r"^\s*(?:【\s*[0-9０-９]+\s*】|\(?[0-9０-９]{1,3}\s*[.．)）]|[0-9０-９]{1,2}\s*番)\s*")
RE_BLANK = re.compile(r"[（(][\s　_＿]*[）)]")
RE_HOLE = re.compile(r"【\s*[0-9０-９]+\s*】|[（(]\s*[0-9０-９]{1,2}\s*[）)]|[（(][\s　_＿]*[）)]|[＿_]{2,}")
RE_SENT = re.compile(r"[^。！？!?\n]*[。！？!?]?")
PART_VI = {"vocab": "Từ vựng", "reading": "Ngữ pháp · Đọc", "listening": "Nghe"}
SECT_JP = {"moji": "語彙", "bunpo": "文法", "dokkai": "読解", "choukai": "聴解"}


def exam_vi(label):
    y, m = label.split("-")
    return f"{int(m)}/{y}"


JA = "ぁ-んァ-ヶー一-龯々、。"
RE_JA_GAP = re.compile(rf"(?<=[{JA}])[ \u3000]+(?=[{JA}])")


def plain(s):
    """Câu để làm ví dụ: bỏ dấu gạch chân của đề và khoảng trắng thừa giữa các chữ Nhật."""
    return RE_JA_GAP.sub("", re.sub(r"\s+", " ", (s or "").replace("＿", "")).strip())


def clean_q(it):
    """-> (thân câu, [lựa chọn]) đã bỏ số thứ tự mà trang nguồn để lẫn trong chữ ("17 街を…", ".誰にも…", "1 だれにも…")."""
    stem = RE_NUM.sub("", it["stem"] or "").strip()
    if it.get("n") is not None:
        stem = re.sub(rf"^{it['n']}\s+(?=\D)", "", stem)
    stem = re.sub(r"^[.．]\s*", "", stem)
    opts = [o.strip() for o in it["options"]]
    if len(opts) > 1 and all(re.match(rf"^{k + 1}\s+\S", o) for k, o in enumerate(opts)):
        opts = [re.sub(r"^\d\s+", "", o) for o in opts]
    return stem, opts


def sentences(text):
    for m in RE_SENT.finditer(text or ""):
        s = m.group(0).strip()
        if s:
            yield s


def has_blank(stem):
    return bool(RE_BLANK.search(stem) or re.search(r"[＿_]{2,}", stem))


def qtype(sect, heading, stem):
    """context | paraphrase | usage | reading | orthography | grammar | None (dạng khác).
    Dựa vào tiêu đề 問題 và hình dạng câu, vì số 問題 trên trang nguồn không ổn định giữa các kỳ."""
    h = heading or ""
    if sect == "bunpo":
        if "★" in stem or stem.count("＿＿＿") >= 2 or "★" in h:
            return None
        return "grammar" if has_blank(stem) else None
    if sect != "moji":
        return None
    if re.fullmatch(r"＿[^＿]+＿", stem.strip()) or "使い方" in h:
        return "usage"
    if "読み方" in h:
        return "reading"
    if "漢字" in h:
        return "orthography"
    if "近い" in h:
        return "paraphrase"
    return "context" if has_blank(stem) else ("paraphrase" if "＿" in stem else "context")


def units_of(page):
    """Mỗi đơn vị: dict(text, role, sect, mondai, n, ok, qtype, split, example?, answer_text?)
    role: stem | option | passage | script ; ok = lựa chọn đúng ; example = câu dùng được làm ví dụ (hoặc None)."""
    part = page["part"]
    heading = ""
    for it in page["items"]:
        if it["kind"] == "heading":
            heading = it["text"]
        elif it["kind"] == "passage":
            if part == "listening":
                continue   # lời hướng dẫn / ô "メモ", không phải nội dung đề
            sect = "dokkai" if part == "reading" and (it["mondai"] or 9) > 3 else "bunpo"
            yield dict(text=it["text"], role="passage", sect=sect, mondai=it["mondai"], n=None, ok=False, split=True, qtype=None)
        elif it["kind"] == "q":
            sect, md, n = it["sect"], it["mondai"], it["n"]
            stem, opts = clean_q(it)
            qt = qtype(sect, heading, stem)
            ans = it["answer"]
            right = opts[ans] if ans is not None and ans < len(opts) else None
            blanks = RE_BLANK.findall(stem)
            if sect == "choukai" or qt == "usage":
                filled = None            # "1番" / chỉ có mỗi từ được hỏi
            elif "★" in stem or stem.count("＿＿＿") >= 2:
                filled = None            # câu sắp xếp: thân câu không phải câu hoàn chỉnh
            elif len(blanks) == 1 and right and len(right) <= 30:
                filled = RE_BLANK.sub(lambda _: plain(right), stem, count=1)
            elif not blanks:
                filled = stem
            else:
                filled = None
            yield dict(text=stem, role="stem", sect=sect, mondai=md, n=n, ok=False, split=False, qtype=qt,
                       example=plain(filled) if filled else None, answer_text=right)
            for k, o in enumerate(opts):
                if not o.strip():
                    continue
                if qt == "reading" or (qt == "orthography" and k != ans):
                    continue   # cách đọc bằng kana / chữ Hán sai do đề bịa ra: không phải từ để học
                # lựa chọn sai của câu "cách dùng" là câu dùng SAI từ -> không bao giờ làm ví dụ
                yield dict(text=o, role="option", sect=sect, mondai=md, n=n, ok=(k == ans), split=False, qtype=qt,
                           example=plain(o) if (k == ans and len(o) > 12) else None)
            if it.get("ref") and sect == "choukai":
                # GT của bài nghe = script. GT các phần khác là lời giải thích (có khi bằng tiếng Trung) -> bỏ.
                yield dict(text=it["ref"], role="script", sect=sect, mondai=md, n=n, ok=False, split=True, qtype=qt)


def load_level(level):
    path = os.path.join(SRC, f"exams_{level}.json")
    if not os.path.exists(path):
        sys.exit(f"Thiếu {path}: chạy  python -I scripts/crawl/masceron.py {level}  trước")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def usable(ex, surface):
    """Câu đủ dài, không còn chỗ trống của đề."""
    return bool(ex) and surface in ex and len(ex) >= len(surface) + 4 and not RE_HOLE.search(ex)


def scan(level_data, extra=()):
    """-> occurrences: [dict(form, surface, exam, part, sect, mondai, n, role, ok, under, example)]"""
    occ = []
    for page in level_data["pages"]:
        def add(u, surf, form, role, ok, ex, under=False):
            occ.append(dict(form=form, surface=surf, exam=page["exam"], part=page["part"], sect=u["sect"],
                            mondai=u["mondai"], n=u["n"], role=role, ok=ok, under=under,
                            example=ex if usable(ex, surf) else None))

        for u in units_of(page):
            text = u["text"]
            fuzzy = u["role"] == "option" and len(text) <= 10
            for (s, e, surf, form) in find_redup(text, fuzzy=fuzzy, extra=extra):
                ex = None
                if u["split"]:
                    pos = 0
                    for sent in sentences(text):
                        at = text.find(sent, pos)
                        pos = at + len(sent)
                        if at <= s < pos:
                            ex = re.sub(r"^[」』）)、。・\s]+", "", plain(sent))
                            break
                    if ex and u["role"] == "script":
                        if re.match(r"^[1-4１-４][\s.．)）、:：]", ex):
                            ex = None  # lựa chọn được đọc trong bài nghe: có thể là câu sai
                        else:
                            ex = re.sub(r"^(?:[男女MFＭＦ][0-9１２]?|[（(][男女][）)])\s*[:：]?\s*", "", ex)
                else:
                    ex = u.get("example")
                add(u, surf, form, u["role"], u["ok"], ex, under=text[max(s - 1, 0):s] == "＿" or "＿" in text[s:e + 1])
            # từ nằm trong đáp án được điền vào thân câu: câu hoàn chỉnh là ví dụ của từ đó
            if u["role"] == "stem" and u.get("example") and u.get("answer_text") and has_blank(text):
                for (_, _, surf, form) in find_redup(u["answer_text"], fuzzy=len(u["answer_text"]) <= 10, extra=extra):
                    add(u, surf, form, "filled", True, u["example"])
    return occ


# ---------------------------------------------------------------- lexicon
def load_lexicon():
    path = os.path.join(SRC, "lexicon.json")
    if not os.path.exists(path):
        return {"words": [], "skip": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def index_lexicon(lex):
    """-> (by_form: dạng đã chuẩn hoá -> mục từ, extra: các dạng phải tìm nguyên văn)"""
    by_form, ids, extra = {}, set(), []
    for w in lex["words"]:
        wid = w["read"]
        if wid in ids:
            sys.exit(f"lexicon: trùng cách đọc {wid}")
        ids.add(wid)
        # "noread": cách đọc viết bằng kana dễ trùng chữ khác (vd. どうどう trong かどうか) -> không tự coi là một dạng viết
        for form in {w["w"], *w.get("forms", []), *w.get("typos", []), *([] if w.get("noread") else [w["read"]])}:
            k = norm_form(form)
            if k in by_form and by_form[k] is not w:
                sys.exit(f"lexicon: dạng {form} thuộc hai mục ({by_form[k]['w']} / {w['w']})")
            by_form[k] = w
            if forms_in(form, fuzzy=True) != [k]:
                extra.append(form)
    return by_form, sorted(set(extra), key=len, reverse=True)


def candidates():
    lex = load_lexicon()
    by_form, extra = index_lexicon(lex)
    skip = {norm_form(k) for k in lex.get("skip", {})}
    only = "--new" in sys.argv
    for level in [a for a in sys.argv[1:] if a in LEVELS] or LEVELS:
        occ = scan(load_level(level), extra)
        agg = defaultdict(lambda: dict(n=0, exams=set(), surf=Counter(), roles=Counter(), ex=[]))
        for o in occ:
            a = agg[o["form"]]
            a["n"] += 1
            a["exams"].add(o["exam"])
            a["surf"][o["surface"]] += 1
            a["roles"][f"{o['part'][0]}:{o['role']}"] += 1
            if o["example"] and len(a["ex"]) < 2 and o["example"] not in a["ex"]:
                a["ex"].append(o["example"][:70])
        print(f"\n===== {level}: {len(agg)} dạng =====")
        for form, a in sorted(agg.items(), key=lambda kv: (-len(kv[1]["exams"]), kv[0])):
            mark = "✓" if form in by_form else ("✗" if form in skip else "?")
            if only and mark != "?":
                continue
            surf = "/".join(f"{s}{c}" for s, c in a["surf"].most_common(3))
            roles = ",".join(f"{r}{c}" for r, c in a["roles"].most_common(4))
            print(f"{mark} {form}\t{len(a['exams'])}đề {a['n']}x\t{surf}\t{roles}\t{' ‖ '.join(a['ex'])}")


# ---------------------------------------------------------------- build
SRC_RANK = {("vocab", "filled"): 0, ("vocab", "option"): 1, ("vocab", "stem"): 1, ("reading", "filled"): 2, ("reading", "stem"): 2,
            ("reading", "option"): 3, ("reading", "passage"): 4, ("vocab", "passage"): 4, ("listening", "script"): 5}


def build():
    lex = load_lexicon()
    by_form, extra = index_lexicon(lex)
    skip = {norm_form(k) for k in lex.get("skip", {})}
    near = defaultdict(set)   # từ gần nghĩa: không dùng làm đáp án nhiễu của nhau (khai báo một chiều là đủ)
    reads = {w["read"] for w in lex["words"]}
    for w in lex["words"]:
        for other in w.get("near", []):
            if other not in reads:
                sys.exit(f"lexicon: near của {w['w']} trỏ tới {other} không có trong danh mục")
            near[w["read"]].add(other)
            near[other].add(w["read"])
    words = {w["read"]: dict(id=w["read"], w=w["w"], read=w["read"], forms=w.get("forms", []), vi=w["vi"],
                             group=w.get("group", "Khác"), **({"note": w["note"]} if w.get("note") else {}),
                             **({"near": sorted(near[w["read"]])} if near[w["read"]] else {}),
                             **({"x": w["ex"]} if w.get("ex") else {}), lv={})
             for w in lex["words"]}
    levels, unknown = {}, Counter()

    def ids_in(text):
        return [by_form[f]["read"] for f in forms_in(text, fuzzy=len(text) <= 10, extra=extra) if f in by_form]

    for level in LEVELS:
        data = load_level(level)
        per = defaultdict(list)
        for o in scan(data, extra):
            w = by_form.get(o["form"])
            if not w:
                if o["form"] not in skip:
                    unknown[o["form"]] += 1
                continue
            per[w["read"]].append(o)

        for wid, lst in per.items():
            exams = sorted({o["exam"] for o in lst})
            asked = {(o["exam"], o["n"]) for o in lst if o["sect"] == "moji" and (o["role"] == "option" or o["under"])}
            seen, ex = set(), []
            cands = [o for o in lst if o["example"]]
            cands.sort(key=lambda o: (len(o["example"]) > MAX_EX_LEN or "注" in o["example"][:6],
                                      SRC_RANK.get((o["part"], o["role"]), 9), -int(o["exam"][:4]), o["exam"]))
            for o in cands:
                key = re.sub(r"\W", "", o["example"])
                if key in seen:
                    continue
                seen.add(key)
                md = f" 問題{o['mondai']}" if o["mondai"] else ""
                ex.append(dict(ja=o["example"], f=o["surface"], src=f"{level} {exam_vi(o['exam'])} · {SECT_JP.get(o['sect'], PART_VI[o['part']])}{md}"))
                if len(ex) >= MAX_EX:
                    break
            words[wid]["lv"][level] = dict(n=len(lst), exams=exams, tested=len(asked), ex=ex)

        # câu hỏi đề thật mà từ láy là từ được hỏi hoặc nằm trong các lựa chọn
        questions, seen_q = [], set()
        for page in data["pages"]:
            heading = ""
            for it in page["items"]:
                if it["kind"] == "heading":
                    heading = it["text"]
                if it["kind"] != "q" or it["answer"] is None or len(it["options"]) != 4:
                    continue
                stem, opts = clean_q(it)
                qt = qtype(it["sect"], heading, stem)
                if not qt or not stem or any(not o for o in opts) or len(set(opts)) < 4:
                    continue
                under = [i for t in re.findall(r"＿([^＿]+)＿", stem) for i in ids_in(t)]
                short = max(len(o) for o in opts) <= 14
                ow = [[], [], [], []]                       # từ láy trong từng lựa chọn
                if qt in ("reading", "orthography"):        # chỉ tính khi chính từ được hỏi là từ láy
                    asked = under or (ids_in(opts[it["answer"]]) if qt == "orthography" else [])
                elif qt == "usage":                         # thân câu chính là từ được hỏi
                    asked = under or ids_in(stem)
                else:
                    asked = under
                    if short:
                        ow = [ids_in(o) for o in opts]
                ids = list(dict.fromkeys(asked + [i for lst in ow for i in lst]))
                key = re.sub(r"\W", "", stem + "".join(opts))
                if not ids or key in seen_q:               # đề các kỳ đôi khi lặp lại nguyên một câu
                    continue
                seen_q.add(key)
                # target = từ mà câu này thực sự kiểm tra (đáp án đúng hoặc từ được hỏi); rỗng nếu từ láy chỉ là đáp án nhiễu
                target = (ow[it["answer"]] + asked + [""])[0]
                questions.append(dict(id=f"{level}:{page['exam']}:{page['part'][0]}{it['n']}", exam=page["exam"], type=qt,
                                      stem=stem, options=opts, answer=it["answer"], words=ids, ow=ow, target=target))
        levels[level] = dict(exams=sorted(data["exams"]), questions=questions)

    out_words = [w for w in words.values() if w["lv"]]
    out_words.sort(key=lambda w: (-sum(len(v["exams"]) for v in w["lv"].values()), w["read"]))
    never = [w["w"] for w in words.values() if not w["lv"]]
    groups = [g for g, _ in Counter(w["group"] for w in out_words).most_common()]
    out = dict(built=time.strftime("%Y-%m-%d"), source="masceron-jlpt.pages.dev", groups=groups, levels=levels, words=out_words)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print(f"-> {OUT}  ({os.path.getsize(OUT) / 1024:.0f} KB)")
    for level in LEVELS:
        ws = [w for w in out_words if level in w["lv"]]
        qs = levels[level]["questions"]
        print(f"{level}: {len(levels[level]['exams'])} kỳ · {len(ws)} từ láy · có trong câu hỏi từ vựng: "
              f"{sum(1 for w in ws if w['lv'][level]['tested'])} từ · không có câu ví dụ: {sum(1 for w in ws if not w['lv'][level]['ex'])} · "
              f"{len(qs)} câu đề thật {dict(Counter(q['type'] for q in qs))}")
    print("nhóm:", dict(Counter(w["group"] for w in out_words)))
    if never:
        print("có trong lexicon nhưng không gặp trong đề:", " ".join(never))
    if unknown:
        print(f"!! {len(unknown)} dạng lặp chưa phân loại (thêm vào lexicon.words hoặc lexicon.skip):")
        print("   " + " ".join(f"{k}×{v}" for k, v in unknown.most_common()))


if __name__ == "__main__":
    if "--candidates" in sys.argv:
        candidates()
    else:
        build()
