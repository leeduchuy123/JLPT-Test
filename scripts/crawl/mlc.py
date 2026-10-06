"""MLC Japanese Language School (mlcjapanese.co.jp) – JLPT N3 kanji/grammar quizzes + lesson quizzes.
Answers come from the inline `hyoka(qnum, anum)` JS on each page (if(anum == N) -> correct)."""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _extra_common import Fetcher, BeautifulSoup, clean, finish, flatten_ruby, make_q, mark_underline  # noqa: E402

SLUG = "mlc"
BASE = "https://www.mlcjapanese.co.jp/"
fetch = Fetcher(SLUG)
questions, dropped = [], Counter()


def answer_map(html):
    """Parse the hyoka() function -> {qnum: correct anum (1-based)}."""
    m = re.search(r"function\s+hyoka\s*\(.*?\)\s*\{(.*)", html, re.S)
    if not m:
        return {}
    body = m.group(1)
    res = {}
    for q, a in re.findall(r"qnum\s*==\s*(\d+)\)\s*\{?\s*if\s*\(\s*anum\s*==\s*(\d+)\s*\)", body):
        res[int(q)] = int(a)
    return res


def parse_quiz_blocks(html, url, kind):
    """Each question is 'Q:n' / 'QUIZ:n' text followed by a <FORM> with radio inputs."""
    amap = answer_map(html)
    soup = BeautifulSoup(html, "lxml")
    for s in soup.find_all(["script", "style"]):
        s.decompose()
    furi = flatten_ruby(soup)
    for u in soup.find_all("u"):
        t = u.get_text()
        if not t.strip():
            u.replace_with("＿＿＿")
        elif t.strip() == "★":
            u.replace_with("＿★＿")
    mark_underline(soup)
    forms = soup.find_all("form")
    out = 0
    for form in forms:
        inputs = form.find_all("input", attrs={"type": re.compile("radio", re.I)})
        if not inputs:
            continue
        m = re.search(r"hyoka\s*\(\s*(\d+)", inputs[0].get("onclick", "")) or re.search(r"toi(\d+)", inputs[0].get("name", ""))
        if not m:
            continue
        qnum = int(m.group(1))
        # option texts: text following each radio input up to <br> / end of form
        opts = []
        for inp in inputs:
            txt = ""
            for sib in inp.next_siblings:
                if getattr(sib, "name", None) in ("br", "input"):
                    break
                txt += sib.get_text() if hasattr(sib, "get_text") else str(sib)
            txt = clean(txt)
            txt = re.sub(r"^[１-４1-4]\s*", "", txt).strip()
            opts.append(txt)
        # stem: text nodes immediately preceding the form (after previous form / image)
        stem_parts = []
        for sib in form.previous_siblings:
            if getattr(sib, "name", None) in ("form", "img", "h4", "p", "div"):
                break
            stem_parts.append(sib.get_text() if hasattr(sib, "get_text") else str(sib))
        stem = clean("".join(reversed(stem_parts)))
        stem = re.sub(r"^(?:Q|QUIZ)\s*[:：]\s*\d+\s*", "", stem).strip()
        # explanation: the "Tips" accordion div that directly follows this question's container div
        expl = None
        container = form.find_parent("div", class_="sp-html-src") or form.parent
        nxt = container.find_next_sibling(True) if container else None
        if nxt is not None and "accordion" in (nxt.get("class") or []) and nxt.find(string=re.compile("Tips")):
            body = nxt.find("div", class_="column-body") or nxt
            expl = clean(body.get_text("\n")) or None
        ans = amap.get(qnum)
        if ans is None:
            dropped["no answer key"] += 1
            continue
        if kind == "kanji":
            section, qtype, mondai = "moji", "orthography", 2
        elif "★" in stem:
            section, qtype, mondai = "bunpo", "sentence_order", 2
        else:
            section, qtype, mondai = "bunpo", "grammar_form", 1
        sid = os.path.basename(url).replace(".html", "") + f"-q{qnum}"
        questions.append(make_q(SLUG, sid, url, section, qtype, stem, opts, ans - 1, mondai=mondai,
                                explanation=expl, furigana=furi))
        out += 1
    return out




def main():
    pages = [(f"n3_jlpt_kanji_quiz_{i:02d}.html", "kanji") for i in range(1, 11)]
    pages += [(f"n3_jlpt_grammar_quiz_{i:02d}.html", "grammar") for i in range(1, 13)]
    # grammar lesson pages (each has a 2-question quiz)
    idx = fetch.get(BASE + "n3.html") or ""
    lesson = sorted(set(re.findall(r'href="(n3_\d{2,3}(?:_\d{2})?\.html)"', idx)))
    pages += [(p, "grammar") for p in lesson]
    for name, kind in pages:
        url = BASE + name
        html = fetch.get(url)
        if not html:
            dropped["page fetch failed"] += 1
            continue
        if "N3" not in html and "n3" not in name:
            continue
        n = parse_quiz_blocks(html, url, kind)
        print(f"{name}: {n} questions")
    finish(SLUG, questions, dropped)


if __name__ == "__main__":
    main()
