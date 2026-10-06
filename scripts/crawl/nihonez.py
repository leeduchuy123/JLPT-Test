"""Crawler: nihonez.com JLPT N3 tests  ->  crawl/raw/nihonez.json

Run from D:/JLPT-app:   python -I scripts/crawl/nihonez.py

STATUS (investigated 2026-10-06, see crawl/cache/nihonez/_*.html):
  * https://nihonez.com/jlpt-n3-test/ lists 17 N3 tests (post type `jlpt_test`), all of them
    reproductions of official past papers ("JLPT N3 Past Test - July 2024 (Real Exam)") plus the
    official practice workbooks.  Questions are a separate CPT `jlpt_question` (1722 tagged N3).
  * Every route to the question content requires a (free) login:
        <test>/?start=test[&section_id=..&subsection=..]  -> "take-test-login-required" block
        /jlpt-question/<slug>/                           -> 302 to /login/
        /feed/?post_type=jlpt_question                   -> items contain only the title
    and the correct answers + explanations are only returned by the authenticated AJAX call
    admin-ajax.php?action=submit_jlpt_test (see assets/js/take-test-script.js).
  * robots.txt only disallows /wp-admin/ (admin-ajax.php explicitly allowed).

  Anonymously this crawler therefore yields 0 questions; it still performs discovery, caches every
  page, reports every test as dropped with the reason, and writes a valid (empty) output file.

  OPTIONAL authenticated path (UNTESTED - written from the DOM selectors used in take-test-script.js):
    set env NIHONEZ_COOKIE="wordpress_logged_in_xxx=...; ..." (copy from a logged-in browser).
    The script then fetches each test's practice page, parses the question DOM and POSTs an empty
    answer sheet to submit_jlpt_test to obtain correct_answer/explaination.  NOTE this creates test
    attempts in that account's history.  Only use it if you have decided that is acceptable.
"""
import sys, site, os, re, json, time, hashlib, html as htmlmod
sys.path.append(site.getusersitepackages())           # -I hides user site-packages
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

SOURCE = "nihonez"
ROOT = "D:/JLPT-app"
CACHE = f"{ROOT}/crawl/cache/{SOURCE}"
OUT = f"{ROOT}/crawl/raw/{SOURCE}.json"
BASE = "https://nihonez.com"
INDEX = f"{BASE}/jlpt-n3-test/"
SLEEP = 0.8
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JLPT-study-crawler/0.1 (personal study app; contact via site form)"
COOKIE = os.environ.get("NIHONEZ_COOKIE", "").strip()

os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = UA
if COOKIE:
    S.headers["Cookie"] = COOKIE
_last = 0.0


def _cache_path(url, suffix=".html"):
    h = hashlib.sha1(url.encode()).hexdigest()[:12]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", url.replace(BASE, ""))[:80].strip("_")
    return f"{CACHE}/{slug}_{h}{suffix}"


def fetch(url, suffix=".html", force=False):
    """GET with on-disk cache + politeness sleep. Returns (text, final_url)."""
    global _last
    p = _cache_path(url, suffix)
    meta = p + ".meta"
    if not force and os.path.exists(p):
        final = open(meta, encoding="utf-8").read() if os.path.exists(meta) else url
        return open(p, encoding="utf-8").read(), final
    wait = SLEEP - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    r = S.get(url, timeout=40)
    _last = time.time()
    r.raise_for_status()
    open(p, "w", encoding="utf-8").write(r.text)
    open(meta, "w", encoding="utf-8").write(r.url)
    return r.text, r.url


def robots_ok(path):
    txt, _ = fetch(f"{BASE}/robots.txt", ".txt")
    block = False; rules = []
    for line in txt.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        k, _, v = line.partition(":")
        k = k.strip().lower(); v = v.strip()
        if k == "user-agent":
            block = (v == "*")
        elif block and k in ("allow", "disallow") and v:
            rules.append((k, v))
    best = None
    for k, v in rules:
        if path.startswith(v) and (best is None or len(v) > len(best[1])):
            best = (k, v)
    return best is None or best[0] == "allow"


