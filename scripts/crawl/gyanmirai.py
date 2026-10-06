"""GyanMirai (gyanmirai.com) – JLPT N3 kanji / grammar / vocabulary practice tests (Nuxt SSR).
Questions, correct_answer (option text) and rich explanations are embedded in the page's
`__NUXT_DATA__` payload (devalue-flattened JSON). Mock tests are client-fetched -> not crawled.
robots.txt disallows /*.json$ so only the HTML pages are fetched."""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _extra_common import Fetcher, BeautifulSoup, clean, finish, make_q  # noqa: E402

SLUG = "gyanmirai"
BASE = "https://www.gyanmirai.com"
KINDS = {"kanji": "kanji-practice-test", "grammar": "grammar-practice-test", "vocabulary": "vocabulary-practice-test"}
fetch = Fetcher(SLUG)
questions, dropped = [], Counter()
KANA = re.compile(r"^[ぁ-ゖァ-ヺー゛゜・\s]+$")


def _isref(x):
    return isinstance(x, int) and not isinstance(x, bool)


def hydrate(flat):
    """Un-flatten a Nuxt/devalue payload (ints are references into the flat array)."""
    memo = {}

    def h(i):
        if i in memo:
            return memo[i]
        v = flat[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in ("ShallowReactive", "Reactive", "Ref", "ShallowRef", "EmptyRef"):
                r = h(v[1]) if len(v) > 1 else None
                memo[i] = r
                return r
            if v and isinstance(v[0], str) and v[0] in ("Set", "Map"):
                r = [h(x) if _isref(x) else x for x in v[1:]]
                memo[i] = r
                return r
            r = []
            memo[i] = r
            for x in v:
                r.append(h(x) if _isref(x) else x)
            return r
        if isinstance(v, dict):
            r = {}
            memo[i] = r
            for k, x in v.items():
                r[k] = h(x) if _isref(x) else x
            return r
        memo[i] = v
        return v

    return h(0)


def html_to_text(s):
    s = (s or "").replace("<br/>", "\n").replace("<br>", "\n").replace("<br />", "\n")
    soup = BeautifulSoup(s, "lxml")
    for u in soup.find_all("u"):
        u.replace_with("＿" + u.get_text() + "＿")
    return clean(soup.get_text(" "))


def explanation_text(e):
    if not e:
        return None
    if isinstance(e, str):
        return clean(e) or None
    parts = []
    if isinstance(e.get("summary"), str):
        parts.append(e["summary"])
    c = e.get("correct")
    if isinstance(c, dict):
        for k in ("body", "rule", "pattern"):
            if isinstance(c.get(k), str):
                parts.append(c[k])
        kb = c.get("kanji_breakdown")
        if isinstance(kb, list) and kb:
            parts.append("; ".join(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in kb))
    elif isinstance(c, str):
        parts.append(c)
    inc = e.get("incorrect")
    if isinstance(inc, list):
        for it in inc:
            if isinstance(it, dict) and isinstance(it.get("reason"), str):
                parts.append(f"✗ {it['reason']}")
    en = e.get("enrichment")
    if isinstance(en, dict):
        ex = en.get("example_sentence")
        if isinstance(ex, dict) and isinstance(ex.get("ja"), str):
            parts.append(f"例: {ex['ja']}" + (f" — {ex['en']}" if isinstance(ex.get("en"), str) else ""))
        if isinstance(en.get("common_confusion"), str):
            parts.append(en["common_confusion"])
    return clean("\n".join(parts)) or None


def classify(kind, stem, opts):
    kana_only = all(KANA.match(o) for o in opts)
    blank = re.search(r"（\s*＿*\s*）|＿{2,}", stem)
    target = "＿" in stem and not blank
    ascii_opts = all(re.search(r"[A-Za-z]", o) and not re.search(r"[ぁ-ヺ一-龯]", o) for o in opts)
    if kind == "kanji":
        if target and kana_only:
            return "moji", "kanji_reading", 1
        if target and not ascii_opts:
            return "moji", "orthography", 2
        return "moji", "kanji_meaning", None
    if kind == "grammar":
        if "★" in stem:
            return "bunpo", "sentence_order", 2
        return "bunpo", "grammar_form", 1
    if "読み方" in stem and kana_only:
        return "moji", "kanji_reading", 1
    if ascii_opts:
        return "moji", "vocab_meaning", None
    if target:
        return "moji", "paraphrase", 4
    if blank:
        return "moji", "context", 3
    return "moji", "vocab_meaning", None


def parse_test(html, url, kind, test_no):
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        dropped["no payload"] += 1
        return 0
    data = hydrate(json.loads(m.group(1)))
    qs = None
    for v in (data.get("data") or {}).values():
        if isinstance(v, dict) and isinstance(v.get("questions"), list):
            qs = v["questions"]
            break
    if qs is None:
        dropped["no questions in payload"] += 1
        return 0
    n = 0
    for i, q in enumerate(qs, 1):
        if not isinstance(q, dict):
            continue
        stem = html_to_text(q.get("question"))
        stem = re.sub(r"[（(]\s*[）)]", "（　）", stem)
        stem = re.sub(r"^\s*\d{1,2}\s*[)）.．]\s*", "", stem)
        opts = [clean(str(o)) for o in (q.get("options") or [])]
        ca = q.get("correct_answer")
        if ca is None:
            dropped["no answer key"] += 1
            continue
        if _isref(ca):
            ans = ca if 0 <= ca < len(opts) else None
        else:
            ca = clean(str(ca))
            idxs = [k for k, o in enumerate(opts) if o == ca]
            ans = idxs[0] if len(idxs) == 1 else None
        if ans is None:
            dropped["answer not matching options"] += 1
            continue
        section, qtype, mondai = classify(kind, stem, opts)
        questions.append(make_q(SLUG, f"{kind}-{test_no}-{i}", url, section, qtype, stem, opts, ans, mondai=mondai,
                                explanation=explanation_text(q.get("explanation"))))
        n += 1
    return n


def main():
    for kind, path in KINDS.items():
        idx = fetch.get(f"{BASE}/jlpt/jlpt-n3/{path}")
        if not idx:
            dropped["index fetch failed"] += 1
            continue
        nums = sorted({int(x) for x in re.findall(rf'href="/jlpt/jlpt-n3/{path}/(\d+)"', idx)})
        print(f"{kind}: {len(nums)} tests")
        for no in nums:
            url = f"{BASE}/jlpt/jlpt-n3/{path}/{no}"
            html = fetch.get(url)
            if not html:
                dropped["test fetch failed"] += 1
                continue
            n = parse_test(html, url, kind, no)
            print(f"  {kind} #{no}: {n}")
    finish(SLUG, questions, dropped)


if __name__ == "__main__":
    main()
