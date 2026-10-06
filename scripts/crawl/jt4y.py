"""Crawler: japanesetest4you.com JLPT N3 exercises  ->  crawl/raw/jt4y.json

Run from D:/JLPT-app:   python -I scripts/crawl/jt4y.py --ignore-robots

robots.txt of japanesetest4you.com ends with "User-agent: * / Disallow: /".  The user decided to
crawl anyway (public pages, personal study use), so the gate is opt-out via --ignore-robots; without
the flag the script writes an empty file and explains why.

Site layout (WordPress, studied 2026-10-06 from the cached pages in crawl/cache/jt4y/):
  /category/jlpt-n3/ (6 pages) with sub-categories jlpt-n3-{grammar,vocabulary,kanji,reading,listening}-test.
  119 posts "JLPT N3 – <Kind> Exercise NN".  Body = <div class="entry clearfix">:
    <p>N. stem<br><input name="questN" value="1"> opt1<br><input ...value="2"> opt2 ...</p>
    kanji posts:   a context <p> (target word in <span class="auto-style1">) precedes each question
    vocab posts:   <p><strong>instruction</strong></p> blocks decide the JLPT 問題 type
    reading posts: <p><strong>Reading Passage N</strong></p> + paragraphs, then its questions
    listening:     <figure class="wp-block-audio"><audio src></figure>, <p><strong>N. Question N</strong></p>, <img>
    <p><strong>Answer Key:</strong></p><p>Question 1: 3 (explanation)<br>Question 2: 1 (...)</p>
"""
import sys, site, os, re, json, time, hashlib, html as htmlmod
sys.path.append(site.getusersitepackages())           # -I hides user site-packages
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urljoin

SOURCE = "jt4y"
ROOT = "D:/JLPT-app"
CACHE = f"{ROOT}/crawl/cache/{SOURCE}"
OUT = f"{ROOT}/crawl/raw/{SOURCE}.json"
BASE = "https://japanesetest4you.com"
CATEGORIES = ["/category/jlpt-n3/"]          # sub-categories are discovered from the index
SLEEP = 1.2
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
IGNORE_ROBOTS = "--ignore-robots" in sys.argv

os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = UA
_last = 0.0


def _cache_path(url, suffix=".html"):
    h = hashlib.sha1(url.encode()).hexdigest()[:12]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", url.replace(BASE, ""))[:80].strip("_")
    return f"{CACHE}/{slug}_{h}{suffix}"


def fetch(url, suffix=".html"):
    """GET with on-disk cache + politeness sleep. Returns (text, final_url) or (None, None) on 4xx."""
    global _last
    p = _cache_path(url, suffix)
    meta = p + ".meta"
    if os.path.exists(p):
        final = open(meta, encoding="utf-8").read() if os.path.exists(meta) else url
        return open(p, encoding="utf-8").read(), final
    wait = SLEEP - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    r = S.get(url, timeout=40)
    _last = time.time()
    if r.status_code >= 400:
        return None, None
    open(p, "w", encoding="utf-8").write(r.text)
    open(meta, "w", encoding="utf-8").write(r.url)
    return r.text, r.url


def robots_disallows(path):
    """True if robots.txt (User-agent: * group) disallows `path`."""
    p = f"{CACHE}/_robots.txt"
    if os.path.exists(p):
        txt = open(p, encoding="utf-8").read()
    else:
        txt = S.get(f"{BASE}/robots.txt", timeout=30).text
        open(p, "w", encoding="utf-8").write(txt)
    star = False; rules = []
    for line in txt.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            star = (v == "*")
        elif star and k in ("allow", "disallow") and v:
            rules.append((k, v))
    best = None
    for k, v in rules:
        if path.startswith(v) and (best is None or len(v) > len(best[1])):
            best = (k, v)
    return best is not None and best[0] == "disallow"


def norm(t):
    t = htmlmod.unescape(t).replace("\xa0", " ")   # keep U+3000 so "（　）" markers survive
    t = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", t)   # stray C0/C1 controls (site has U+0081 before blanks)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def mark_targets(node):
    """<span class="auto-style1">語</span> (the underlined target word) -> 「語」 unless already quoted."""
    for sp in node.select("span.auto-style1, u, span[style*=underline]"):
        word = sp.get_text()
        prev = sp.previous_sibling
        nxt = sp.next_sibling
        already = (isinstance(prev, NavigableString) and str(prev).rstrip().endswith("「")) or \
                  (isinstance(nxt, NavigableString) and str(nxt).lstrip().startswith("」"))
        sp.replace_with(word if already else f"「{word}」")


def text_of(node):
    """Plain text of a tag: ruby readings dropped, <br> -> newline."""
    for rt in node.select("rt, rp"):
        rt.decompose()
    for br in node.find_all("br"):
        br.replace_with("\n")
    return norm(node.get_text())


