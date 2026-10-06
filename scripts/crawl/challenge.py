# -*- coding: utf-8 -*-
"""Crawler for https://challenge-jlpt.com/ ("Let's Challenge JLPT").

Findings (2026-10-06):
* ``index.php?tenant=001_sample`` is just the home page; the ``tenant`` param is
  referenced nowhere in the HTML or JS.
* Static pages (/n3-practice/, /n3-practice/{vocabulary,grammar,kanji-reading,
  kanji-choice}/, /practice.php?level=N3&type=...) contain NO questions. They
  only advertise the counts (N3: 語彙 325, 文法 241, 漢字読み 179, 漢字選択 250 = 995).
* Questions + answers + explanations are delivered exclusively by
  ``POST /api/questions.php`` with JSON {level,type,count,mode,studied,review}
  (see assets/practice.js). Response: {ok, items:[{id:"N3G0169", type, question,
  instruction, choices[], answer_index, answer_text, explanation_ja,
  correct_sentence, has_audio, ...}]}. Furigana/translation/audio come from
  other /api/*.php endpoints.
* robots.txt: ``Allow: /`` then ``Disallow: /api/``. Under RFC 9309 (longest
  match wins) the API is DISALLOWED, so by default this script does not call
  it and writes an empty array.  (Python's urllib.robotparser uses first-match
  and would wrongly say "allowed"; we implement longest-match ourselves.)

Opt-in: ``python -I scripts/crawl/challenge.py --allow-api`` ignores the robots
rule, harvests random 10-question sets per type until no new ids appear, and
also re-uses any api_N3_*.json responses already in the cache.
"""
import glob, json, re, sys, time
from pathlib import Path
try:
    import requests
except ModuleNotFoundError:  # `python -I` skips user site-packages
    import site; sys.path.append(site.getusersitepackages()); import requests

BASE = "https://challenge-jlpt.com/"
SRC = "challenge"
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "crawl" / "cache" / SRC
OUT = ROOT / "crawl" / "raw" / f"{SRC}.json"
UA = "Mozilla/5.0 (compatible; JLPT-study-crawler/1.0; personal study use)"
SLEEP = 0.8
API_PATH = "/api/questions.php"
API = BASE.rstrip("/") + API_PATH
TYPES = {
    "vocabulary": ("moji", 3, "context"),
    "grammar": ("bunpo", 1, "grammar_form"),
    "kanji_reading": ("moji", 1, "kanji_reading"),
    "kanji_choice": ("moji", 2, "orthography"),
}

session = requests.Session()
session.headers["User-Agent"] = UA


def fetch(path: str, name: str) -> str:
    p = CACHE / name
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    time.sleep(SLEEP)
    r = session.get(BASE + path, timeout=30)
    r.raise_for_status()
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return r.text


def robots_allows(robots_txt: str, path: str) -> bool:
    """RFC 9309 semantics for the '*' group: the most specific (longest) matching
    rule wins; on a tie Allow wins; no match -> allowed."""
    rules, in_star, seen_ua = [], False, False
    for line in robots_txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            if seen_ua and rules:
                in_star = False
            seen_ua = True
            if v == "*":
                in_star = True
        elif k in ("allow", "disallow") and in_star and v:
            rules.append((k, v))
            seen_ua = False
    best = None
    for k, v in rules:
        if path.startswith(v.rstrip("$")):
            if best is None or len(v) > len(best[1]) or (len(v) == len(best[1]) and k == "allow"):
                best = (k, v)
    return best is None or best[0] == "allow"


