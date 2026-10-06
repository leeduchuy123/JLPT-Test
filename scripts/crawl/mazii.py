"""Crawler: Mazii learning-hub JLPT N3 mock exams -> crawl/raw/mazii.json

Source page : https://mazii.net/vi-VN/learning-hub/exam
Data API    : https://v2.migii.net/mazii/exam?level=3            (list of tests)
              https://v2.migii.net/mazii/exam/<id>?language=vn    (full test, unauthenticated, plain JSON)
Discovered from Mazii's Angular bundle (chunk-VIMNI2JQ.js, getListTestJLPT / getTestById / formatDataJLPT).

Access policy
-------------
The Mazii UI marks only the first 3 tests of each level as `open` (formatDataTest: open = index <= 3);
the remaining tests show as "locked" and call userService.requiredPremium(). The API itself does not
check that, but we honour the paywall and only crawl the free tests (FREE_TESTS_PER_LEVEL).

Run:  cd D:/JLPT-app && python -I scripts/crawl/mazii.py
"""
import hashlib
import html as htmlmod
import json
import os
import re
import site
import sys
import time
from collections import Counter

# `python -I` ignores the user site-packages where requests/bs4 live on this machine.
sys.path.append(site.getusersitepackages())
sys.stdout.reconfigure(encoding="utf-8")

import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

SOURCE = "mazii"
LEVEL = 3
FREE_TESTS_PER_LEVEL = 3  # mirrors the UI's `open: index <= 3`; the rest are Premium-only
ROOT = r"D:/JLPT-app"
CACHE = os.path.join(ROOT, "crawl", "cache", SOURCE)
OUT = os.path.join(ROOT, "crawl", "raw", f"{SOURCE}.json")
API = "https://v2.migii.net/mazii/exam"
PAGE = "https://mazii.net/vi-VN/learning-hub/exam"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JLPT-study-bot/0.1 (personal study tool; contact: see repo)"
SLEEP = 1.0

os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})


class StopCrawl(Exception):
    pass


def fetch_json(url: str, cache_name: str) -> dict:
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    r = session.get(url, timeout=60)
    if r.status_code in (401, 403, 429):
        raise StopCrawl(f"HTTP {r.status_code} for {url} - stopping (auth/rate-limit pattern)")
    r.raise_for_status()
    data = r.json()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    time.sleep(SLEEP)
    return data


# ----------------------------------------------------------------------------- kind mapping
# Mazii/Migii use Vietnamese "kind" labels. (section, mondai, type)
KIND_MAP = {
    "cách đọc kanji": ("moji", 1, "kanji_reading"),
    "cách viết từ": ("moji", 2, "orthography"),
    "hình thành từ": ("moji", 3, "vocab_meaning"),  # 語形成 - N2/N1 only, not expected for N3
    "điền từ theo văn cảnh": ("moji", 3, "context"),
    "thay đổi cách nói": ("moji", 4, "paraphrase"),
    "ứng dụng từ": ("moji", 5, "usage"),
    "lựa chọn ngữ pháp": ("bunpo", 1, "grammar_form"),
    "lắp ghép câu": ("bunpo", 2, "sentence_order"),
    "ngữ pháp theo đoạn văn": ("bunpo", 3, "text_grammar"),
    "đoạn văn ngắn": ("dokkai", 4, "reading_short"),
    "đoạn văn vừa": ("dokkai", 5, "reading_mid"),
    "đoạn văn dài": ("dokkai", 6, "reading_long"),
    "đọc hiểu tổng hợp": ("dokkai", None, "reading_long"),  # 統合理解 - N2/N1
    "đọc hiểu chủ đề": ("dokkai", None, "reading_long"),  # 主張理解 - N2/N1
    "tìm thông tin": ("dokkai", 7, "info_retrieval"),
    "nghe hiểu chủ đề": ("choukai", 1, "listening"),  # 課題理解
    "nghe hiểu điểm chính": ("choukai", 2, "listening"),  # ポイント理解
    "nghe hiểu khái quát": ("choukai", 3, "listening"),  # 概要理解
    "nghe hiểu diễn đạt": ("choukai", 4, "listening"),  # 発話表現
    "trả lời nhanh": ("choukai", 5, "listening"),  # 即時応答
    "nghe hiểu tổng hợp": ("choukai", None, "listening"),  # 統合理解 - N2/N1
}

# ----------------------------------------------------------------------------- html cleaning
_STRAY_LT = re.compile(r"<(?![a-zA-Z/!])")
_WS = re.compile(r"[ \t\u3000]*\n[ \t\u3000]*")
_MULTI_NL = re.compile(r"\n{3,}")
_SPACES = re.compile(r"[ \t]{2,}")
_LEADING_NUM = re.compile(r"^\s*(?:[1-4１-４][.．、)）]|\([1-4１-４]\)|（[1-4１-４]）)\s*")