JP_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
KANJI_RE = re.compile(r"[\u4e00-\u9fff]")


def kind_of(title):
    t = title.lower()
    for k in ("grammar", "vocabulary", "kanji", "reading", "listening"):
        if k in t:
            return k
    return "other"


def vocab_type(instruction, stem):
    i = instruction or ""
    if "意味" in i and "近い" in i:
        return 4, "paraphrase"
    if "使い方" in i or "用法" in i:
        return 5, "usage"
    if "読み方" in i:
        return 1, "kanji_reading"
    if "漢字" in i and ("書" in i or "表記" in i):
        return 2, "orthography"
    if "入れる" in i or "入る" in i:
        return 3, "context"
    # fall back on the stem shape
    if "「" in stem and not re.search(r"_{3,}|（\s*）|\(\s*\)", stem):
        return 4, "paraphrase"
    if re.search(r"_{3,}|（\s*）|\(\s*\)", stem):
        return 3, "context"
    return None, "vocab_meaning"


def parse_key(entry):
    """-> {n: (answer_index0, explanation or None)} from the 'Answer Key:' paragraph(s)."""
    key = {}
    start = None
    for p in entry.find_all("p"):
        if re.match(r"^\s*answer\s*key", p.get_text(), re.I):
            start = p
            break
    if start is None:
        return key
    for sib in start.find_next_siblings():
        if sib.name == "hr" or (sib.name == "p" and re.match(r"^\s*new\s*words", sib.get_text(), re.I)):
            break
        if sib.name != "p":
            continue
        for br in sib.find_all("br"):
            br.replace_with("\n")
        txt = norm(sib.get_text())
        # entries are usually one per line, but some posts run them together: "Question 1: 1 (…)Question 2: 3 (…)"
        for chunk in re.split(r"(?=(?:Question|Q)\s*\d{1,3}\s*[:.]\s*[1-4]\b)", txt, flags=re.I):
            m = re.match(r"^\s*(?:Question|Q)\s*(\d{1,3})\s*[:.]\s*([1-4])\b\s*(.*)$", chunk.strip(), re.I | re.S)
            if not m:
                continue
            expl = m.group(3).strip()
            expl = re.sub(r"^\(\s*(.*?)\s*\)\s*$", r"\1", expl, flags=re.S).strip() or None
            key.setdefault(int(m.group(1)), (int(m.group(2)) - 1, expl))
    return key


def grammar_links(entry, n_questions):
    """Grammar posts list one flashcard link per question after the key; use them as explanations."""
    links = []
    for a in entry.select('p a[href*="/flashcard/"]'):
        if "contact" in a["href"]:
            continue
        txt = a.get_text(strip=True)
        if txt and JP_RE.search(txt):
            links.append(f"Grammar point: {txt} — {a['href']}")
    return links if len(links) == n_questions else []


def split_question_p(p):
    """<p>stem<br><input> opt<br><input> opt</p> -> (n, stem, [options])"""
    inputs = p.find_all("input")
    if not inputs:
        return None
    m = re.search(r"quest(\d+)", inputs[0].get("name", ""))
    n = int(m.group(1)) if m else None
    mark_targets(p)
    for br in p.find_all("br"):
        br.replace_with("\n")
    segments, cur = [], []
    for node in p.descendants:
        if isinstance(node, Tag) and node.name == "input":
            segments.append(cur); cur = []
        elif isinstance(node, NavigableString) and not isinstance(node.parent, Tag) or isinstance(node, NavigableString):
            if node.parent.name not in ("rt", "rp", "script", "style"):
                cur.append(str(node))
    segments.append(cur)
    stem = norm("".join(segments[0]))
    opts = [norm("".join(s)) for s in segments[1:]]
    stem = re.sub(r"^\s*\d{1,3}\s*[.．、)]\s*", "", stem).strip()
    return n, stem, opts


