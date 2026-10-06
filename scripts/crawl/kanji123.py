# -*- coding: utf-8 -*-
"""Crawler for https://kanji123.org/ N3 kanji tests (10 tests x 20 questions).

How the site works: each test page (GET /n3-kanji-testN) is a Laravel form with
20 radio groups answer[N]=1..4 and a CSRF ``_token``; grading is server side at
POST /result/n3-kanji-testN. The result page echoes every question + options and
marks the correct option div with class ``true`` (the user's wrong pick gets
``false``). So per test we do ONE GET (token+session) and ONE POST (all "1"),
and parse the result page. Result pages are cached, so re-runs are free.

Reference kanji list: the site has NO kanji list (only tests + an English
WordPress blog), so crawl/raw/ref_kanji_kanji123.json cannot be produced.
"""
import json, re, sys, time
from pathlib import Path
try:
    import requests
except ModuleNotFoundError:  # `python -I` skips user site-packages
    import site; sys.path.append(site.getusersitepackages()); import requests
from bs4 import BeautifulSoup

BASE = "https://kanji123.org/"
SRC = "kanji123"
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "crawl" / "cache" / SRC
OUT = ROOT / "crawl" / "raw" / f"{SRC}.json"
UA = "Mozilla/5.0 (compatible; JLPT-study-crawler/1.0; personal study use)"
SLEEP = 0.8
TESTS = range(1, 11)

session = requests.Session()
session.headers["User-Agent"] = UA


def get_result_html(t: int) -> str:
    p = CACHE / f"result_n3_{t}.html"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    url = f"{BASE}n3-kanji-test{t}"
    time.sleep(SLEEP)
    r = session.get(url, timeout=30)
    r.raise_for_status()
    (CACHE / f"n3-kanji-test{t}.html").write_bytes(r.content)
    m = re.search(r'name="_token" value="([^"]+)"', r.text)
    if not m:
        raise RuntimeError(f"no _token on {url}")
    data = {"_token": m.group(1), "level": "3", "test_number": str(t)}
    for i in range(1, 21):
        data[f"answer[{i}]"] = "1"
    time.sleep(SLEEP)
    r2 = session.post(f"{BASE}result/n3-kanji-test{t}", data=data, headers={"Referer": url}, timeout=30)
    r2.raise_for_status()
    p.write_bytes(r2.content)
    return r2.text


def flatten(node):
    """Stem text: <fg t="reading">漢字</fg> -> 漢字 (furigana dropped), <u>word</u> -> ＿word＿."""
    has_fg = node.find("fg") is not None
    for fg in node.find_all("fg"):
        fg.replace_with(fg.get_text())
    for u in node.find_all("u"):
        u.replace_with("＿" + u.get_text() + "＿")
    txt = re.sub(r"\s+", " ", node.get_text()).strip()
    return txt, has_fg


KANJI_RE = re.compile(r"[一-鿿]")


def parse_result(t: int, html: str):
    soup = BeautifulSoup(html, "lxml")
    out, dropped = [], {}
    url = f"{BASE}n3-kanji-test{t}"
    for blk in soup.select("div.answer.section-anchor[id^=question-]"):
        n = int(blk["id"].split("-")[1])
        stem_node = blk.select_one("p.question_number_content")
        if stem_node is None:
            dropped["no_stem"] = dropped.get("no_stem", 0) + 1
            continue
        stem, has_fg = flatten(stem_node)
        trans = blk.select_one(".question-translation")
        trans = re.sub(r"\s+", " ", trans.get_text()).strip() if trans else None
        opts = []
        for od in blk.select(".answer-list .answer_answer"):
            inp = od.find("input")
            val = int(inp["value"]) if inp and inp.get("value") else 99
            text = re.sub(r"\s+", " ", od.get_text()).strip()
            text = re.sub(r"^\d+\.\s*", "", text)
            opts.append((val, text, "true" in od.get("class", [])))
        opts.sort(key=lambda o: o[0])
        options = [o[1] for o in opts]
        correct = [i for i, o in enumerate(opts) if o[2]]
        if len(correct) != 1:
            dropped["no_single_correct"] = dropped.get("no_single_correct", 0) + 1
            continue
        if not (2 <= len(options) <= 4) or not all(options) or not stem:
            dropped["bad_options_or_stem"] = dropped.get("bad_options_or_stem", 0) + 1
            continue
        kanji_opts = sum(1 for o in options if KANJI_RE.search(o))
        if "_____" in stem:
            # blank-fill drills (ASCII underscores in source) -> normalise marker
            stem = re.sub(r"_{3,}", "＿＿＿", stem)
            if all(len(o) == 1 and KANJI_RE.match(o) for o in options):
                mondai, qtype = None, "kanji_meaning"   # complete the kanji compound (第10＿＿＿ -> 課)
            else:
                mondai, qtype = 3, "context"            # choose the word that fits
        elif kanji_opts == 0:
            mondai, qtype = 1, "kanji_reading"      # underlined kanji -> choose reading
        elif kanji_opts == len(options):
            mondai, qtype = 2, "orthography"        # underlined kana -> choose kanji
        else:
            mondai, qtype = None, "kanji_meaning"
        out.append({
            "id": f"{SRC}:n3-t{t}-q{n}",
            "source": SRC,
            "source_url": url,
            "exam": f"kanji123 N3 Kanji Test {t}",
            "section": "moji",
            "mondai": mondai,
            "type": qtype,
            "passage": None,
            "passage_id": None,
            "question": stem,
            "options": options,
            "answer": correct[0],
            "explanation": f"EN: {trans}" if trans else None,
            "audio": None,
            "image": None,
            "transcript": None,
            "furigana": has_fg,
        })
    return out, dropped


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    all_q, drops = [], {}
    for t in TESTS:
        html = get_result_html(t)
        qs, d = parse_result(t, html)
        for k, v in d.items():
            drops[k] = drops.get(k, 0) + v
        print(f"  test {t}: {len(qs)} questions, dropped {d}")
        all_q.extend(qs)
    seen, uniq = set(), []
    for q in all_q:
        if q["id"] in seen:
            drops["dup_id"] = drops.get("dup_id", 0) + 1
            continue
        seen.add(q["id"])
        uniq.append(q)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("\nSUMMARY kanji123")
    print(" total:", len(uniq))
    print(" per section/type:", dict(Counter((q["section"], q["type"]) for q in uniq)))
    print(" with explanation (EN translation):", sum(1 for q in uniq if q["explanation"]))
    print(" with furigana flattened:", sum(1 for q in uniq if q["furigana"]))
    print(" dropped:", drops)
    print(" NOTE: no kanji reference list exists on kanji123.org -> ref_kanji_kanji123.json not produced.")


if __name__ == "__main__":
    main()