def clean_html(raw: str | None, mark_underline: bool = False) -> tuple[str, bool]:
    """HTML -> plain text. Returns (text, had_furigana)."""
    if not raw:
        return "", False
    raw = _STRAY_LT.sub("&lt;", raw)
    soup = BeautifulSoup(raw, "lxml")
    had_ruby = bool(soup.find(["rt", "rp"]))
    for t in soup.find_all(["rt", "rp"]):
        t.decompose()
    for t in soup.find_all(["script", "style"]):
        t.decompose()
    if mark_underline:
        for t in soup.find_all("u"):
            t.insert_before("「")
            t.insert_after("」")
        for t in soup.find_all(style=re.compile(r"text-decoration:\s*underline")):
            t.insert_before("「")
            t.insert_after("」")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        tr.replace_with(" | ".join(x for x in cells if x) + "\n")
    for t in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "table", "ul", "ol"]):
        t.insert_before("\n")
        t.insert_after("\n")
    text = soup.get_text()
    text = htmlmod.unescape(text).replace("\xa0", " ").replace("\r", "")
    text = _WS.sub("\n", text)
    text = _MULTI_NL.sub("\n\n", text)
    text = _SPACES.sub(" ", text)
    return text.strip(), had_ruby


def to_https(u: str | None) -> str | None:
    if not u:
        return None
    u = u.strip()
    if u.startswith("http://"):
        u = "https://" + u[7:]
    return u or None


def clean_option(raw: str) -> tuple[str, bool]:
    text, ruby = clean_html(raw)
    text = _LEADING_NUM.sub("", text).strip()
    return text, ruby


def first_nonempty(*vals):
    for v in vals:
        if v:
            return v
    return None


_SEP_LINE = re.compile(r"^\s*[-－—_=]{5,}\s*$", re.M)
_NUMBERED_LINE = re.compile(r"^\s*[1-4１-４][.．。、)）]")
_JP = re.compile(r"[぀-ヿ一-鿿]")


def pick_transcript(candidates, options) -> tuple[str | None, str | None]:
    """Longest Japanese candidate; split off trailing Vietnamese commentary after a ----- line.
    Returns (transcript, extra_vietnamese). A candidate that is only the numbered option list is ignored."""
    best = ""
    for c in candidates:
        t, _ = clean_html(c)
        if not t or not _JP.search(t):
            continue
        lines = [ln for ln in t.split("\n") if ln.strip()]
        if lines and all(_NUMBERED_LINE.match(ln) for ln in lines):
            continue  # just "１．... ２．..." = the options, not a script
        if len(t) > len(best):
            best = t
    if not best:
        return None, None
    m = _SEP_LINE.search(best)
    if m:
        return best[:m.start()].strip() or None, best[m.end():].strip() or None
    return best, None


def pick_explanation(vn_candidates, other_candidates) -> str | None:
    best = ""
    for c in vn_candidates:
        t, _ = clean_html(c)
        if len(t) > len(best):
            best = t
    if best:
        return best
    for c in other_candidates:
        t, _ = clean_html(c)
        if t:
            return t
    return None


