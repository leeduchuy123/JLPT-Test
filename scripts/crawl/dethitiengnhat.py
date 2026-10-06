# -*- coding: utf-8 -*-
"""Crawler for dethitiengnhat.com JLPT N3 mock exams -> crawl/raw/dethitiengnhat.json

Run from D:/JLPT-app:  python -I scripts/crawl/dethitiengnhat.py

Site structure (verified 2026-10):
  index  https://dethitiengnhat.com/jlpt/N3            lists exams  /jlpt/N3/<exam>/<part>
  part 1 = 文字・語彙, part 3 = 文法・読解 (part 2 is an alias of 3), part 4 = 聴解
  Each part page holds every question inline:
    div.big_item          問題 heading (listening: contains the Google-Drive audio iframe)
    div.question_content  reading passage (shared by the following questions)
    div.question_list     question stem  ("19. ...", "1番", "【19】")
    div.answer_2row/1row  options  div.answers#QS<n><k>  "k) text"
    div#AS<n>  (hidden)   1-based answer key
    div#GT<n>  (hidden)   explanation / listening transcript ("Tham khảo: ...")
    div#type<n> (hidden)  1=moji 2=bunpo 3=dokkai 4=choukai
"""
import json
import os
import re
import time
from collections import Counter
from urllib.parse import urljoin

import sys

try:
    import requests
    from bs4 import BeautifulSoup, NavigableString
except ModuleNotFoundError:  # `python -I` skips the per-user site-packages where these live
    import site
    sys.path.append(site.getusersitepackages())
    import requests
    from bs4 import BeautifulSoup, NavigableString