def parse_post(url, title, html):
    soup = BeautifulSoup(html, "lxml")
    entry = soup.select_one("div.entry")
    if entry is None:
        return [], "no div.entry"
    m = re.search(r"\bpost-(\d+)\b", " ".join(soup.select_one("div.post-single")["class"]) if soup.select_one("div.post-single") else "")
    post_id = m.group(1) if m else hashlib.sha1(url.encode()).hexdigest()[:8]
    for junk in entry.select("script, style, noscript, iframe, .fb-share-button, .statcounter"):
        junk.decompose()
    key = parse_key(entry)
    if not key:
        return [], "no answer key"
    kind = kind_of(title)

    items = []
    instruction = None          # current bold instruction (vocab)
    passage_paras, passage_id, passage_no = [], None, 0
    context = None              # preceding context sentence (kanji)
    audio = image = None        # pending media (listening)
    pending_stem = None         # "<p><strong>1. Question 1</strong></p>" (listening)
    in_key = False
    for el in entry.children:
        if not isinstance(el, Tag):
            continue
        if el.name == "p" and re.match(r"^\s*answer\s*key", el.get_text(), re.I):
            in_key = True
        if in_key:
            break
        if el.name == "figure" or el.name == "div":
            a = el.find("audio")
            if a and a.get("src"):
                audio = urljoin(BASE, a["src"])
                continue
            img = el.find("img")
            if img and img.get("src") and "wp-content/uploads" not in img["src"]:   # uploads/ = ad banners
                image = urljoin(BASE, img["src"])
            continue
        if el.name != "p":
            continue
        if el.find("input"):
            parsed = split_question_p(el)
            if not parsed:
                continue
            n, stem, opts = parsed
            # newer posts split one question over two <p>: "stem<br><input1> opt1" + "<input2> opt2<br>…"
            if items and items[-1]["n"] == n and not stem:
                items[-1]["options"].extend(opts)
                continue
            img = el.find("img")
            if img and img.get("src") and "wp-content/uploads" not in img["src"]:
                image = urljoin(BASE, img["src"])
            if not stem and pending_stem:
                stem = pending_stem
            if not stem and kind == "listening":
                stem = f"Question {n}"
            if kind == "kanji" and context:
                word = stem
                single = context.count("「") == 1
                stem = context if (single and word and word in context) else f"{context}\n{word}".strip()
                if single:
                    context = None       # one target -> consumed; multi-target sentences serve several questions
            else:
                context = None
            items.append({"n": n, "stem": stem, "options": opts, "instruction": instruction,
                          "passage": "\n".join(passage_paras) if passage_paras else None,
                          "passage_id": passage_id, "audio": audio if kind == "listening" else None,
                          "image": image})
            pending_stem = audio = image = None
            continue
        # non-question paragraph
        img = el.find("img")
        if img and img.get("src") and "wp-content/uploads" not in img["src"]:
            image = urljoin(BASE, img["src"])
        strong = el.find("strong")
        txt = text_of(el)
        if not txt:
            continue
        if re.match(r"^\s*\d{1,3}\s*[.．]\s*Question\s*\d+\s*$", txt, re.I):     # listening heading (bold or not)
            pending_stem = re.sub(r"^\s*\d{1,3}\s*[.．]\s*", "", txt).strip()
            continue
        if strong and strong.get_text(strip=True) == txt.replace("\n", " ").strip():
            if re.search(r"passage|読解|文章", txt, re.I):
                passage_no += 1
                passage_paras, passage_id = [], f"{SOURCE}:{post_id}-p{passage_no}"
            else:
                instruction = txt
            continue
        if kind == "reading" and passage_id:
            passage_paras.append(txt)
        elif kind == "kanji" or (kind != "reading" and JP_RE.search(txt) and len(txt) < 400):
            mark_targets(el)
            context = text_of(el)
    expl_links = grammar_links(entry, len(items)) if kind == "grammar" else []
    out = []
    for i, it in enumerate(items):
        ans = key.get(it["n"])
        extra = expl_links[i] if expl_links else None
        out.append((it, ans, extra))
    return out, None


def classify(kind, it):
    """-> (section, mondai, type)"""
    stem = it["stem"]
    if kind == "grammar":
        if "★" in stem or "＿★＿" in stem:
            return "bunpo", 2, "sentence_order"
        return "bunpo", 1, "grammar_form"
    if kind == "kanji":
        word = stem.split("\n")[-1]
        m = re.search(r"「([^」]+)」", stem)
        target = m.group(1) if m else word
        if KANJI_RE.search(target):
            return "moji", 1, "kanji_reading"
        return "moji", 2, "orthography"
    if kind == "vocabulary":
        mondai, t = vocab_type(it["instruction"], stem)
        return "moji", mondai, t
    if kind == "reading":
        L = len(it["passage"] or "")
        if L <= 350:
            return "dokkai", 4, "reading_short"
        if L <= 900:
            return "dokkai", 5, "reading_mid"
        return "dokkai", 6, "reading_long"
    if kind == "listening":
        return "choukai", None, "listening"
    return "bunpo", None, "grammar_misc"


