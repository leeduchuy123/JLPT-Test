"""Build crawl/raw/ref_grammar.json: JLPT N3 grammar reference.

Source: jlptsensei.com "JLPT N3 Grammar List" (5 list pages + one detail page per point:
meaning, usage table, example sentences JA/EN).  Crawled politely (0.8 s between requests)
with a disk cache.  Vietnamese meanings / first-example translations come from
scripts/ref/grammar_vi.py (hand-written).
Run from D:/JLPT-app:  python -I scripts/ref/build_grammar.py [--refetch]
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, dump, CACHE_DIR
from bs4 import BeautifulSoup

LIST = "https://jlptsensei.com/jlpt-n3-grammar-list/"
SLEEP = 0.8
SKIP_RE = re.compile(r"download|e-?book|patreon|flashcard|study guide|click the|support", re.I)


def soup(url):
    b = fetch(url, ext=".html", sleep=SLEEP)
    return BeautifulSoup(b, "lxml") if b else None


def list_points():
    pts = []
    page = 1
    while True:
        url = LIST if page == 1 else f"{LIST}page/{page}/"
        s = soup(url)
        if s is None:
            break
        rows = s.select("table tr")[1:]
        if not rows:
            break
        for tr in rows:
            tds = tr.select("td")
            if len(tds) < 4:
                continue
            a = tr.select_one("a[href]")
            pts.append({"romaji": tds[1].get_text(" ", strip=True), "pattern": tds[2].get_text(" ", strip=True),
                        "meaning_en": tds[3].get_text(" ", strip=True), "url": a["href"] if a else None})
        nxt = s.select_one(f'a.page-numbers[href$="/page/{page+1}/"]')
        if not nxt:
            break
        page += 1
    return pts


def parse_structure(s):
    tb = s.select_one("table.usage")
    if not tb:
        return None
    rows, shared, left = [], None, 0
    for tr in tb.select("tr"):
        cells = []
        for td in tr.select("td,th"):
            t = td.get_text(" ", strip=True)
            if td.get("rowspan"):
                shared, left = t, int(td["rowspan"]) - 1
            cells.append(t)
        if not any(td.get("rowspan") for td in tr.select("td,th")) and left > 0:
            cells.append(shared)
            left -= 1
        cells = [c for c in cells if c]
        if cells:
            rows.append(" + ".join(cells))
    return " / ".join(dict.fromkeys(rows)) or None


def parse_detail(url):
    s = soup(url)
    if s is None:
        return {}
    d = {}
    m = s.select_one("#meaning")
    if m:
        t = m.get_text(" ", strip=True)
        t = re.sub(r"^Meaning\s*意味\s*", "", t).strip()
        if t:
            d["meaning_en"] = t
    d["structure"] = parse_structure(s)
    # notes: paragraphs between usage table and examples section
    notes = []
    tb = s.select_one("table.usage") or s.select_one("#meaning")
    ex_sec = s.select_one("#examples")
    if tb is not None:
        for el in tb.find_all_next(["p", "h2", "h3"]):
            if ex_sec is not None and (el is ex_sec or ex_sec in el.parents or el.sourceline and ex_sec.sourceline and el.sourceline >= ex_sec.sourceline):
                break
            if el.name != "p":
                continue
            t = el.get_text(" ", strip=True)
            if not t or SKIP_RE.search(t) or t.startswith("Learn Japanese grammar"):
                continue
            notes.append(t)
    d["notes"] = " ".join(notes) or None
    exs = []
    for ec in s.select(".example-cont"):
        jp = ec.select_one("p.jp")
        en = ec.select_one('[id$="_en"] .alert')
        if not jp:
            continue
        ja = re.sub(r"\s+", "", jp.get_text("", strip=True))
        exs.append({"ja": ja, "en": en.get_text(" ", strip=True) if en else None})
    d["examples"] = exs
    return d


def crawl():
    cache = os.path.join(CACHE_DIR, "grammar_crawl.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            pts = json.load(f)
    else:
        pts = list_points()
    print("list entries:", len(pts))
    # resumable: (re)fetch detail pages for entries that still lack examples (anti-bot 202s).
    # On a fresh crawl everything is fetched; with an existing cache pass --refetch to retry the gaps.
    todo = [p for p in pts if p["url"] and not p.get("examples")]
    if os.path.exists(cache) and "--refetch" not in sys.argv:
        print(f"cache present; {len(todo)} entries lack detail pages (run with --refetch to retry them)")
        todo = []
    print("detail pages to fetch:", len(todo))
    for i, p in enumerate(todo):
        p.update({k: v for k, v in parse_detail(p["url"]).items() if v is not None})
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(todo)}")
    print("still missing examples:", sum(1 for p in pts if p["url"] and not p.get("examples")))
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(pts, f, ensure_ascii=False, indent=1)
    return pts


def main():
    pts = crawl()
    try:
        from grammar_vi import MEANING_VI, EXAMPLE_VI
    except ImportError:
        MEANING_VI, EXAMPLE_VI = {}, {}
    try:
        from grammar_fallback import FALLBACK
    except ImportError:
        FALLBACK = {}
    out, seen = [], set()
    n_vi = n_ex_vi = n_fallback = 0
    for p in pts:
        pat = p["pattern"].strip()
        if not pat or pat in seen:
            continue
        seen.add(pat)
        if not p.get("examples") and pat in FALLBACK:
            fb = FALLBACK[pat]
            p = dict(p, examples=fb["examples"], structure=p.get("structure") or fb["structure"],
                     notes=((p.get("notes") or "") + " " + fb.get("notes", "")).strip() + " (Ví dụ/cấu trúc tự soạn; trang nguồn bị chặn.)")
            n_fallback += 1
        exs = []
        for e in p.get("examples", []):
            vi = EXAMPLE_VI.get(e["ja"])
            if vi:
                n_ex_vi += 1
            exs.append({"ja": e["ja"], "vi": vi, "en": e.get("en")})
        mv = MEANING_VI.get(pat)
        if mv:
            n_vi += 1
        notes = p.get("notes")
        romaji = p.get("romaji")
        notes = f"[{romaji}] {notes}" if (romaji and notes) else (f"[{romaji}]" if romaji else notes)
        out.append({"pattern": pat, "meaning_vi": mv, "meaning_en": p.get("meaning_en"),
                    "structure": p.get("structure"), "examples": exs, "notes": notes, "level": "N3",
                    "source_url": p.get("url")})
    for o in out:
        assert o["pattern"] and o["meaning_en"], o
    print(f"patterns: {len(out)}  meaning_vi: {n_vi}  fallback-filled: {n_fallback}  examples with vi: {n_ex_vi}  "
          f"patterns with >=1 vi example: {sum(1 for o in out if any(e['vi'] for e in o['examples']))}  "
          f"no structure: {sum(1 for o in out if not o['structure'])}  no examples: {sum(1 for o in out if not o['examples'])}")
    dump("ref_grammar.json", out)


if __name__ == "__main__":
    main()