def clean(node_or_text):
    """HTML -> plain text. <ruby>: keep base, drop <rt>. <br> -> \\n."""
    if node_or_text is None:
        return ""
    if isinstance(node_or_text, str):
        t = node_or_text
    else:
        node = node_or_text
        for rt in node.select("rt, rp"):
            rt.decompose()
        for br in node.find_all("br"):
            br.replace_with("\n")
        for p in node.find_all(["p", "div", "li"]):
            p.insert_after("\n")
        t = node.get_text()
    t = htmlmod.unescape(t).replace("\xa0", " ")   # keep U+3000 so "\uff08\u3000\uff09" markers survive
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# ---- JLPT type mapping (nihonez `question_type` taxonomy names) ----------------------------
TYPE_MAP = {
    "kanji reading": ("moji", 1, "kanji_reading"),
    "orthography": ("moji", 2, "orthography"),
    "word formation": ("moji", 3, "context"),           # N3 has no word-formation mondai; closest bucket
    "contextually-defined expressions": ("moji", 3, "context"),
    "paraphrases": ("moji", 4, "paraphrase"),
    "usage": ("moji", 5, "usage"),
    "sentential grammar 1": ("bunpo", 1, "grammar_form"),
    "sentential grammar 2": ("bunpo", 2, "sentence_order"),
    "text grammar": ("bunpo", 3, "text_grammar"),
    "comprehension (short passages)": ("dokkai", 4, "reading_short"),
    "comprehension (mid-size passages)": ("dokkai", 5, "reading_mid"),
    "comprehension (long passages)": ("dokkai", 6, "reading_long"),
    "information retrieval": ("dokkai", 7, "info_retrieval"),
    "task-based comprehension": ("choukai", 1, "listening"),
    "comprehension of key points": ("choukai", 2, "listening"),
    "comprehension of general outline": ("choukai", 3, "listening"),
    "verbal expressions": ("choukai", 4, "listening"),
    "quick response": ("choukai", 5, "listening"),
}


def map_type(name):
    n = re.sub(r"\s+", " ", name.lower()).strip()
    n = re.sub(r"^問題\s*\S+\s*-\s*", "", n)           # "問題１ - Kanji Reading"
    for k, v in TYPE_MAP.items():
        if n.startswith(k):
            return v
    return ("bunpo", None, "grammar_misc")


# ---- discovery -----------------------------------------------------------------------------
def discover_tests():
    """Return [{url,title,premium,questions}] for every N3 test card on the listing page(s)."""
    tests = {}
    for url in (INDEX, INDEX + "?type=section", INDEX + "?type=question-type"):
        html, _ = fetch(url)
        soup = BeautifulSoup(html, "lxml")
        for card in soup.select(".test-card"):
            a = card.find("a", href=re.compile(r"/jlpt-test/"))
            if not a:
                continue
            href = urljoin(BASE, a["href"].split("?")[0].split("#")[0])
            title = clean(card.select_one(".card-title"))
            m = re.search(r"(\d+)\s*問題", card.get_text())
            tests[href] = {"url": href, "title": title,
                           "premium": "premium" in card.get("class", []),
                           "questions": int(m.group(1)) if m else None}
    # fall back / cross-check with the REST `test` taxonomy (public)
    try:
        js, _ = fetch(f"{BASE}/wp-json/wp/v2/test?per_page=100", ".json")
        for t in json.loads(js):
            if "n3" in t["slug"] and t["count"]:
                pass  # term archives are 404; permalinks only exist on the jlpt_test posts above
    except Exception as e:  # noqa
        print("  (taxonomy cross-check failed:", e, ")")
    return [tests[k] for k in sorted(tests)]


# ---- authenticated parsing (UNTESTED, selectors from take-test-script.js) ------------------
def parse_test_dom(html, test):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for qel in soup.select('[id^="question-"]'):
        qid = qel.get("id", "")[len("question-"):]
        if not qid.isdigit():
            continue
        choices = [clean(c) for c in qel.select(".answer-choice")]
        choices = [re.sub(r"^\s*[1-4１-４][.．、)]\s*", "", c) for c in choices]
        stem_el = qel.select_one(".question-text, .question-content, .question-stem") or qel
        stem = clean(stem_el)
        if stem_el is qel:
            for c in choices:
                stem = stem.replace(c, "")
        passage_el = qel.find_previous(class_=re.compile(r"passage|reading-text"))
        audio = qel.find("audio") or qel.find("source")
        img = qel.find("img")
        tname = ""
        hdr = qel.find_previous(class_=re.compile(r"mondai|section-title|question-type"))
        if hdr:
            tname = clean(hdr)
        out.append({"qid": qid, "stem": clean(stem), "options": choices,
                    "passage": clean(passage_el) if passage_el else None,
                    "audio": urljoin(BASE, (audio.get("src") or "")) if audio and audio.get("src") else None,
                    "image": urljoin(BASE, img["src"]) if img and img.get("src") else None,
                    "type_name": tname})
    return out