# ---- discovery -----------------------------------------------------------------------------
def discover_posts():
    """Walk /category/jlpt-n3/ (+ sub-categories found there) with WP /page/N/ pagination."""
    cats = list(CATEGORIES)
    seen_cats, posts = set(), {}
    while cats:
        cat = cats.pop(0)
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        page = 1
        while True:
            url = urljoin(BASE, cat if page == 1 else f"{cat}page/{page}/")
            html, _ = fetch(url)
            if html is None:
                break
            soup = BeautifulSoup(html, "lxml")
            for a in soup.select('a[href*="/category/jlpt-n3"]'):
                sub = re.sub(r"/page/\d+/?$", "/", a["href"].replace(BASE, "")).split("?")[0]
                if sub.startswith("/category/jlpt-n3") and not sub.endswith("/feed/") and sub not in seen_cats:
                    cats.append(sub)
            n = 0
            for h in soup.select("h2.title, h2.entry-title, .post h2, article h2"):
                a = h.find("a", href=True)
                if not a:
                    continue
                title = norm(h.get_text())
                if "n3" not in title.lower():
                    continue
                posts[a["href"]] = title
                n += 1
            if n == 0 or not soup.select_one('a.nextpostslink, a[rel="next"]'):
                break
            page += 1
    return posts


# ---- main ----------------------------------------------------------------------------------
def main():
    questions, dropped = [], {}

    def drop(why, k=1):
        dropped[why] = dropped.get(why, 0) + k

    if robots_disallows("/category/jlpt-n3/") and not IGNORE_ROBOTS:
        print("japanesetest4you.com/robots.txt: 'User-agent: * / Disallow: /' -> crawl not permitted.")
        print("SCHEMA.md requires honouring robots.txt; writing empty output. "
              "(Re-run with --ignore-robots only if you decide to accept that.)")
        json.dump([], open(OUT, "w", encoding="utf-8"))
        print(f"\nwrote {OUT}: 0 questions\ndropped: all (robots.txt Disallow: /)")
        return
    print("NOTE: --ignore-robots given; crawling against robots.txt per user decision.")
    posts = discover_posts()
    print(f"discovered {len(posts)} N3 posts")
    seen_ids = set()
    for url, title in sorted(posts.items(), key=lambda kv: kv[1]):
        html, _ = fetch(url)
        if html is None:
            drop("fetch failed"); continue
        items, why = parse_post(url, title, html)
        if why:
            drop(f"post skipped: {why}")
            print(f"  ! {title}: {why}")
            continue
        kind = kind_of(title)
        soup_id = re.search(r"\bpost-(\d+)\b", html)
        post_id = soup_id.group(1) if soup_id else hashlib.sha1(url.encode()).hexdigest()[:8]
        got = 0
        for it, ans, extra in items:
            if it["n"] is None:
                drop("question without number"); continue
            if ans is None:
                drop("question not in answer key"); continue
            opts = [o for o in it["options"] if o]
            if len(opts) != len(it["options"]) or not (2 <= len(opts) <= 4):
                drop("bad options (empty / count)"); continue
            if len(set(opts)) != len(opts):
                drop("duplicate options (source typo)"); continue
            if not it["stem"].strip():
                drop("empty stem"); continue
            idx, expl = ans
            if not (0 <= idx < len(opts)):
                drop("answer out of range"); continue
            if kind == "listening" and not it["audio"]:
                drop("listening question without audio"); continue
            if kind != "listening" and not JP_RE.search(it["stem"] + "".join(opts)):
                drop("no Japanese in question"); continue
            qid = f"{SOURCE}:{post_id}-{it['n']}"
            if qid in seen_ids:
                drop("duplicate id"); continue
            seen_ids.add(qid)
            section, mondai, qtype = classify(kind, it)
            explanation = "\n".join(x for x in (expl, extra) if x) or None
            questions.append({
                "id": qid, "source": SOURCE, "source_url": url, "exam": None,
                "section": section, "mondai": mondai, "type": qtype,
                "passage": it["passage"], "passage_id": it["passage_id"] if it["passage"] else None,
                "question": it["stem"], "options": opts, "answer": idx,
                "explanation": explanation, "audio": it["audio"], "image": it["image"],
                "transcript": None, "furigana": False,
            })
            got += 1
        print(f"  {title}: {got} q")
    json.dump(questions, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by = {}
    for q in questions:
        by[(q["section"], q["type"])] = by.get((q["section"], q["type"]), 0) + 1
    print(f"\nwrote {OUT}: {len(questions)} questions")
    for k in sorted(by):
        print(f"  {k[0]:8s} {k[1]:16s} {by[k]}")
    print("  with explanation:", sum(1 for q in questions if q["explanation"]))
    print("  with passage:    ", sum(1 for q in questions if q["passage"]))
    print("  with audio:      ", sum(1 for q in questions if q["audio"]))
    print("  with image:      ", sum(1 for q in questions if q["image"]))
    print(f"dropped ({sum(dropped.values())}):")
    for k, v in dropped.items():
        print(f"  {v:4d}  {k}")


if __name__ == "__main__":
    main()
