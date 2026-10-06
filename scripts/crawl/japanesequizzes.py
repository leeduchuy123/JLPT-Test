"""JapaneseQuizzes.com – JLPT N3 grammar / kanji / vocabulary practice tests (WP Pro Quiz).
Question HTML is server-rendered; correct answers are in the inline `wpProQuizInitList` JSON
(`json: {"<qid>": {"correct":[1,0,0,0]}}`)."""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _extra_common import Fetcher, BeautifulSoup, clean, finish, flatten_ruby, make_q, mark_underline  # noqa: E402

SLUG = "japanesequizzes"
BASE = "https://japanesequizzes.com"
INDEXES = {
    "grammar": "/portfolio/jlpt-n3-grammar-practice-test/",
    "kanji": "/portfolio/jlpt-n3-kanji-practice-test/",
    "vocabulary": "/portfolio/jlpt-n3-vocabulary-practice-test/",
}
fetch = Fetcher(SLUG)
questions, dropped = [], Counter()

KANA = re.compile(r"^[ぁ-ゖァ-ヺー゛゜・\s]+$")


def classify(kind, stem, opts):
    kana_only = all(KANA.match(o) for o in opts)
    blank = re.search(r"＿{2,}|（\s*＿*\s*）|\(\s*\)", stem)
    target = "＿" in stem and not blank
    if kind == "kanji":
        if target and kana_only:
            return "moji", "kanji_reading", 1
        if target:
            return "moji", "orthography", 2
        return "moji", "kanji_meaning", None
    if kind == "grammar":
        if "★" in stem:
            return "bunpo", "sentence_order", 2
        return "bunpo", "grammar_form", 1
    # vocabulary
    if target:
        return "moji", "paraphrase", 4
    if blank:
        return "moji", "context", 3
    return "moji", "vocab_meaning", None


def strip_ruby_text(t):
    """Some options contain HTML-escaped <ruby> markup as literal text."""
    t = re.sub(r"<rt>.*?</rt>|<rp>.*?</rp>", "", t)
    return re.sub(r"</?(?:ruby|rb)>", "", t).strip()


def answer_map(html):
    res = {}
    for m in re.finditer(r"json:\s*\{", html):
        start = m.end() - 1
        depth, i = 0, start
        while i < len(html):
            if html[i] == "{":
                depth += 1
            elif html[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        try:
            data = json.loads(html[start:i + 1])
        except json.JSONDecodeError:
            continue
        for qid, info in data.items():
            if isinstance(info, dict) and info.get("type") == "single" and isinstance(info.get("correct"), list):
                c = [k for k, v in enumerate(info["correct"]) if v]
                if len(c) == 1:
                    res[str(qid)] = c[0]
    return res


def parse_test(html, url, kind, test_no):
    amap = answer_map(html)
    # source HTML wraps lines inside Japanese sentences; real breaks are <br>/<p>, handled below
    soup = BeautifulSoup(re.sub(r"[ \t]*\r?\n[ \t]*", "", html), "lxml")
    for s in soup.find_all(["script", "style"]):
        s.decompose()
    furi = flatten_ruby(soup)
    mark_underline(soup)
    n = 0
    for ul in soup.select("ul.wpProQuiz_questionList"):
        qid = ul.get("data-question_id")
        if ul.get("data-type") != "single":
            dropped["non-single type"] += 1
            continue
        qdiv = ul.find_previous("div", class_="wpProQuiz_question_text")
        if qdiv is None:
            dropped["no stem"] += 1
            continue
        if qdiv.find("img"):
            dropped["image stem"] += 1
            continue
        for br in qdiv.find_all("br"):
            br.replace_with("\n")
        for ptag in qdiv.find_all("p"):
            ptag.append("\n")
        stem = strip_ruby_text(clean(qdiv.get_text("")))
        stem = re.sub(r"[（(]\s*＿+\s*[）)]", "（＿＿＿）", stem)
        stem = re.sub(r"_{2,}", "＿＿＿", stem)
        stem = re.sub(r"＿{2,}", "＿＿＿", stem)
        opts = []
        for li in ul.select("li.wpProQuiz_questionListItem"):
            lab = li.find("label")
            if lab is None or li.find("img"):
                opts = []
                break
            for inp in lab.find_all("input"):
                inp.decompose()
            opts.append(strip_ruby_text(clean(lab.get_text(""))))
        if not opts:
            dropped["bad options"] += 1
            continue
        ans = amap.get(str(qid))
        if ans is None:
            dropped["no answer key"] += 1
            continue
        if ans >= len(opts):
            dropped["answer out of range"] += 1
            continue
        section, qtype, mondai = classify(kind, stem, opts)
        questions.append(make_q(SLUG, f"{kind}-{test_no}-{qid}", url, section, qtype, stem, opts, ans,
                                mondai=mondai, furigana=furi))
        n += 1
    return n


def main():
    for kind, path in INDEXES.items():
        idx = fetch.get(BASE + path)
        if not idx:
            dropped["index fetch failed"] += 1
            continue
        pat = re.compile(rf"https://japanesequizzes\.com/portfolio/jlpt-n3-{kind}-practice-test-(\d+)/")
        tests = sorted({(int(m.group(1)), m.group(0)) for m in pat.finditer(idx)})
        print(f"{kind}: {len(tests)} test pages")
        for no, url in tests:
            html = fetch.get(url)
            if not html:
                dropped["test fetch failed"] += 1
                continue
            n = parse_test(html, url, kind, no)
            print(f"  {kind} #{no:02d}: {n}")
    finish(SLUG, questions, dropped)


if __name__ == "__main__":
    main()