def to_question(it: dict):
    typ = it.get("type")
    if typ not in TYPES or it.get("level") != "N3":
        return None, "not_n3_or_unknown_type"
    choices = it.get("choices") or []
    ans = it.get("answer_index")
    if ans is None and it.get("answer_text") in choices:
        ans = choices.index(it["answer_text"])
    if it.get("format") == "text_input" and not choices:
        # free-text reading item: the API gives only the correct reading, no distractors -> cannot
        # make a multiple-choice question without inventing options
        return None, "text_input_no_distractors"
    if not (2 <= len(choices) <= 4) or not all(isinstance(c, str) and c.strip() for c in choices):
        return None, "bad_choices"
    if not isinstance(ans, int) or not (0 <= ans < len(choices)):
        return None, "no_answer"
    stem = str(it.get("question") or "")
    stem = re.sub(r'<span class="kanji">(.*?)</span>', r"＿\1＿", stem)   # underlined target word
    stem = re.sub(r"<[^>]+>", "", stem)
    stem = re.sub(r"[ \t\r\n]+", " ", stem).strip()   # keep full-width space inside （　）
    if not stem:
        return None, "empty_stem"
    section, mondai, qtype = TYPES[typ]
    # "kanji_choice" items are either kanji->reading or reading->kanji; classify per item
    direction = (it.get("source") or {}).get("question_direction") or ""
    instr = it.get("instruction") or ""
    if typ in ("kanji_choice", "kanji_reading"):
        if direction == "kanji_to_reading" or "読み方" in instr:
            mondai, qtype = 1, "kanji_reading"
        elif direction == "reading_to_kanji" or "漢字" in instr:
            mondai, qtype = 2, "orthography"
    return {
        "id": f"{SRC}:{it['id']}",
        "source": SRC,
        "source_url": f"{BASE}practice.php?level=N3&type={typ}",
        "exam": None,
        "section": section,
        "mondai": mondai,
        "type": qtype,
        "passage": None,
        "passage_id": None,
        "question": stem,
        "options": [c.strip() for c in choices],
        "answer": ans,
        "explanation": it.get("explanation_ja") or None,
        "audio": None,  # has_audio=true but the mp3 is only served via /api/audio.php (disallowed)
        "image": None,
        "transcript": None,
        "furigana": False,
    }, None


def harvest_via_api(questions: dict, drops: dict):
    for typ in TYPES:
        stale = 0
        for attempt in range(100):
            p = CACHE / f"api_N3_{typ}_{attempt}.json"
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
            else:
                time.sleep(SLEEP)
                r = session.post(API, json={"level": "N3", "type": typ, "count": 10, "mode": "random",
                                            "studied": [], "review": []},
                                 headers={"Accept": "application/json"}, timeout=30)
                data = r.json()
                p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            new = 0
            for it in data.get("items") or []:
                q, why = to_question(it)
                if q is None:
                    drops[why] = drops.get(why, 0) + 1
                    continue
                if q["id"] not in questions:
                    questions[q["id"]] = q
                    new += 1
            stale = stale + 1 if new == 0 else 0
            have = sum(1 for q in questions.values() if q["source_url"].endswith(typ))
            if stale >= 8 or have >= int(data.get("available_count") or 10**9):
                break


def main():
    allow_api = "--allow-api" in sys.argv
    CACHE.mkdir(parents=True, exist_ok=True)
    robots_txt = fetch("robots.txt", "robots.txt")
    api_allowed = robots_allows(robots_txt, API_PATH)

    fetch("index.php?tenant=001_sample", "index.html")
    hub = fetch("n3-practice/", "n3-practice.html")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", hub, flags=re.S)))
    counts = dict(re.findall(r"(語彙|文法|漢字読み|漢字選択) [A-Za-z ]+ (\d+)問", text))
    print("advertised N3 question counts (static hub page):", counts)
    print("question delivery: POST", API, "(found in assets/practice.js)")
    print("robots.txt allows", API_PATH, "(RFC 9309 longest-match):", api_allowed)

    questions, drops = {}, {}
    if api_allowed or allow_api:
        if not api_allowed:
            print("-> --allow-api given: overriding robots.txt Disallow: /api/ at the user's request")
        harvest_via_api(questions, drops)
    else:
        print("-> /api/ is disallowed by robots.txt; NOT fetching questions (use --allow-api to override). Output will be empty.")

    out = list(questions.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("\nSUMMARY challenge")
    print(" total:", len(out))
    print(" per section/type:", dict(Counter((q["section"], q["type"]) for q in out)))
    print(" with explanation:", sum(1 for q in out if q["explanation"]))
    print(" dropped:", drops)
    if not out:
        print(" dropped: all advertised N3 questions (995) are served only by /api/questions.php,"
              " which robots.txt disallows -> nothing crawled")


if __name__ == "__main__":
    main()
