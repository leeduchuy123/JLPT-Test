# -*- coding: utf-8 -*-
"""Crawler for https://jlpt.u-biq.org/ (日本語能力試験学習サイト, U-biq, 2009).

IMPORTANT LEVEL NOTE
--------------------
The site predates the 2010 JLPT reform and uses the OLD 1級–4級 scale. There are
NO N3 pages. Old 3級 ≈ today's N4; old 2級 ≈ N2 (its vocabulary/kanji/grammar
lists cover what was later split into N3+N2). We crawl BOTH neighbouring levels
(2級 and 3級) and tag every question with an extra field ``level_hint`` so the
consumer can decide which to keep. Nothing here is "certified N3".

Page naming: <level><kind><n>.html  kind: k=漢字, v=語彙, g=文法.
Answer key: inline JS ``document.test.qNN[IDX].checked`` (0-based index).
Encoding: Shift_JIS (decoded as cp932 for circled numerals / roman numerals).
"""
import hashlib, json, os, re, sys, time
from pathlib import Path
try:
    import requests
except ModuleNotFoundError:  # `python -I` skips user site-packages
    import site; sys.path.append(site.getusersitepackages()); import requests

BASE = "https://jlpt.u-biq.org/"
SRC = "ubiq"
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "crawl" / "cache" / SRC
OUT = ROOT / "crawl" / "raw" / f"{SRC}.json"
UA = "Mozilla/5.0 (compatible; JLPT-study-crawler/1.0; personal study use)"
SLEEP = 0.8

# old level -> (level_hint, pages)
LEVELS = {
    "2": "old-2kyuu (approx. N2; superset of N3 range)",
    "3": "old-3kyuu (approx. N4)",
}
KIND_NAME = {"k": "漢字", "v": "語彙", "g": "文法"}

session = requests.Session()
session.headers["User-Agent"] = UA


def fetch(name: str) -> str:
    p = CACHE / name
    if p.exists():
        raw = p.read_bytes()
    else:
        time.sleep(SLEEP)
        r = session.get(BASE + name, timeout=30)
        r.raise_for_status()
        raw = r.content
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    return raw.decode("cp932", "replace")