def fetch_answers(test_url, html, qids):
    """POST an empty answer sheet; returns {qid: result} with correct_answer (1-based)."""
    m = re.search(r'var jlptTestData = (\{.*?\});', html)
    cfg = json.loads(m.group(1)) if m else {}
    m2 = re.search(r'test_slug_in_question_post_type:\s*[\'"]([^\'"]+)', html)
    tid = re.search(r'id="test_id"[^>]*value="(\d+)"', html)
    data = {"action": "submit_jlpt_test", "security": cfg.get("nonce", ""),
            "test_id": tid.group(1) if tid else "", "answers": json.dumps({}),
            "test_slug_in_question_post_type": m2.group(1) if m2 else "", "mode": "practice",
            "time_spent": "0"}
    time.sleep(SLEEP)
    r = S.post(cfg.get("ajaxurl", f"{BASE}/wp-admin/admin-ajax.php"), data=data,
               headers={"Referer": test_url}, timeout=40)
    r.raise_for_status()
    j = r.json()
    res = j.get("data", j).get("results", j.get("data", j))
    return {str(k): v for k, v in res.items()} if isinstance(res, dict) else {}


# ---- main ----------------------------------------------------------------------------------
def main():
    questions, dropped = [], {}
    if not robots_ok("/jlpt-n3-test/"):
        print("robots.txt disallows the listing; aborting.")
        json.dump([], open(OUT, "w", encoding="utf-8"))
        return
    tests = discover_tests()
    print(f"discovered {len(tests)} N3 tests on {INDEX}")
    for t in tests:
        print(f"- {t['title']}  ({t['questions']} q, premium={t['premium']})")
        html, final = fetch(t["url"] + "?start=test")
        if "/login/" in final or "take-test-login-required" in html or "login-required" in html:
            dropped[f"login required: {t['title']}"] = t["questions"] or 0
            continue
        parsed = parse_test_dom(html, t)
        if not parsed:
            dropped[f"no question DOM found: {t['title']}"] = t["questions"] or 0
            continue
        try:
            answers = fetch_answers(t["url"], html, [p["qid"] for p in parsed])
        except Exception as e:
            dropped[f"answer request failed ({e.__class__.__name__}): {t['title']}"] = len(parsed)
            continue
        for p in parsed:
            res = answers.get(p["qid"])
            ca = None
            try:
                ca = int(res.get("correct_answer")) - 1 if res else None
            except (TypeError, ValueError):
                ca = None
            if ca is None or not (0 <= ca < len(p["options"])):
                dropped["no/invalid answer key"] = dropped.get("no/invalid answer key", 0) + 1
                continue
            if not (2 <= len(p["options"]) <= 4) or not all(p["options"]) or not p["stem"]:
                dropped["bad options/stem"] = dropped.get("bad options/stem", 0) + 1
                continue
            section, mondai, qtype = map_type(p["type_name"])
            pid = hashlib.sha1(p["passage"].encode()).hexdigest()[:10] if p["passage"] else None
            questions.append({
                "id": f"{SOURCE}:{p['qid']}", "source": SOURCE, "source_url": t["url"],
                "exam": f"nihonez {t['title']}", "section": section, "mondai": mondai, "type": qtype,
                "passage": p["passage"], "passage_id": f"{SOURCE}:{pid}" if pid else None,
                "question": p["stem"], "options": p["options"], "answer": ca,
                "explanation": clean(res.get("explaination") or res.get("explanation")) or None,
                "audio": p["audio"], "image": p["image"],
                "transcript": clean(res.get("listening_script")) or None,
                "furigana": False,
            })
    json.dump(questions, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # summary
    by = {}
    for q in questions:
        by[(q["section"], q["type"])] = by.get((q["section"], q["type"]), 0) + 1
    print(f"\nwrote {OUT}: {len(questions)} questions")
    for k in sorted(by):
        print(f"  {k[0]:8s} {k[1]:16s} {by[k]}")
    print("  with explanation:", sum(1 for q in questions if q["explanation"]))
    print("  with passage:    ", sum(1 for q in questions if q["passage"]))
    print(f"dropped ({sum(dropped.values())} questions):")
    for k, v in dropped.items():
        print(f"  {v:4d}  {k}")
    if not COOKIE:
        print("\nNOTE: nihonez requires login for all question content; set NIHONEZ_COOKIE to try the "
              "authenticated path (see module docstring).")


if __name__ == "__main__":
    main()
