"""Crawler: jlptpracticetest.com (N3 only) -> crawl/raw/jlptpt.json

How the site works
------------------
Next.js app on Vercel (https://www.jlptpracticetest.com, the bare domain 307-redirects to www).
  * /n3                        level page, lists the dated past-exam sets (/n3/YYYYMM) and the
                               original listening practice tests (/n3/listening/<n>).
  * /n3/YYYYMM/{vocabulary,grammar}  client-rendered quiz; data comes from
    GET /api/test/n3/YYYYMM    -> {"level","date","year","month","sections":[
                                    {"type":"vocabulary"|"grammar","groups":[
                                       {"instruction","passage"?,"passageHtml"?,"questions":[
                                          {"id","questionNumber","text","textHtml","options","correctAnswer"(1-based)}]}]}]}
    Anonymous, public (Cache-Control: public) and explicitly allowed by robots.txt
    ("Disallow: /api/" but "Allow: /api/test/"). No explanations are provided for past exams
    (the "Ask Keiko" AI tutor is login-only), so explanation is null.
  * Past-exam sets contain only 文字・語彙 + 文法・読解; the site has NO past-exam 聴解.
  * /n3/listening/<n>          original (non-official, AI-voiced) listening practice tests. The full
    28-question tests are "Keiko Pro" (paid, login) and served from /api/listening/... which robots.txt
    disallows -> NOT crawled. Each page server-renders ONE free sample question (question, choices,
    answer key, script, audio + image URL) in its RSC payload; we take that sample only.
  * /jlpt-full-mock, /jlpt-mini-mock re-use the past-exam questions (sourceType historical_exam) -> skipped.

Run:  cd D:/JLPT-app && python -I -X utf8 scripts/crawl/jlptpt.py
"""
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path

try:
    import requests
except ModuleNotFoundError:  # `python -I` skips the per-user site-packages where requests/bs4 live
    import site
    sys.path.append(site.getusersitepackages())
    import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("D:/JLPT-app")
CACHE = ROOT / "crawl/cache/jlptpt"
OUT = ROOT / "crawl/raw/jlptpt.json"
BASE = "https://www.jlptpracticetest.com"
SOURCE = "jlptpt"
LEVEL = "n3"
SLEEP = 0.8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.8",
}

CACHE.mkdir(parents=True, exist_ok=True)
OUT.parent.mkdir(parents=True, exist_ok=True)

_session = requests.Session()
_session.headers.update(HEADERS)
_last_request = 0.0


def fetch(path: str, cache_name: str) -> str | None:
    """GET BASE+path, caching the raw body under crawl/cache/jlptpt/. Returns None on HTTP error."""
    global _last_request
    cpath = CACHE / cache_name
    if cpath.exists() and cpath.stat().st_size > 0:
        return cpath.read_text(encoding="utf-8")
    wait = SLEEP - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        r = _session.get(BASE + path, timeout=60)
    finally:
        _last_request = time.time()
    if r.status_code != 200:
        print(f"  HTTP {r.status_code} {path}")
        return None
    r.encoding = "utf-8"
    cpath.write_text(r.text, encoding="utf-8")
    return r.text


# ----------------------------------------------------------------------------- markup -> text
# The API uses a pseudo-markup ([[br]], [[u]]..[[/u]], [[blank]], [[b]], [[center]], [[align-right]],
# [[h3]], [[table]]/[[tr]]/[[td]]/[[th]], [[passage-break]]) mixed with some real HTML (<tbody>,
# <td rowspan=..>, <hr>, <ul><li>, <h5>) and raw "\n" that are partly real line breaks, partly
# OCR line-wraps in the middle of a sentence.
LINE_END = set("。．.！!？?」』）)】］]：:…")
LINE_START = set("（(【「『［[①②③④⑤⑥⑦⑧⑨⑩・*＊※〒◆■●○◎☆★-－―")
SPEAKER_RE = re.compile(r"^[^\s「」。、]{1,8}?\s*[「：:]")
FURI_RE = re.compile(r"([一-龯々〆ヶ])[（(]([ぁ-ゖー]{1,8})[)）]")
UNDERSCORE = "_＿"
JP_CHARS = "ぁ-ゖァ-ヺー一-龯々〆ヶ"
HIRA_KANJI = "ぁ-ゖ一-龯々〆ヶ"