def clean(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    s = s.replace("\u3000", " ")
    s = re.sub(r"[ \t\r]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    s = re.sub(r"（\s*）", "（　）", s)  # keep the JLPT blank marker in its canonical full-width form
    return s.strip()


CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
RE_LEADNUM = re.compile(r"^[０-９0-9]+[）)]\s*")


def parse_page(name: str, html: str, level: str, kind: str):
    url = BASE + name
    key = {q: int(i) for q, i in re.findall(r"document\.test\.(q\d+)\[(\d+)\]\.checked", html)}
    m = re.search(r"<form[^>]*>(.*?)</form>", html, flags=re.S)
    if not m:
        return [], {"no_form": 1}
    form = m.group(1)
    title = clean(re.search(r"<h3>(.*?)</h3>", html, flags=re.S).group(1)).split("\n")[0] if "<h3>" in html else name
    exam = f"ubiq 旧{level}級 {KIND_NAME[kind]}{name[2:-5]}"
    out, dropped = [], {}

    # Walk the form: 問題 headers and <p> blocks in document order.
    header = ""
    for tok in re.finditer(r'<div class="mondai">(.*?)</div>|<p>(.*?)(?=<p>|</form>|$)', form, flags=re.S):
        if tok.group(1) is not None:
            header = clean(tok.group(1))
            continue
        block = tok.group(2)
        if 'name="q' not in block and "name=q" not in block:
            continue
        # split on the result-text inputs; part[0] is the sentence
        parts = re.split(r'<input type=text name="(q\d+)_o"[^>]*>', block)
        stem_html = re.sub(r"[%s]" % CIRCLED, "", parts[0])
        subs = list(zip(parts[1::2], parts[2::2]))
        if len(subs) == 1:
            # single question per sentence: keep the source's underline as ＿…＿ (unless the whole stem is underlined)
            plain = RE_LEADNUM.sub("", clean(stem_html))
            us = [clean(u) for u in re.findall(r"<u>(.*?)</u>", stem_html, flags=re.S)]
            if us and not (len(us) == 1 and us[0] == plain):
                stem_html = re.sub(r"<u>(.*?)</u>", lambda m: "＿" + m.group(1) + "＿", stem_html, flags=re.S)
        stem = RE_LEADNUM.sub("", clean(stem_html))
        for qname, seg in subs:
            # label before first radio (kanji pages: "①週末　：　")
            first_radio = re.search(r'<input type="radio"', seg)
            label = clean(seg[: first_radio.start()]) if first_radio else ""
            opts_html = re.split(r'<input type="radio"[^>]*>', seg[first_radio.start():] if first_radio else "")[1:]
            options = []
            for o in opts_html:
                o = re.split(r"<br|</p>|<input", o)[0]
                options.append(clean(o))
            options = [o for o in options if o]
            if qname not in key:
                dropped["no_answer_key"] = dropped.get("no_answer_key", 0) + 1
                continue
            ans = key[qname]
            if not (2 <= len(options) <= 4) or ans >= len(options):
                dropped["bad_options"] = dropped.get("bad_options", 0) + 1
                continue
            question = stem
            target = None
            if label:
                target = re.sub(r"[%s]" % CIRCLED, "", label).replace("：", "").replace(":", "").strip()
                if target and target in stem:
                    question = stem.replace(target, f"＿{target}＿", 1)
                elif target:
                    question = f"{stem}\n＿{target}＿"
            if not question:
                dropped["empty_stem"] = dropped.get("empty_stem", 0) + 1
                continue
            # type mapping from header + kind
            hn = header.replace(" ", "")
            if "読み方" in hn or "よみかた" in hn:
                section, mondai, qtype = "moji", 1, "kanji_reading"
            elif "同じひらがなで書く漢字" in hn:
                # homophone drill: pick the kanji word read the same as the underlined word; keep the instruction
                section, mondai, qtype = "moji", None, "orthography"
                question = question + "\n（＿＿＿と同じひらがなで書く漢字を選びなさい。）"
            elif "正しい漢字" in hn or "ただしいかんじ" in hn:
                section, mondai, qtype = "moji", 2, "orthography"
            elif "使い方" in hn:
                section, mondai, qtype = "moji", 5, "usage"
            elif "同じ文" in hn or "同じ意味" in hn:
                section, mondai, qtype = "moji", 4, "paraphrase"
            elif kind == "k":
                section, mondai, qtype = "moji", None, "kanji_meaning"
            elif kind == "v":
                section, mondai, qtype = "moji", 3, "context"
            else:
                section, mondai, qtype = "bunpo", 1, "grammar_form"
            out.append({
                "id": f"{SRC}:{name[:-5]}-{qname}",
                "source": SRC,
                "source_url": url,
                "exam": exam,
                "section": section,
                "mondai": mondai,
                "type": qtype,
                "passage": None,
                "passage_id": None,
                "question": question,
                "options": options,
                "answer": ans,
                "explanation": None,
                "audio": None,
                "image": None,
                "transcript": None,
                "furigana": False,
                "level_hint": LEVELS[level],
                "page_title": title,
            })
    return out, dropped


def main():
    index = fetch("index.html")
    links = sorted(set(re.findall(r'href="([234][kvg]\d+\.html)"', index)))
    pages = [l for l in links if l[0] in LEVELS]
    print(f"index links for levels {list(LEVELS)}: {pages}")
    all_q, drops = [], {}
    for name in pages:
        level, kind = name[0], name[1]
        html = fetch(name)
        qs, d = parse_page(name, html, level, kind)
        for k, v in d.items():
            drops[k] = drops.get(k, 0) + v
        print(f"  {name}: {len(qs)} questions, dropped {d}")
        all_q.extend(qs)
    # de-dupe by id
    seen, uniq = set(), []
    for q in all_q:
        if q["id"] in seen:
            drops["dup_id"] = drops.get("dup_id", 0) + 1
            continue
        seen.add(q["id"]); uniq.append(q)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("\nSUMMARY ubiq")
    print(" total:", len(uniq))
    print(" per level_hint:", dict(Counter(q["level_hint"] for q in uniq)))
    print(" per section/type:", dict(Counter((q["section"], q["type"]) for q in uniq)))
    print(" with explanation:", sum(1 for q in uniq if q["explanation"]))
    print(" dropped:", drops)
    print(" NOTE: site uses OLD 1-4級 scale; no true N3 pages exist. See level_hint.")


if __name__ == "__main__":
    main()