# ----------------------------------------------------------------------------- parsing
def parse_test(test: dict, test_index: int, dropped: Counter) -> list[dict]:
    exam_id = test["id"]
    exam_name = f"Mazii JLPT N3 {test.get('title') or 'Test ' + str(test_index)}"
    source_url = f"{PAGE}/do/jlpt/{exam_id}"
    out = []
    for part in test.get("parts", []):
        is_listening_part = "聴解" in (part.get("name") or "")
        for block in part.get("content", []):
            kind = (block.get("kind") or "").strip()
            if kind not in KIND_MAP:
                dropped[f"unknown kind: {kind}"] += len(block.get("Questions", []))
                continue
            section, mondai, qtype = KIND_MAP[kind]
            for q in block.get("Questions", []):
                if q.get("level") not in (None, LEVEL):
                    dropped[f"level != {LEVEL}"] += len(q.get("content", []))
                    continue
                general = q.get("general") or {}
                passage, p_ruby = clean_html(general.get("txt_read"))
                audio = to_https(general.get("audio"))
                g_image = to_https(general.get("image"))
                vn_passage, _ = clean_html(general.get("text_read_vn"))
                subs = q.get("content") or []
                key_answers = q.get("correct_answers") or []
                multi = len(subs) > 1
                passage_id = f"{SOURCE}:{q['id']}" if (passage or audio or multi) else None
                for si, sub in enumerate(subs):
                    options, o_ruby = [], False
                    for a in sub.get("answers") or []:
                        t, r = clean_option(str(a))
                        options.append(t)
                        o_ruby |= r
                    ans = sub.get("correctAnswer")
                    if ans is None and si < len(key_answers):
                        ans = key_answers[si]
                    if not isinstance(ans, int) or ans is True or ans is False:
                        dropped["no answer key"] += 1
                        continue
                    if not (2 <= len(options) <= 4) or any(not o for o in options):
                        dropped["bad options (count or empty)"] += 1
                        continue
                    if not (0 <= ans < len(options)):
                        dropped["answer index out of range"] += 1
                        continue
                    if si < len(key_answers) and key_answers[si] != ans:
                        dropped["_warn answer mismatch vs correct_answers (kept sub.correctAnswer)"] += 1

                    stem, s_ruby = clean_html(sub.get("question"), mark_underline=True)
                    explain_all = sub.get("explainAll") or {}
                    if section == "choukai":
                        # Listening: the Japanese script lives in one of explain / explain_vn / explain_en /
                        # explainAll.*, sometimes followed by a "-----" separator and Vietnamese commentary;
                        # general.text_read_vn holds the Vietnamese translation of the script.
                        transcript, extra_vn = pick_transcript(
                            [sub.get("explain"), sub.get("explain_vn"), sub.get("explain_en"),
                             explain_all.get("vn"), explain_all.get("en")], options)
                        explanation = "\n\n".join(x for x in (vn_passage, extra_vn) if x) or None
                        passage_text = None
                    else:
                        transcript = None
                        explanation = pick_explanation(
                            [explain_all.get("vn"), sub.get("explain_vn"), explain_all.get("vn_auto")],
                            [sub.get("explain"), explain_all.get("en"), sub.get("explain_en")])
                        passage_text = passage or None
                    image = to_https(sub.get("image")) or g_image
                    out.append({
                        "id": f"{SOURCE}:{exam_id}-{q['id']}-{si}",
                        "source": SOURCE,
                        "source_url": source_url,
                        "exam": exam_name,
                        "section": section,
                        "mondai": mondai,
                        "type": qtype,
                        "passage": passage_text,
                        "passage_id": passage_id,
                        "question": stem,
                        "options": options,
                        "answer": ans,
                        "explanation": explanation,
                        "audio": audio if section == "choukai" else None,
                        "image": image,
                        "transcript": transcript or None,
                        "furigana": bool(s_ruby or o_ruby or p_ruby),
                    })
    return out


def main() -> None:
    dropped: Counter = Counter()
    questions: list[dict] = []
    try:
        listing = fetch_json(f"{API}?level={LEVEL}", f"list_n{LEVEL}.json")
        tests = listing.get("data") or []
        print(f"N{LEVEL}: {len(tests)} tests listed; crawling the {FREE_TESTS_PER_LEVEL} free ones "
              f"(others are Premium-locked in the Mazii UI)")
        for idx, t in enumerate(tests, start=1):
            if idx > FREE_TESTS_PER_LEVEL:
                dropped["test skipped: Premium-locked in UI"] += 1
                continue
            detail = fetch_json(f"{API}/{t['id']}?language=vn", f"exam_{t['id']}_vn.json")
            data = detail.get("data")
            if not data:
                dropped["test without data"] += 1
                continue
            qs = parse_test(data, idx, dropped)
            print(f"  test {t['id']} ({t.get('title')}): {len(qs)} questions")
            questions.extend(qs)
    except StopCrawl as e:
        print("STOP:", e)

    # dedupe by id (defensive)
    seen = set()
    uniq = []
    for q in questions:
        if q["id"] in seen:
            dropped["duplicate id"] += 1
            continue
        seen.add(q["id"])
        uniq.append(q)
    questions = uniq

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)

    # ------------------------------------------------------------------ summary
    print(f"\nWrote {len(questions)} questions -> {OUT}")
    by_section = Counter(q["section"] for q in questions)
    by_type = Counter((q["section"], q["mondai"], q["type"]) for q in questions)
    print("per section:", dict(by_section))
    for k, v in sorted(by_type.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        print(f"  {k[0]:8s} 問題{k[1]!s:4s} {k[2]:16s} {v}")
    print("with explanation:", sum(1 for q in questions if q["explanation"]))
    print("with transcript :", sum(1 for q in questions if q["transcript"]))
    print("with audio      :", sum(1 for q in questions if q["audio"]))
    print("with image      :", sum(1 for q in questions if q["image"]))
    print("empty stem      :", sum(1 for q in questions if not q["question"]))
    print("dropped / notes :", dict(dropped))


if __name__ == "__main__":
    main()