SOURCE = "dethitiengnhat"
BASE = "https://dethitiengnhat.com/"
INDEX_URL = BASE + "jlpt/N3"
CACHE_DIR = os.path.join("crawl", "cache", SOURCE)
OUT_PATH = os.path.join("crawl", "raw", SOURCE + ".json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JLPT-study-crawler/1.0 (personal study use)"
SLEEP = 0.8
PARTS = (1, 3, 4)

SECTION_BY_CODE = {"1": "moji", "2": "bunpo", "3": "dokkai", "4": "choukai"}
TYPE_MAP = {
    ("moji", 1): "kanji_reading", ("moji", 2): "orthography", ("moji", 3): "context",
    ("moji", 4): "paraphrase", ("moji", 5): "usage",
    ("bunpo", 1): "grammar_form", ("bunpo", 2): "sentence_order", ("bunpo", 3): "text_grammar",
    ("dokkai", 4): "reading_short", ("dokkai", 5): "reading_mid", ("dokkai", 6): "reading_long",
    ("dokkai", 7): "info_retrieval",
}
FALLBACK_TYPE = {"moji": "vocab_meaning", "bunpo": "grammar_misc", "dokkai": "reading_mid", "choukai": "listening"}
PASSAGE_TYPES = ("text_grammar", "reading_short", "reading_mid", "reading_long", "info_retrieval")

session = requests.Session()
session.headers["User-Agent"] = UA
_last_fetch = 0.0


def fetch(url, cache_name):
    """GET with on-disk cache + polite delay."""
    global _last_fetch
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, cache_name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    wait = SLEEP - (time.time() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    resp = session.get(url, timeout=30)
    _last_fetch = time.time()
    resp.raise_for_status()
    resp.encoding = "utf-8"
    html = resp.text
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return html


# ---------------------------------------------------------------- text utils
FW_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def _flatten(el):
    """In-place: <br> -> newline, <u>x</u> -> ＿x＿, drop <rt>/<rp>. Returns True if ruby was present."""
    had_ruby = False
    for br in el.find_all("br"):
        br.replace_with(NavigableString("\n"))
    for rt in el.find_all(["rt", "rp"]):
        had_ruby = True
        rt.decompose()
    for rb in el.find_all("ruby"):
        had_ruby = True
        rb.unwrap()
    for u in el.find_all("u"):
        inner = u.get_text()
        if inner.strip():
            u.replace_with(NavigableString("＿" + inner.strip() + "＿"))
        else:
            u.replace_with(NavigableString(inner))
    for cell in el.find_all(["td", "th"]):
        if cell.find_previous_sibling(["td", "th"]) is not None:
            cell.insert_before(NavigableString(" | "))
    for p in el.find_all(["p", "div", "center", "tr", "li", "h1", "h2", "h3", "h4", "h5"]):
        p.insert_before(NavigableString("\n"))
        p.insert_after(NavigableString("\n"))
    return had_ruby


def _clean_line(s):
    s = re.sub(r"[ \t\r\f\v\u00a0]+", " ", s)
    return s.strip(" \u3000\t\r\n")


def text_inline(el):
    """Single-line text (stems, options)."""
    had_ruby = _flatten(el)
    t = el.get_text()
    t = _clean_line(t.replace("\n", " "))
    return t, had_ruby


def text_block(el):
    """Multi-line text (passages, transcripts): keep line breaks."""
    had_ruby = _flatten(el)
    lines = [_clean_line(x) for x in el.get_text().split("\n")]
    t = "\n".join(lines)
    t = re.sub(r"\n{3,}", "\n\n", t).strip("\n ")
    return t, had_ruby


def media_in(el, page_url):
    """(audio_url, image_url) found inside an element."""
    audio = image = None
    for tag in el.find_all(["iframe", "audio", "source", "a"]):
        src = tag.get("src") or tag.get("href") or ""
        if not src:
            continue
        if ("drive.google.com" in src or tag.name in ("audio", "source")
                or re.search(r"\.(mp3|m4a|ogg|wav)(\?|$)", src, re.I)):
            audio = urljoin(page_url, src)
            break
    img = el.find("img")
    if img and img.get("src"):
        image = urljoin(page_url, img["src"])
    return audio, image


RE_MONDAI = re.compile(r"問\s*題\s*([0-9０-９]+)")
RE_OPT_PREFIX = re.compile(r"^\s*[1-4１-４]\s*[)）.．、]\s*")
RE_STEM_NUM = re.compile(r"^\s*(?:\(?[0-9０-９]{1,2}[).．、]\s*)")
RE_STEM_ID = re.compile(r"^\s*(?:【\s*([0-9０-９]+)\s*】|([0-9０-９]+)\s*[.．)）番])")
RE_TRANSCRIPT_OPT = re.compile(r"^\s*([1-4１-４])[\s.．)）、]+(.+?)\s*$")


# ---------------------------------------------------------------- page parser
def parse_part(html, exam_no, part, page_url, drops):
    soup = BeautifulSoup(html, "lxml")
    base = soup.find("base")
    base_url = urljoin(page_url, base["href"]) if base and base.get("href") else page_url

    hidden = {"AS": {}, "GT": {}, "type": {}}
    for d in soup.find_all("div", id=re.compile(r"^(AS|GT|type)(\d+)$")):
        m = re.match(r"^(AS|GT|type)(\d+)$", d["id"])
        hidden[m.group(1)][int(m.group(2))] = d

    nodes = soup.select("div.big_item, div.question_content, div.question_list, div.answer_2row, div.answer_1row")
    exam_name = f"{SOURCE} N3 Đề {exam_no}"
    results = []

    cur_mondai = None
    cur_hint = {1: "moji", 3: "bunpo", 4: "choukai"}[part]
    cur_audio = None
    passage = passage_id = passage_img = None
    passage_counter = 0
    pending = None  # dict(stem, image, audio, n, ruby)
    orphans = []  # passage-type questions emitted before their passage appeared

    for node in nodes:
        cls = node.get("class", [])
        if "big_item" in cls:
            audio, _ = media_in(node, base_url)
            txt, _ = text_inline(node)
            m = RE_MONDAI.search(txt)
            if m:
                cur_mondai = int(m.group(1).translate(FW_DIGITS))
            elif cur_mondai is not None:
                cur_mondai += 1  # blank heading (seen for 問題7): assume the next 問題
                drops["(info) blank 問題 heading -> assumed previous+1"] += 1
            else:
                cur_mondai = None
            if "読解" in txt:
                cur_hint = "dokkai"
            elif "文法" in txt:
                cur_hint = "bunpo"
            cur_audio = audio
            passage = passage_id = passage_img = None
            pending = None
            orphans = []
        elif "question_content" in cls:
            _, passage_img = media_in(node, base_url)
            passage, _ = text_block(node)
            passage_counter += 1
            passage_id = f"{SOURCE}:N3-{exam_no}-{part}-p{passage_counter}"
            if not passage:
                passage = None
            elif orphans:  # passage printed after its questions (seen in 問題7 pages)
                for r in orphans:
                    r["passage"], r["passage_id"] = passage, passage_id
                    r["image"] = r["image"] or passage_img
                drops["(info) passage back-filled to preceding questions"] += len(orphans)
                orphans = []
        elif "question_list" in cls:
            if orphans and not RE_STEM_ID.match(node.get_text().strip()) and len(node.get_text().strip()) > 80:
                # some pages (問題7) dump the reading material into a trailing question_list block
                _, passage_img = media_in(node, base_url)
                passage, _ = text_block(node)
                passage_counter += 1
                passage_id = f"{SOURCE}:N3-{exam_no}-{part}-p{passage_counter}"
                for r in orphans:
                    r["passage"], r["passage_id"] = passage, passage_id
                    r["image"] = r["image"] or passage_img
                drops["(info) passage back-filled to preceding questions"] += len(orphans)
                orphans = []
                pending = None
                continue
            q_audio, q_img = media_in(node, base_url)
            stem, ruby = text_inline(node)
            m = RE_STEM_ID.match(stem)
            n = int((m.group(1) or m.group(2)).translate(FW_DIGITS)) if m else None
            pending = {"stem": stem, "image": q_img, "audio": q_audio or cur_audio, "n": n, "ruby": ruby}
        elif "answer_2row" in cls or "answer_1row" in cls:
            if pending is None:
                drops["options without question"] += 1
                continue
            q, pending = pending, None
            opts, n, ruby = [], q["n"], q["ruby"]
            for a in node.select("div.answers"):
                mid = re.match(r"^QS(\d+)(\d)$", a.get("id", ""))
                if mid:
                    n = int(mid.group(1))  # page-global number; stem numbers restart per 問題 in listening
                t, r = text_inline(a)
                ruby = ruby or r
                opts.append(RE_OPT_PREFIX.sub("", t).strip(" \u3000"))
            if n is None:
                drops["cannot determine question number"] += 1
                continue
            as_div = hidden["AS"].get(n)
            if as_div is None or not as_div.get_text().strip().isdigit():
                drops["no answer key"] += 1
                continue
            answer = int(as_div.get_text().strip()) - 1
            code = hidden["type"].get(n)
            section = SECTION_BY_CODE.get(code.get_text().strip()) if code is not None else None
            if section is None:
                section = cur_hint if part != 3 else ("bunpo" if (cur_mondai or 0) <= 3 else "dokkai")
            explanation = transcript = None
            gt = hidden["GT"].get(n)
            if gt is not None:
                gt_txt, _ = text_block(gt)
                gt_txt = re.sub(r"^Tham khảo\s*[:：]\s*", "", gt_txt).strip() or None
                if gt_txt:
                    if section == "choukai":
                        transcript = gt_txt
                    else:
                        explanation = gt_txt
            # listening 問題3/5: options are not printed on the paper; recover from transcript if listed there
            if section == "choukai" and opts and all(o == "" for o in opts):
                recovered = []
                if transcript:
                    for line in transcript.split("\n"):
                        mm = RE_TRANSCRIPT_OPT.match(line)
                        if mm:
                            recovered.append((int(mm.group(1).translate(FW_DIGITS)), mm.group(2)))
                keys = [k for k, _ in recovered]
                if recovered and keys == list(range(1, len(recovered) + 1)) and len(recovered) >= len(opts) - 1:
                    opts = [t for _, t in recovered]
                    drops["(info) listening options recovered from transcript"] += 1
                else:
                    opts = [str(i + 1) for i in range(len(opts))]
                    drops["(info) listening options unprinted -> numeric placeholders"] += 1
            if len(opts) < 2 or len(opts) > 4 or any(not o for o in opts):
                drops["bad options (count/empty)"] += 1
                continue
            if not (0 <= answer < len(opts)):
                drops["answer index out of range"] += 1
                continue
            stem = q["stem"] if section == "choukai" else RE_STEM_NUM.sub("", q["stem"]).strip()
            if section == "choukai" and not stem:
                stem = f"{n}番"
            if not stem:
                drops["empty stem"] += 1
                continue
            if section == "choukai" and not q["audio"]:
                drops["listening question without audio"] += 1
                continue
            mondai = cur_mondai
            if section == "bunpo":
                if "★" in stem:
                    mondai = 2
                elif re.fullmatch(r"【\s*[0-9０-９]+\s*】", stem):
                    mondai = 3
                elif mondai == 2 or mondai == 3:
                    mondai = 1 if ("（" in stem or "(" in stem) else mondai
                if mondai != cur_mondai:
                    drops["(info) bunpo mondai corrected from question content"] += 1
            qtype = "listening" if section == "choukai" else TYPE_MAP.get((section, mondai), FALLBACK_TYPE[section])
            has_passage = bool(passage) and section in ("bunpo", "dokkai")
            rec = {
                "id": f"{SOURCE}:N3-{exam_no}-{part}-q{n}",
                "source": SOURCE,
                "source_url": page_url,
                "exam": exam_name,
                "section": section,
                "mondai": mondai,
                "type": qtype,
                "passage": passage if has_passage else None,
                "passage_id": passage_id if has_passage else None,
                "question": stem,
                "options": opts,
                "answer": answer,
                "explanation": explanation,
                "audio": q["audio"] if section == "choukai" else None,
                "image": q["image"] or (passage_img if qtype in PASSAGE_TYPES else None),
                "transcript": transcript,
                "furigana": bool(ruby),
            }
            results.append(rec)
            if qtype in PASSAGE_TYPES and not has_passage:
                orphans.append(rec)
    kept = []
    for r in results:
        if r["type"] in PASSAGE_TYPES and not r["passage"]:
            drops["passage-type question without passage on page"] += 1
            continue
        kept.append(r)
    return kept


# ---------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    index_html = fetch(INDEX_URL, "index.html")
    exams = sorted({int(m) for m in re.findall(r"/jlpt/N3/(\d+)/\d\b", index_html)})
    print(f"index lists {len(exams)} N3 exams: {exams}")

    drops = Counter()
    all_q = []
    seen_ids = set()
    per_part_missing = []
    for exam_no in exams:
        for part in PARTS:
            url = f"{BASE}jlpt/N3/{exam_no}/{part}"
            html = fetch(url, f"N3_{exam_no}_{part}.html")
            if 'class="question_list"' not in html:
                per_part_missing.append(f"{exam_no}/{part}")
                continue
            qs = parse_part(html, exam_no, part, url, drops)
            for q in qs:
                if q["id"] in seen_ids:
                    drops["duplicate id"] += 1
                    continue
                seen_ids.add(q["id"])
                all_q.append(q)
            print(f"  exam {exam_no:>2} part {part}: {len(qs)} questions")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_q, f, ensure_ascii=False, indent=1)

    # summary
    print("\n=== SUMMARY ===")
    print(f"total questions: {len(all_q)}  -> {OUT_PATH}")
    print(f"exams: {len({q['exam'] for q in all_q})}")
    by_sec = Counter(q["section"] for q in all_q)
    by_type = Counter((q["section"], q["type"]) for q in all_q)
    for s in ("moji", "bunpo", "dokkai", "choukai"):
        print(f"  {s:8s} {by_sec[s]:4d}")
        for (ss, t), c in sorted(by_type.items()):
            if ss == s:
                print(f"      {t:16s} {c}")
    print(f"with explanation: {sum(1 for q in all_q if q['explanation'])}")
    print(f"with transcript:  {sum(1 for q in all_q if q['transcript'])}")
    print(f"with audio:       {sum(1 for q in all_q if q['audio'])}")
    n_pass = len({q['passage_id'] for q in all_q if q['passage_id']})
    print(f"with passage:     {sum(1 for q in all_q if q['passage'])}  (distinct passages: {n_pass})")
    print(f"with image:       {sum(1 for q in all_q if q['image'])}")
    if per_part_missing:
        print(f"part pages without questions (skipped): {per_part_missing}")
    print("dropped / notes:")
    for k, v in drops.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