def _raw_newlines(s: str) -> str:
    """Decide for every raw newline whether it is a real break (keep) or an OCR wrap (drop)."""
    out = []
    i = 0
    for m in re.finditer(r"[ \t　]*\n[ \t　\n]*", s):
        out.append(s[i:m.start()])
        before = s[:m.start()]
        after = s[m.end():]
        b = before[-1:] if before else ""
        a = after[:1] if after else ""
        if not before or not after or before.endswith("]]") or before.endswith(">") \
                or after.startswith("[[") or after.startswith("<"):
            rep = ""  # structure comes from the surrounding tags
        elif b in LINE_END or a in LINE_START or SPEAKER_RE.match(after) or re.match(r"[\(（]?注", after):
            rep = "\n"
        elif b in UNDERSCORE or a in UNDERSCORE or (b.isascii() and b.isalnum() and a.isascii() and a.isalnum()):
            rep = " "
        else:
            rep = ""
        out.append(rep)
        i = m.end()
    out.append(s[i:])
    return "".join(out)


def _clean_lines(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "").replace("\t", " ")
    lines = [re.sub(r"[ ]{2,}", " ", ln).strip(" ") for ln in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # stray spaces next to Japanese punctuation (e.g. "教室で、 自分" / "です 。")
    text = re.sub(r"(?<=[、。「『（])[ ]+", "", text)
    text = re.sub(r"[ ]+(?=[、。」』）])", "", text)
    text = re.sub(r"[ ]+(?=（　）)|(?<=（　）)[ ]+", "", text)
    # OCR split words: a single ASCII space inside Japanese text ("知らないこ とが", "多 かった").
    # Katakana|katakana is only joined for obvious splits ("ラジカ セ", "ピ ーマン") so that
    # names like "ジョーンズ エミリー" keep their space.
    text = re.sub(rf"(?<=[{HIRA_KANJI}]) (?=[{JP_CHARS}])|(?<=[{JP_CHARS}]) (?=[{HIRA_KANJI}])", "", text)
    text = re.sub(r"([ァ-ヺー]+) ([ァ-ヺー]+)",
                  lambda m: m.group(1) + m.group(2)
                  if min(len(m.group(1)), len(m.group(2))) == 1 or m.group(2)[0] in "ーァィゥェォャュョッヮ"
                  else m.group(0), text)
    # OCR artefact: the digit 1 read as "1)" -> "1) 0分" = "10分", "1) 2月1日" = "12月1日"
    text = re.sub(r"(?<![（(\d])1\)\s*(?=\d)", "1", text)
    return text


def markup_to_text(s: str) -> tuple[str, bool]:
    """Return (plain text, furigana_flattened)."""
    if not s:
        return "", False
    s = _raw_newlines(s)
    s = s.replace("[[passage-break]]", "\n\n")
    s = s.replace("[[blank]]", "（　）")
    s = s.replace("[[br]]", "\n")
    s = re.sub(r"\[\[u\]\](.*?)\[\[/u\]\]", lambda m: f"＿{m.group(1)}＿" if m.group(1).strip() else "＿＿＿", s, flags=re.S)
    s = re.sub(r"\[\[/?u\]\]", "＿", s)
    s = re.sub(r"\[\[/?b\]\]", "", s)
    # tables: one row per line, cells separated by " | "
    s = re.sub(r"\[\[(/?)(table|tr|td|th)\]\]", r"<\1\2>", s)
    s = re.sub(r"<td\b[^>]*>", "<td>", s)
    s = re.sub(r"<th\b[^>]*>", "<th>", s)
    s = re.sub(r"</?(tbody|thead)\b[^>]*>", "", s)
    s = re.sub(r"<table\b[^>]*>", "\n", s)
    s = s.replace("</table>", "\n")
    s = re.sub(r"<tr>(.*?)</tr>", lambda m: "\n" + " | ".join(
        c.strip().replace("\n", " ") for c in re.findall(r"<t[dh]>(.*?)</t[dh]>", m.group(1), flags=re.S)),
        s, flags=re.S)
    s = re.sub(r"</?t[dhr]>", " ", s)
    # block-level pseudo tags / html -> line breaks
    s = re.sub(r"\[\[/?(center|align-right|align-left|h\d)\]\]", "\n", s)
    s = re.sub(r"<li\b[^>]*>", "\n・", s)
    s = re.sub(r"</?(ul|ol|li|h\d|p|div|hr)\b[^>]*/?>", "\n", s)
    s = re.sub(r"\[\[/?[a-z0-9\-]+\]\]", "", s)  # any remaining pseudo tag
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s, n = FURI_RE.subn(r"\1", s)
    s, n2 = FURI_RE.subn(r"\1", s)  # consecutive pairs 制(せい)限(げん)
    return _clean_lines(s), bool(n or n2)


def normalize_star(stem: str) -> str:
    """Unify the sentence-composition blanks: ___ ___ _★_ ___ -> ＿＿＿ ＿＿＿ ＿★＿ ＿＿＿."""
    stem = re.sub(r"[_＿]*\s*★\s*[_＿]*", "\x00", stem)
    stem = re.sub(r"[_＿]{2,}", "\x01", stem)
    stem = re.sub(r"(?<=[\x00\x01])(?=[\x00\x01])", " ", stem)  # glued blanks
    return stem.replace("\x00", "＿★＿").replace("\x01", "＿＿＿")


NUM_OPT_RE = re.compile(r"^\s*[1-4１-４lI][\s　.．、)）]")
NUM_STRIP_RE = re.compile(r"^\s*[1-4１-４lI](?![0-9０-９])[\s　]*[.．、)）]?[\s　]*")


def clean_options(raw: list) -> list:
    """Strip '1 ', '2　', '4 )' style numbering that leaked into option texts."""
    n_sep = sum(1 for o in raw if NUM_OPT_RE.match(o or ""))
    # every option starts with its own number ("1 言いました", "2言わせました", ...) -> numbering leaked
    n_idx = sum(1 for i, o in enumerate(raw)
                if re.match(rf"^\s*[{i + 1}{'１２３４'[i] if i < 4 else ''}{'lI' if i == 0 else ''}](?![0-9０-９])", o or ""))
    numbered = n_sep >= 3 or (n_sep >= 1 and n_idx == len(raw))
    out = []
    for i, o in enumerate(raw):
        o = o or ""
        if numbered:
            o = NUM_STRIP_RE.sub("", o, count=1)
        else:
            m = re.match(r"^\s*([1-4])\s*[)）](?!\s*\d)\s*", o)  # not "1) 2月" (= OCR'd "12月")
            if m and int(m.group(1)) == i + 1:
                o = o[m.end():]
        out.append(o)
    return out


def option_text(o: str) -> tuple[str, bool]:
    t, furi = markup_to_text(o)
    return re.sub(r"\s*\n\s*", " ", t).strip(), furi


# ----------------------------------------------------------------------------- classification
MOJI_TYPES = {1: "kanji_reading", 2: "orthography", 3: "context", 4: "paraphrase", 5: "usage"}
BUNPO_TYPES = {1: "grammar_form", 2: "sentence_order", 3: "text_grammar"}
DOKKAI_TYPES = {4: "reading_short", 5: "reading_mid", 6: "reading_long", 7: "info_retrieval"}

# keyword sanity checks for the positional mondai assignment (instructions are OCR'd and messy)
VOCAB_KEYS = {1: ("読み方",), 2: ("字で書く",), 3: ("入れる", "入れの", "人れる"),
              4: ("意味が",), 5: ("使い方",)}
GRAMMAR_KEYS = {1: ("入れる", "入れの", "人れる"), 2: ("★",), 3: ("文章全体", "中に入る"),
                4: ("4)", "4」", "４)", "４）", "4）"), 5: ("2)", "２)", "２）", "2）"),
                6: ("文章を読ん",), 7: ("ページ", "案内", "お知らせ", "ポスター", "プリント", "問題7", "問題７")}


def check_keywords(table, mondai, instruction) -> bool:
    ins = re.sub(r"\s+", "", instruction)
    return any(k.replace(" ", "") in ins for k in table.get(mondai, ()))


# ----------------------------------------------------------------------------- parsing
dropped = Counter()
drop_examples = {}
notes = Counter()
note_examples = {}


def drop(reason: str, info: str = ""):
    dropped[reason] += 1
    drop_examples.setdefault(reason, info)


def note(reason: str, info: str = ""):
    notes[reason] += 1
    note_examples.setdefault(reason, info)


HEADER_ONLY_RE = re.compile(r"^\s*[（(]?\s*[1-4１-４]\s*[)）]?\s*[.．]?\s*$")


def split_pieces(passage_html: str) -> list:
    """Split a group passage on [[passage-break]]; merge header-only pieces like '(2).' with the next."""
    pieces = []
    carry = ""
    for p in passage_html.split("[[passage-break]]"):
        plain = re.sub(r"\[\[[^\]]*\]\]|<[^>]+>", "", p)
        if HEADER_ONLY_RE.match(plain):
            carry += p + "[[br]]"
            continue
        pieces.append(carry + p)
        carry = ""
    if carry:
        if pieces:
            pieces[-1] += carry
        else:
            pieces.append(carry)
    return pieces


def strip_qnum(text: str, nums) -> str:
    """Remove a leading '12．' / '34　' question number (only when it equals the item's own number)."""
    for n in nums:
        if n is None:
            continue
        m = re.match(rf"^\s*{n}\s*[．.、)）:：\s　]+(?=\S)", text)
        if m:
            return text[m.end():]
    return text


def build_question(*, exam_name, date, sec_type, q, section, mondai, qtype, passage, passage_id, furi_p=False):
    qid = f"{SOURCE}:n3-{date}-{sec_type}-{q['id']}"
    source_url = f"{BASE}/n3/{date}/{sec_type}"
    stem, furi_q = markup_to_text(q.get("textHtml") or q.get("text") or "")
    stem = strip_qnum(stem, [q.get("questionNumber"), q.get("id")])
    if qtype == "sentence_order":
        stem = normalize_star(stem)
    if qtype == "text_grammar" and re.fullmatch(r"\d{1,2}", stem.strip()):
        stem = f"【{stem.strip()}】"  # bare blank number -> marker
    raw_opts = clean_options(q.get("options") or [])
    options, furi_o = [], False
    for o in raw_opts:
        t, f = option_text(o)
        furi_o = furi_o or f
        options.append(t)
    if not (2 <= len(options) <= 4) or any(not o for o in options):
        drop("bad options (count or empty)", f"{qid} {options}")
        return None
    ans = q.get("correctAnswer")
    if not isinstance(ans, int) or not (1 <= ans <= len(options)):
        drop("no/invalid answer key", f"{qid} correctAnswer={ans!r}")
        return None
    if not stem:
        drop("empty question stem", qid)
        return None
    if section == "moji" and mondai in (1, 2, 4) and "＿" not in stem:
        note(f"moji 問題{mondai}: no underline marker in stem (kept)", f"{qid} {stem[:40]}")
    if qtype == "sentence_order" and (stem.count("＿★＿") != 1 or stem.count("＿＿＿") != 3):
        note("sentence_order stem without the usual 3 blanks + ＿★＿ (kept)", f"{qid} {stem[:70]}")
    if len(set(options)) != len(options):
        note("duplicate option texts (kept, answer from key)", f"{qid} {options}")
    return {
        "id": qid,
        "source": SOURCE,
        "source_url": source_url,
        "exam": exam_name,
        "section": section,
        "mondai": mondai,
        "type": qtype,
        "passage": passage or None,
        "passage_id": passage_id if passage else None,
        "question": stem,
        "options": options,
        "answer": ans - 1,
        "explanation": None,
        "audio": None,
        "image": None,
        "transcript": None,
        "furigana": bool(furi_q or furi_o or (furi_p and passage)),
    }


def parse_exam(data: dict) -> tuple[str, list]:
    date = data["date"]
    year, month = data.get("year") or int(date[:4]), data.get("month") or int(date[4:])
    exam_name = f"JLPT N3 {year}年{month}月"
    out = []
    kw = dict(exam_name=exam_name, date=date)
    for sec in data.get("sections") or []:
        sec_type = sec.get("type")
        groups = sec.get("groups") or []
        if sec_type == "vocabulary":
            for gi, g in enumerate(groups):
                mondai = gi + 1
                if mondai not in MOJI_TYPES:
                    for q in g["questions"]:
                        drop("extra vocabulary group", f"{date} g{gi}")
                    continue
                if not check_keywords(VOCAB_KEYS, mondai, g.get("instruction") or ""):
                    note("vocab instruction keyword mismatch (positional mondai kept)",
                         f"{date} 問題{mondai}: {g.get('instruction', '')[:40]}")
                for q in g["questions"]:
                    rec = build_question(**kw, sec_type=sec_type, q=q, section="moji", mondai=mondai,
                                         qtype=MOJI_TYPES[mondai], passage=None, passage_id=None)
                    if rec:
                        out.append(rec)
        elif sec_type == "grammar":
            # expand groups to (mondai, group, questions, pieces) units
            units = []
            for gi, g in enumerate(groups):
                mondai = gi + 1
                qs = g["questions"]
                ph = g.get("passageHtml") or ""
                pieces = split_pieces(ph) if ph else []
                if mondai == 6 and len(groups) == 6 and len(qs) == 6 and len(pieces) == 2:
                    # 問題6 (4 q) and 問題7 (2 q) were merged into one group on the site
                    note("問題6+7 merged in one group -> split by passage-break", date)
                    units.append((6, g, qs[:4], [pieces[0]]))
                    units.append((7, g, qs[4:], [pieces[1]]))
                    continue
                units.append((mondai, g, qs, pieces))
            for mondai, g, qs, pieces in units:
                if mondai > 7:
                    for q in qs:
                        drop("extra grammar/reading group", f"{date} g{mondai}")
                    continue
                if not check_keywords(GRAMMAR_KEYS, mondai, g.get("instruction") or ""):
                    note("grammar instruction keyword mismatch (positional mondai kept)",
                         f"{date} 問題{mondai}: {g.get('instruction', '')[:40]}")
                if mondai in BUNPO_TYPES:
                    section, qtype = "bunpo", BUNPO_TYPES[mondai]
                else:
                    section, qtype = "dokkai", DOKKAI_TYPES[mondai]
                if mondai < 3:
                    if pieces:
                        note("passage on 問題1/2 group ignored", f"{date} 問題{mondai}: {pieces[0][:30]}")
                    for q in qs:
                        rec = build_question(**kw, sec_type="grammar", q=q, section=section, mondai=mondai,
                                             qtype=qtype, passage=None, passage_id=None)
                        if rec:
                            out.append(rec)
                    continue
                # map questions to sub-passages: 問題4 = 4 texts x 1 q, 問題5 = 2 texts x 3 q
                expected = {4: 4, 5: 2}.get(mondai, 1)
                if expected > 1 and len(pieces) == expected and len(qs) % expected == 0:
                    per = len(qs) // expected
                    assign = [i // per for i in range(len(qs))]
                    texts = [markup_to_text(p) for p in pieces]
                else:
                    if expected > 1:
                        note(f"問題{mondai}: sub-passages not separable -> whole group passage",
                             f"{date} pieces={len(pieces)} q={len(qs)}")
                    assign = [0] * len(qs)
                    texts = [markup_to_text("[[br]][[br]]".join(pieces))]
                group_recs = []
                for qi, q in enumerate(qs):
                    ptext, pfuri = texts[assign[qi]]
                    pid = f"{SOURCE}:n3-{date}-m{mondai}" + (f"-{assign[qi] + 1}" if len(texts) > 1 else "")
                    if not ptext:
                        drop("passage question without passage", f"n3-{date}-grammar-{q['id']}")
                        continue
                    rec = build_question(**kw, sec_type="grammar", q=q, section=section, mondai=mondai,
                                         qtype=qtype, passage=ptext, passage_id=pid, furi_p=pfuri)
                    if rec:
                        group_recs.append(rec)
                if qtype == "text_grammar" and group_recs:
                    # stems are just the blank number; if it does not occur in the passage but the passage
                    # has exactly one 【n】 marker per question, point each stem at the passage's marker
                    ptext = group_recs[0]["passage"]
                    z2h = str.maketrans("０１２３４５６７８９", "0123456789")
                    marks = list(dict.fromkeys(m.translate(z2h) for m in re.findall(r"【\s*([0-9０-９]{1,2})", ptext)))
                    nums = [re.sub(r"\D", "", r["question"].translate(z2h)) for r in group_recs]
                    if len(marks) == len(group_recs) and any(n not in marks for n in nums):
                        for r, mk in zip(group_recs, marks):
                            r["question"] = f"【{mk}】"
                        note("text_grammar stems renumbered to the passage's 【n】 markers", f"{date} {nums} -> {marks}")
                out.extend(group_recs)
        else:
            for g in groups:
                for q in g.get("questions") or []:
                    drop(f"unknown section type {sec_type!r}", date)
    return exam_name, out


# ----------------------------------------------------------------------------- listening free samples
SPEAKER = {"male": "男", "female": "女", "narrator": ""}


def rsc_payload(html: str) -> str:
    """Concatenate the Next.js flight data (self.__next_f.push([1,"..."])) embedded in the page."""
    parts = []
    for c in re.findall(r"self\.__next_f\.push\((\[.*?\])\)</script>", html, flags=re.S):
        try:
            a = json.loads(c)
        except json.JSONDecodeError:
            continue
        if len(a) > 1 and isinstance(a[1], str):
            parts.append(a[1])
    return "".join(parts)


def parse_listening_sample(n: str, html: str) -> list:
    """The page server-renders one free sample question (with answer key) of the Pro listening test."""
    payload = rsc_payload(html)
    i = payload.find('"sample":{')
    if i < 0:
        drop("listening page without free sample", n)
        return []
    sample, _ = json.JSONDecoder().raw_decode(payload, i + len('"sample":'))
    section = sample.get("section") or {}
    mondai = section.get("problem_number")
    title = sample.get("title") or f"Practice Test {n}"
    total = sample.get("totalQuestions")
    if total:
        notes[f"listening Pro-only questions not crawled (login + paid, /api/listening disallowed)"] += max(0, total - len(section.get("items") or []))
    audio_tags = re.findall(r'<audio[^>]*\bsrc="([^"]+)"', html)
    img_tags = [u for u in re.findall(r'<img[^>]*\bsrc="([^"]+)"', html) if "/api/listening/" in u]
    out = []
    for it in section.get("items") or []:
        qid = f"{SOURCE}:n3-listening-{n}-{it.get('item_id')}"
        choices = it.get("choices") or []
        options = [norm(c.get("ja") or "") for c in choices]
        correct_id = str((it.get("answer") or {}).get("correct_choice_id") or "")
        idx = [k for k, c in enumerate(choices) if str(c.get("id")) == correct_id]
        if len(idx) != 1:
            drop("no/invalid answer key", qid)
            continue
        if not (2 <= len(options) <= 4) or any(not o for o in options):
            drop("bad options (count or empty)", f"{qid} {options}")
            continue
        audio_uri = (it.get("audio") or {}).get("uri") or ""
        audio = next((u for u in audio_tags if audio_uri and u.split("?")[0].endswith(audio_uri)), None)
        if audio is None and audio_uri:
            audio = f"/api/listening/{LEVEL}/{n}/media/{audio_uri}?sample=1"
        image_uri = (it.get("image") or {}).get("uri") or ""
        image = None
        if it.get("printed_choice_mode") == "images" and image_uri:
            image = next((u for u in img_tags if u.split("?")[0].endswith(image_uri)),
                         f"/api/listening/{LEVEL}/{n}/media/{image_uri}?sample=1")
        script = []
        for ln in it.get("script") or []:
            sp = SPEAKER.get(ln.get("speaker_type"), "")
            txt = norm(ln.get("japanese") or "")
            if txt:
                script.append(f"{sp}：{txt}" if sp else txt)
        if not audio:
            drop("listening without audio", qid)
            continue
        out.append({
            "id": qid,
            "source": SOURCE,
            "source_url": f"{BASE}/n3/listening/{n}",
            "exam": f"JLPT N3 Listening {title}",
            "section": "choukai",
            "mondai": mondai,
            "type": "listening",
            "passage": None,
            "passage_id": None,
            "question": norm((it.get("question") or {}).get("ja") or "") or "音声を聞いて、正しい答えを一つえらびなさい。",
            "options": options,
            "answer": idx[0],
            "explanation": None,
            "audio": BASE + audio if audio.startswith("/") else audio,
            "image": (BASE + image if image.startswith("/") else image) if image else None,
            "transcript": "\n".join(script) or None,
            "furigana": False,
        })
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ----------------------------------------------------------------------------- validation
def validate(questions: list) -> list:
    problems = []
    ids = Counter(q["id"] for q in questions)
    for k, v in ids.items():
        if v > 1:
            problems.append(f"duplicate id {k} x{v}")
    for q in questions:
        qid = q["id"]
        if not (2 <= len(q["options"]) <= 4) or not all(o.strip() for o in q["options"]):
            problems.append(f"{qid}: options {q['options']}")
        if not (isinstance(q["answer"], int) and 0 <= q["answer"] < len(q["options"])):
            problems.append(f"{qid}: answer {q['answer']}")
        if not q["question"].strip():
            problems.append(f"{qid}: empty question")
        if q["section"] not in ("moji", "bunpo", "dokkai", "choukai"):
            problems.append(f"{qid}: section {q['section']}")
        if q["type"] in ("text_grammar", "reading_short", "reading_mid", "reading_long", "info_retrieval"):
            if not q["passage"] or not q["passage_id"]:
                problems.append(f"{qid}: passage question without passage")
        if q["section"] == "choukai" and not q["audio"]:
            problems.append(f"{qid}: listening without audio")
        if q["audio"] and not q["audio"].startswith("http"):
            problems.append(f"{qid}: relative audio url")
    # same passage_id must carry the same passage text
    by_pid = defaultdict(set)
    for q in questions:
        if q["passage_id"]:
            by_pid[q["passage_id"]].add(q["passage"])
    for pid, texts in by_pid.items():
        if len(texts) > 1:
            problems.append(f"passage_id {pid} has {len(texts)} different texts")
    return problems


# ----------------------------------------------------------------------------- main
def main():
    robots = fetch("/robots.txt", "robots.txt") or ""
    print("robots.txt: 'Disallow: /api/' but 'Allow: /api/test/' -> only /api/test/ is used; "
          f"Crawl-delay {re.search(r'Crawl-delay:\s*(\d+)', robots).group(1) if 'Crawl-delay' in robots else '?'} "
          f"(we sleep {SLEEP}s)")
    level_html = fetch(f"/{LEVEL}", f"level_{LEVEL}.html") or ""
    dates = sorted(set(re.findall(rf'href="/{LEVEL}/(\d{{6}})"', level_html)))
    listening = sorted(set(re.findall(rf'href="/{LEVEL}/listening/(\d+)"', level_html)), key=int)
    print(f"N3 past-exam sets listed: {len(dates)} | listening practice tests: {len(listening)}")

    all_q = []
    per_exam = {}
    for d in dates:
        body = fetch(f"/api/test/{LEVEL}/{d}", f"api_test_{LEVEL}_{d}.json")
        if not body:
            drop("exam API unavailable", d)
            continue
        data = json.loads(body)
        if (data.get("level") or "").upper() != "N3":
            drop("exam not N3", d)
            continue
        name, qs = parse_exam(data)
        per_exam[name] = (len(qs), data.get("totalQuestions"))
        all_q.extend(qs)

    for n in listening:
        html = fetch(f"/{LEVEL}/listening/{n}", f"listening_{LEVEL}_{n}.html")
        if not html:
            drop("listening page unavailable", n)
            continue
        qs = parse_listening_sample(n, html)
        if qs:
            per_exam[qs[0]["exam"]] = (len(qs), None)
        all_q.extend(qs)

    problems = validate(all_q)
    if problems:
        print(f"\nVALIDATION PROBLEMS ({len(problems)}):")
        for p in problems[:50]:
            print("  ", p)
        raise SystemExit(1)

    OUT.write_text(json.dumps(all_q, ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ summary
    print(f"\nwrote {OUT} : {len(all_q)} questions from {len(per_exam)} exams/sets")
    for name, (n, total) in per_exam.items():
        print(f"  {name:<40} {n:>3} q" + (f"  (site total {total})" if total else ""))
    print("per section:", dict(Counter(q["section"] for q in all_q)))
    print("per type:", dict(Counter(q["type"] for q in all_q)))
    print("per section/mondai:", dict(sorted(Counter(f"{q['section']}{q['mondai']}" for q in all_q).items())))
    print("with explanation:", sum(1 for q in all_q if q["explanation"]),
          "| with passage:", sum(1 for q in all_q if q["passage"]),
          f"(distinct passages {len({q['passage_id'] for q in all_q if q['passage_id']})})",
          "| with audio:", sum(1 for q in all_q if q["audio"]),
          "| with image:", sum(1 for q in all_q if q["image"]),
          "| with transcript:", sum(1 for q in all_q if q["transcript"]),
          "| furigana flattened:", sum(1 for q in all_q if q["furigana"]))
    print("dropped questions:", sum(dropped.values()))
    for k, v in dropped.most_common():
        print(f"  {v:>4}  {k}   e.g. {drop_examples[k]}")
    print("notes (kept questions / not crawled):")
    for k, v in notes.most_common():
        print(f"  {v:>4}  {k}" + (f"   e.g. {note_examples[k]}" if k in note_examples else ""))

    rnd = random.Random(int(os.environ.get("JLPTPT_SEED", "3")))
    print("\n--- spot check (8 random questions) ---")
    for q in rnd.sample(all_q, min(8, len(all_q))):
        print(f"[{q['id']}] {q['exam']} | {q['section']} 問題{q['mondai']} {q['type']}")
        if q["passage"]:
            print("  passage:", q["passage"][:160].replace("\n", " / "), "…")
        print("  Q:", q["question"].replace("\n", " / "))
        for k, o in enumerate(q["options"]):
            print(f"   {'*' if k == q['answer'] else ' '} {k + 1}. {o}")
        if q["audio"]:
            print("  audio:", q["audio"])


if __name__ == "__main__":
    main()
