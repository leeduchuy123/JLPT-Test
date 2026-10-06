"""Crawler: bunpro.jp free JLPT practice tests (N3 only).

How the site works
------------------
Next.js app. The index https://bunpro.jp/jlpt_practice_tests ships a `__NEXT_DATA__` JSON with the
list of mock tests (5 per level) and their sections (vocab / grammar_reading / listening).
Each section page  https://bunpro.jp/jlpt_practice_tests/n{level}/{test_id}/{category}/{section_id}
is statically generated (__N_SSG) and its `__NEXT_DATA__.props.pageProps.section.questions` holds the
full question objects: stem, answers, `correct_answer` (1-based), per-option `reason_en`, passage
(`context`, HTML), `audio_url`, `img_url`, listening `script`, `custom_instructions`.
No login is needed (the page itself says results are "freely available without ... an account").

Note on answer order: Bunpro stores the correct option FIRST (correct_answer == 1) for every question
flagged `can_shuffle_answers` and shuffles client-side. To avoid an "answer is always A" bias we apply a
deterministic shuffle (seeded by question id) to those questions and remap the key; questions with
can_shuffle_answers == false (e.g. ①②③ listening choices) keep their original order.

Run:  cd D:/JLPT-app && python -I scripts/crawl/bunpro.py
"""
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ModuleNotFoundError:  # `python -I` skips the per-user site-packages where requests/bs4 live
    import site
    sys.path.append(site.getusersitepackages())
    import requests
    from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("D:/JLPT-app")
CACHE = ROOT / "crawl/cache/bunpro"
OUT = ROOT / "crawl/raw/bunpro.json"
BASE = "https://bunpro.jp"
SOURCE = "bunpro"
LEVEL = 3
SLEEP = 0.8
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JLPT-study-crawler/0.1 (personal study use)"}

CACHE.mkdir(parents=True, exist_ok=True)
OUT.parent.mkdir(parents=True, exist_ok=True)
_last = 0.0


def fetch(url: str, cache_name: str) -> str:
    global _last
    path = CACHE / cache_name
    if path.exists() and path.stat().st_size > 0:
        return path.read_text(encoding="utf-8")
    wait = SLEEP - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    r = requests.get(url, headers=HEADERS, timeout=60)
    _last = time.time()
    r.raise_for_status()
    path.write_text(r.text, encoding="utf-8")
    return r.text


def next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("__NEXT_DATA__ not found")
    return json.loads(m.group(1))


# ----------------------------------------------------------------------------- text cleanup
FURI_RE = re.compile(r"(?<=[\u4e00-\u9fff\u3005\u3006\u30f6々])（([\u3041-\u309f\u30fc]+)）")
MARK_RE = re.compile(r"\{\d*\{(.*?)\}\}", re.S)
KEY_RE = re.compile(r"^[A-Za-zＡ-Ｚａ-ｚ0-9０-９]{1,2}$")


def strip_furigana(s: str) -> tuple[str, bool]:
    new = FURI_RE.sub("", s)
    return new, new != s


