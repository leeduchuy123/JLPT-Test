"""Nihongo-Pro (nihongo-pro.com) free JLPT N3 quizzes.
Index: /free-jlpt-n3-quizzes lists ~90 quizzes grouped by ribbon (Kanji / Grammar / Vocabulary ...).
Quiz pages are server-rendered; the correct choice carries class `quiz_answer_choice_correct`."""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _extra_common import Fetcher, BeautifulSoup, clean, finish, flatten_ruby, make_q, mark_underline  # noqa: E402

SLUG = "nihongopro"
BASE = "https://www.nihongo-pro.com"
fetch = Fetcher(SLUG)
questions, dropped = [], Counter()


def classify(group, stem, opts):
    g = group.lower()
    kana_only = all(re.fullmatch(r"[ぁ-ゖァ-ヺー゛゜・\s]+", o) for o in opts)
    has_target = "＿" in stem
    # usage (用法): short word as stem, options are full sentences containing the word
    if len(stem) <= 8 and not re.search(r"[。、（）\(\)]", stem) and sum("＿" in o for o in opts) >= 3:
        return "moji", "usage", 5
    if "kanji" in g:
        if has_target and kana_only:
            return "moji", "kanji_reading", 1
        if has_target and not kana_only:
            return "moji", "orthography", 2
        return "moji", "kanji_meaning", None
    if "grammar" in g:
        return "bunpo", "grammar_form", 1
    if "vocab" in g:
        if "（" in stem or "(" in stem or "＿＿" in stem:
            return "moji", "context", 3
        return "moji", "vocab_meaning", None
    if "listening" in g:
        return "choukai", "listening", None
    if "reading" in g:
        return "dokkai", "reading_short", 4
    return "moji", "vocab_meaning", None


def parse_quiz(html, url, group, title):
    soup = BeautifulSoup(html, "lxml")
    for s in soup.find_all(["script", "style"]):
        s.decompose()
    furi = flatten_ruby(soup)
    mark_underline(soup)
    audio = None
    a = soup.find("audio")
    if a:
        src = a.get("src") or (a.find("source") or {}).get("src")
        if src:
            audio = src if src.startswith("http") else BASE + src
    n = 0
    for qtr in soup.select("tr.quiz_question_tr"):
        num_el = qtr.select_one(".quiz_number")
        qnum = clean(num_el.get_text()) if num_el else str(n + 1)
        desc = qtr.select_one("[id^=questionDescription]")
        if desc is None:
            dropped["no question body"] += 1
            continue
        if desc.find("img"):
            dropped["image question"] += 1
            continue
        stem = clean(desc.get_text(""))
        stem = re.sub(r"\s+", " ", stem)
        stem = re.sub(r"[（(]\s*[）)]", "（　）", stem)
        atr = qtr.find_next_sibling("tr", class_="quiz_answer_choices_tr")
        if atr is None:
            dropped["no choices"] += 1
            continue
        opts, ans = [], None
        for i, div in enumerate(atr.select("div.quiz_answer_choice")):
            if div.find("img"):
                opts = []
                break
            opts.append(clean(div.get_text("")))
            if "quiz_answer_choice_correct" in (div.get("class") or []):
                ans = i if ans is None else -1
        if not opts:
            dropped["image options"] += 1
            continue
        if ans is None or ans < 0:
            dropped["no/multiple correct"] += 1
            continue
        section, qtype, mondai = classify(group, stem, opts)
        if qtype == "listening" and not audio:
            dropped["listening without audio"] += 1
            continue
        if section == "dokkai":
            dropped["reading question without passage"] += 1
            continue
        qid = url.rstrip("/").split("/quiz/")[1].split("/")[0]
        questions.append(make_q(SLUG, f"{qid}-{qnum}", url, section, qtype, stem, opts, ans, mondai=mondai,
                                exam=None, audio=audio, furigana=furi))
        n += 1
    return n


def main():
    idx = fetch.get(BASE + "/free-jlpt-n3-quizzes")
    if not idx:
        sys.exit("index fetch failed")
    soup = BeautifulSoup(idx, "lxml")
    items = []
    for sec in soup.select("div.quizSection"):
        h = sec.select_one("h2")
        group = clean(h.get_text()) if h else "?"
        for a in sec.select("div.link a[href^='/quiz/']"):
            items.append((group, BASE + a["href"], clean(a.get_text())))
    print(f"{len(items)} N3 quizzes listed; groups: {dict(Counter(g for g, _, _ in items))}")
    for group, url, title in items:
        html = fetch.get(url)
        if not html:
            dropped["quiz fetch failed"] += 1
            continue
        n = parse_quiz(html, url, group, title)
        print(f"  [{group}] {title[:50]}: {n}")
    finish(SLUG, questions, dropped)


if __name__ == "__main__":
    main()