def clean_markup(s: str) -> str:
    """Bunpro inline markup -> plain text with JLPT-style markers."""
    s = s.replace("||", "").replace("\u200b", "").replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("{{()}}", "（　）")

    def mark(m):
        inner = m.group(1).strip()
        if inner == "()" or inner == "（）":
            return "（　）"
        if KEY_RE.match(inner):  # text-grammar blank key like {{A}} / {{1}}
            return f"【{inner}】"
        return f"＿{inner}＿"

    s = MARK_RE.sub(mark, s)
    s = re.sub(r"\[x\]", " ＿★＿ ", s)
    s = re.sub(r"\[\]", " ＿＿＿ ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" ?\n ?", "\n", s)
    return s.strip()


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(["rt", "rp"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for blk in soup.find_all(["p", "div", "li", "tr", "blockquote", "h1", "h2", "h3", "h4"]):
        blk.append("\n")
    text = soup.get_text().replace("\xa0", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def clean(s: str | None, html: bool = False) -> tuple[str, bool]:
    s = s or ""
    if html:
        s = html_to_text(s)
    s = clean_markup(s)
    s, furi = strip_furigana(s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s, furi


# ----------------------------------------------------------------------------- classification
VOCAB = {  # Bunpro's names for 問題3/問題5 are swapped relative to JLPT; checked against the stem markup below
    "kanji_reading": ("moji", 1, "kanji_reading"),
    "orthography": ("moji", 2, "orthography"),
    "usage": ("moji", 3, "context"),
    "paraphrase": ("moji", 4, "paraphrase"),
    "context_defined_expressions": ("moji", 5, "usage"),
}
GRAMMAR_READING = {
    "sentential_grammar_1": ("bunpo", 1, "grammar_form"),
    "sentential_grammar_2": ("bunpo", 2, "sentence_order"),
    "text_grammar": ("bunpo", 3, "text_grammar"),
    "comprehension_short": ("dokkai", 4, "reading_short"),
    "comprehension_mid": ("dokkai", 5, "reading_mid"),
    "comprehension_long": ("dokkai", 6, "reading_long"),
    "information_retrieval": ("dokkai", 7, "info_retrieval"),
}
LISTENING = {
    "task_based_comprehension": 1,
    "point_comprehension": 2,
    "outline_comprehension": 3,
    "utterance": 4,
    "quick_response": 5,
}

dropped = Counter()
drop_examples = {}


def drop(reason, info=""):
    dropped[reason] += 1
    drop_examples.setdefault(reason, info)


def classify(q: dict, category: str):
    qt = q.get("question_type") or ""
    if category == "vocab":
        if qt in VOCAB:
            section, mondai, typ = VOCAB[qt]
            raw = q.get("question") or ""
            if "{{()}}" in raw:
                mondai, typ = 3, "context"
            elif qt in ("usage", "context_defined_expressions") and "{{" not in raw and "（　）" not in raw:
                mondai, typ = 5, "usage"
            return section, mondai, typ
        return "moji", None, "vocab_meaning"
    if category == "grammar_reading":
        if qt in GRAMMAR_READING:
            return GRAMMAR_READING[qt]
        return "bunpo", None, "grammar_misc"
    if category == "listening":
        return "choukai", LISTENING.get(qt), "listening"
    return None, None, None


def convert(q: dict, test: dict, section: dict, url: str) -> dict | None:
    sec_name, mondai, typ = classify(q, section["category"])
    if sec_name is None:
        drop("unknown section category", f"{q.get('id')} {section['category']}")
        return None
    qid = q.get("id")
    answers = q.get("answers") or []
    ca = q.get("correct_answer")
    if not isinstance(ca, int) or not (1 <= ca <= len(answers)):
        drop("no/invalid correct_answer", f"{qid} correct_answer={ca!r}")
        return None
    if not (2 <= len(answers) <= 4):
        drop("option count not 2-4", f"{qid} n={len(answers)}")
        return None

    order = list(range(len(answers)))
    if q.get("can_shuffle_answers"):
        random.Random(f"{SOURCE}:{qid}").shuffle(order)
    options, furi_o = [], False
    for i in order:
        t, f = clean(answers[i])
        options.append(re.sub(r"\s+", " ", t).strip())
        furi_o = furi_o or f
    if any(not o for o in options):
        drop("empty option text", f"{qid} {answers}")
        return None
    answer = order.index(ca - 1)
    # reason_en alignment varies in Bunpro's data: len == n answers -> aligned with answers (correct slot "");
    # len == n-1 -> reasons for the wrong options only, in answer order; anything else -> cannot map per option.
    raw_reasons = [(r or "").replace("\r\n", "\n").strip() for r in (q.get("reason_en") or [])]
    per_option = [""] * len(answers)
    if len(raw_reasons) == len(answers):
        per_option = raw_reasons
    elif len(raw_reasons) == len(answers) - 1:
        wrong = [i for i in range(len(answers)) if i != ca - 1]
        for i, r in zip(wrong, raw_reasons):
            per_option[i] = r
    if any(per_option):
        expl_lines = [f"{pos + 1}. {options[pos]} — {per_option[i]}" for pos, i in enumerate(order) if per_option[i]]
        explanation = "\n".join(expl_lines)
    else:
        explanation = "\n".join(r for r in raw_reasons if r) or None

    question, furi_q = clean(q.get("question"))
    if typ == "text_grammar" and re.fullmatch(r"【[^】]+】", question):
        question = f"{question}に入れるのに最もよいものはどれか。"
    if not question:
        drop("empty question stem", str(qid))
        return None

    custom, _ = clean(q.get("custom_instructions"), html=True)
    context, furi_p = clean(q.get("context"), html=True)
    passage = "\n\n".join(x for x in (custom, context) if x) or None
    passage_id = f"{SOURCE}:p{hashlib.sha1(passage.encode('utf-8')).hexdigest()[:10]}" if passage else None

    audio = (q.get("audio_url") or "").strip() or None
    image = (q.get("img_url") or "").strip() or None
    transcript, _ = clean(q.get("script"))
    transcript = transcript or None
    if sec_name == "choukai" and not audio:
        drop("listening without audio", str(qid))
        return None

    return {
        "id": f"{SOURCE}:{qid}",
        "source": SOURCE,
        "source_url": url,
        "exam": f"Bunpro {test['title']}",
        "section": sec_name,
        "mondai": mondai,
        "type": typ,
        "passage": passage,
        "passage_id": passage_id,
        "question": question,
        "options": options,
        "answer": answer,
        "explanation": explanation,
        "audio": audio,
        "image": image,
        "transcript": transcript,
        "furigana": bool(furi_q or furi_o or furi_p),
    }


def main():
    print("robots.txt: bunpro.jp has no Disallow rules (sitemap only)")
    index = next_data(fetch(f"{BASE}/jlpt_practice_tests", "index.html"))
    tests = [t for t in index["props"]["pageProps"]["tests"] if t.get("level") == LEVEL and t.get("is_published", True)]
    print(f"N3 tests: {[(t['id'], t['title']) for t in tests]}")

    out = []
    for test in tests:
        for sec in sorted(test["mock_sections"], key=lambda s: s["position"]):
            url = f"{BASE}/jlpt_practice_tests/n{LEVEL}/{test['id']}/{sec['category']}/{sec['id']}"
            html = fetch(url, f"n{LEVEL}_{test['id']}_{sec['category']}_{sec['id']}.html")
            data = next_data(html)
            section = data["props"]["pageProps"]["section"]
            qs = sorted(section.get("questions") or [], key=lambda q: q.get("position", 0))
            n0 = len(out)
            for q in qs:
                rec = convert(q, test, section, url)
                if rec:
                    out.append(rec)
            print(f"  {test['title']} / {sec['category']:<16} {len(qs):>3} questions -> {len(out) - n0:>3} kept")

    seen, unique = set(), []
    for q in out:
        key = hashlib.sha1("|".join([q["question"], *sorted(q["options"]), q["audio"] or "", q["passage"] or "",
                                      q["transcript"] or ""]).encode("utf-8")).hexdigest()
        if key in seen:
            drop("duplicate question", q["id"])
            continue
        seen.add(key)
        unique.append(q)

    for q in unique:
        assert 2 <= len(q["options"]) <= 4 and all(q["options"]), q["id"]
        assert 0 <= q["answer"] < len(q["options"]), q["id"]
        assert q["question"] and q["section"] in ("moji", "bunpo", "dokkai", "choukai"), q["id"]

    OUT.write_text(json.dumps(unique, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT} : {len(unique)} questions")
    print("per exam:", dict(Counter(q["exam"] for q in unique)))
    print("per section:", dict(Counter(q["section"] for q in unique)))
    print("per type:", dict(Counter(q["type"] for q in unique)))
    print("answer position distribution:", dict(sorted(Counter(q["answer"] for q in unique).items())))
    print("with explanation:", sum(1 for q in unique if q["explanation"]),
          "| with transcript:", sum(1 for q in unique if q["transcript"]),
          "| with audio:", sum(1 for q in unique if q["audio"]),
          "| with image:", sum(1 for q in unique if q["image"]),
          "| with passage:", sum(1 for q in unique if q["passage"]),
          "| furigana stripped:", sum(1 for q in unique if q["furigana"]))
    print("dropped questions:", sum(dropped.values()))
    for k, v in dropped.most_common():
        print(f"  {v:>4}  {k}   e.g. {drop_examples[k]}")


if __name__ == "__main__":
    main()
