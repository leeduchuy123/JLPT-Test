"""Crawler: tryjlpt.com (N3 only).

How the site works
------------------
tryjlpt.com is a Vue SSR app. All content comes from a single JSON endpoint:
    POST https://api.tryjlpt.com/   body {"m":"exam","fn":<name>,...}   header Namespace: TryJlpt
  * fn=exam-list        -> exam metadata (level/type/skill filters, pageIndex/pageSize)
  * fn=exam-detail      -> exam info incl. legacy inline content `info.data` (JSON string with
                           KTNN = 言語知識+読解 blocks, NH = 聴解 blocks, answers carry IsCorrect)
  * fn=exam-detail-full -> new format (dataVersion2 -> sentences/questions/answers tables).
                           Requires a logged-in member (route /exam/detail/:id has requiresAuth,
                           the API answers "Đã có lỗi xảy ra" anonymously). NOT crawlable.
Only the legacy "Test JLPT N3 (n)" exams (list type 1) still embed their content in `info.data`.
The official past papers (type 7) and the member-made "Đề thi trình độ N3" (type 2) /
skill drills (type 3) only have dataVersion2 -> skipped (we probe a sample to be sure).

Run:  cd D:/JLPT-app && python -I scripts/crawl/tryjlpt.py
"""
import hashlib
import json
import os
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
CACHE = ROOT / "crawl/cache/tryjlpt"
OUT = ROOT / "crawl/raw/tryjlpt.json"
API = "https://api.tryjlpt.com/"
STORAGE = "https://storage.dekiru.vn"
SOURCE = "tryjlpt"
LEVEL = 3
SLEEP = 0.8
PROBE_NON_LEGACY = int(os.environ.get("TRYJLPT_PROBE", "15"))  # how many type-2/3 exams to probe

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JLPT-study-crawler/0.1 (personal study use)",
    "Content-Type": "application/json",
    "Namespace": "TryJlpt",
    "Origin": "https://tryjlpt.com",
    "Referer": "https://tryjlpt.com/",
}

CACHE.mkdir(parents=True, exist_ok=True)
OUT.parent.mkdir(parents=True, exist_ok=True)

_last_request = 0.0


def api(body: dict, cache_name: str) -> dict:
    """POST to the API, caching the raw response JSON under crawl/cache/tryjlpt/."""
    global _last_request
    path = CACHE / cache_name
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8"))
    wait = SLEEP - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    r = requests.post(API, json=body, headers=HEADERS, timeout=60)
    _last_request = time.time()
    r.raise_for_status()
    path.write_text(r.text, encoding="utf-8")
    return r.json()


# ----------------------------------------------------------------------------- listing
LIST_FILTERS = {
    # list page /vi/exams/<type>  -> params used by exam/list.vue (asyncData)
    1: {"skill": -1, "isCreatedByMember": False, "isOnline": False},            # Đề thi chuẩn JLPT (legacy, has inline data)
    7: {"skill": -1, "isCreatedByMember": False, "isOnline": False, "type": 7},  # Đề thi JLPT các năm (past papers)
    2: {"skill": 0, "isCreatedByMember": True, "isOnline": False},              # Đề thi JLPT mới
    3: {"skill": 6, "isCreatedByMember": True, "isOnline": False},              # Đề thi luyện kỹ năng
}


def list_exams(list_type: int) -> list:
    exams = []
    page = 1
    page_size = 200
    while True:
        body = {"m": "exam", "fn": "exam-list", "level": LEVEL, "pageIndex": page, "pageSize": page_size}
        body.update(LIST_FILTERS[list_type])
        name = f"list_n3_type{list_type}.json" if page == 1 else f"list_n3_type{list_type}_p{page}.json"
        d = api(body, name)
        data = d.get("data") or []
        exams.extend(x["info"] for x in data if x.get("info", {}).get("level") == LEVEL)
        if len(data) < page_size:
            break
        page += 1
    return exams


def exam_detail(exam_id: int) -> dict:
    d = api({"m": "exam", "fn": "exam-detail", "id": exam_id}, f"detail_short_{exam_id}.json")
    return d.get("data") or {}


# ----------------------------------------------------------------------------- html -> text
RUBY_RE = re.compile(r"<ruby>", re.I)


def html_to_text(html: str) -> tuple[str, str | None, bool]:
    """Return (plain text, first image url or None, had_ruby)."""
    if not html:
        return "", None, False
    had_ruby = bool(RUBY_RE.search(html))
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(["rt", "rp"]):
        t.decompose()
    image = None
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if src and image is None:
            image = absolutize(src)
        img.decompose()
    for span in soup.find_all("span", class_="content_underline"):
        span.replace_with(" ＿★＿ " if "★" in span.get_text() else " ＿＿＿ ")
    for span in soup.find_all("span", class_="content_number_highlight"):
        n = span.get_text(strip=True).replace("\xa0", "")
        span.replace_with(f"【{n}】" if n else "")
    for u in soup.find_all("u"):
        txt = u.get_text()
        u.replace_with(f"＿{txt}＿" if txt.strip() else "＿＿＿")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for blk in soup.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "blockquote"]):
        blk.append("\n")
    text = soup.get_text()
    text = text.replace("\xa0", " ").replace("\u200b", "")
    lines = [re.sub(r"[ \t]+", " ", ln).strip(" ") for ln in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # empty ASCII parentheses used as blanks -> full-width blank marker
    text = re.sub(r"\(\s*\)", "（　）", text)
    text = re.sub(r"（[ 　]+）", "（　）", text)
    return text, image, had_ruby


def absolutize(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("http"):
        return re.sub(r"(?<!:)//+", "/", url)
    return STORAGE + "/" + url.lstrip("/")


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ----------------------------------------------------------------------------- classification
MOJI_TYPES = {1: "kanji_reading", 2: "orthography", 3: "context", 4: "paraphrase", 5: "usage"}
BUNPO_TYPES = {1: "grammar_form", 2: "sentence_order", 3: "text_grammar"}
DOKKAI_TYPES = {4: "reading_short", 5: "reading_mid", 6: "reading_long", 7: "info_retrieval"}


def mondai_number(title_text: str) -> int | None:
    m = re.search(r"問題\s*[:：]?\s*(\d+)", title_text)
    if m:
        return int(m.group(1))
    m = re.search(r"もんだい\s*(\d+)", title_text)
    return int(m.group(1)) if m else None


def guess_moji_mondai(title: str) -> int | None:
    if "読み方" in title:
        return 1
    if "漢字で書く" in title or "漢字" in title:
        return 2
    if "意味が最も近い" in title or "意味" in title:
        return 4
    if "使い方" in title:
        return 5
    if "入れるのに" in title:
        return 3
    return None


def guess_bunpo_mondai(title: str) -> int | None:
    if "★" in title:
        return 2
    if "文章" in title:
        return 3
    if "入れるのに" in title or "入れる" in title:
        return 1
    return None


# ----------------------------------------------------------------------------- parsing
dropped = Counter()
drop_examples = {}


def drop(reason: str, info: str = ""):
    dropped[reason] += 1
    drop_examples.setdefault(reason, info)


def build_question(exam, q, *, section, mondai, qtype, passage, passage_id, source_url, exam_name, placeholder_stem=None):
    qtext, image, ruby_q = html_to_text(q.get("Text") or "")
    options, ruby_o = [], False
    for a in q.get("Answers") or []:
        t, _img, r = html_to_text(a.get("Text") or "")
        ruby_o = ruby_o or r
        options.append(norm_space(t))
    correct = [i for i, a in enumerate(q.get("Answers") or []) if str(a.get("IsCorrect")) == "1"]
    if len(correct) != 1:
        drop("no/ambiguous answer key", f"{exam['id']}/{q.get('Id')} correct={correct}")
        return None
    if not (2 <= len(options) <= 4) or any(not o for o in options):
        drop("bad options (count or empty)", f"{exam['id']}/{q.get('Id')} {options}")
        return None
    meta = (q.get("Meta") or "").strip()
    transcript, explanation = None, None
    if meta:
        m = re.match(r"^\s*Script\s*[:：]\s*", meta)
        if m:
            transcript = meta[m.end():].strip() or None
        else:
            explanation = meta
    audio = absolutize(q.get("SoundUrl") or "") or None
    if section == "choukai" and not audio and not transcript:
        drop("listening without audio/transcript", f"{exam['id']}/{q.get('Id')}")
        return None
    if not qtext:
        if placeholder_stem:
            qtext = placeholder_stem
        elif section == "choukai":
            qtext = "音声を聞いて、正しい答えを一つえらびなさい。"
        elif section == "dokkai" and passage:
            qtext = "文章の内容と合っているものはどれか。"  # should not happen; checked below
            drop("dokkai question with empty stem", f"{exam['id']}/{q.get('Id')}")
            return None
        else:
            drop("empty question stem", f"{exam['id']}/{q.get('Id')}")
            return None
    return {
        "id": f"{SOURCE}:{exam['id']}-{q.get('Id')}",
        "source": SOURCE,
        "source_url": source_url,
        "exam": exam_name,
        "section": section,
        "mondai": mondai,
        "type": qtype,
        "passage": passage or None,
        "passage_id": passage_id if passage else None,
        "question": qtext,
        "options": options,
        "answer": correct[0],
        "explanation": explanation,
        "audio": audio,
        "image": image,
        "transcript": transcript,
        "furigana": bool(ruby_q or ruby_o),
    }


def parse_exam(exam: dict, detail: dict) -> list:
    info = detail.get("info") or {}
    raw = info.get("data")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        drop("exam data not JSON", str(exam["id"]))
        return []
    exam_name = f"tryjlpt {info.get('title') or exam.get('title')}"
    source_url = f"https://tryjlpt.com/vi/exam/info/{exam['id']}"
    out = []

    # --- KTNN: Type 1 = 文字・語彙 (問題1-5), Type 2 = 文法 (問題1-3) + 読解 (問題4-7)
    for blk in data.get("KTNN") or []:
        btype = int(blk.get("Type") or 0)
        prev_num = None
        for item in blk.get("BlockItems") or []:
            title, _i, _r = html_to_text(item.get("Title") or "")
            title = norm_space(title)
            num = mondai_number(title)
            passage, _pi, _pr = html_to_text(item.get("Sapo") or "")
            passage_id = f"{SOURCE}:{exam['id']}-{item.get('Id')}"
            if btype == 1:
                if num is None and title:
                    num = guess_moji_mondai(title)
                if num is None:
                    num = prev_num  # untitled continuation item
                prev_num = num
                section, qtype = "moji", MOJI_TYPES.get(num)
            elif btype == 2:
                if num is None and title:
                    num = guess_bunpo_mondai(title)
                if num is None:
                    num = prev_num
                prev_num = num
                if num in BUNPO_TYPES:
                    section, qtype = "bunpo", BUNPO_TYPES[num]
                else:
                    section, qtype = "dokkai", DOKKAI_TYPES.get(num)
            else:
                section, qtype = None, None
            if qtype is None:
                for q in item.get("Questions") or []:
                    drop("unclassified KTNN item", f"{exam['id']} Type={btype} title={title[:60]!r}")
                continue
            if qtype == "text_grammar":
                # stems are empty; the blank numbers are highlighted inside the passage
                numbers = re.findall(r"【(\d+)】", passage)
                for qi, q in enumerate(item.get("Questions") or []):
                    ph = (f"【{numbers[qi]}】に入れるのに最もよいものはどれか。" if qi < len(numbers)
                          else f"（{qi + 1}）に入れるのに最もよいものはどれか。")
                    rec = build_question(exam, q, section=section, mondai=num, qtype=qtype, passage=passage,
                                         passage_id=passage_id, source_url=source_url, exam_name=exam_name,
                                         placeholder_stem=ph)
                    if rec:
                        out.append(rec)
            else:
                for q in item.get("Questions") or []:
                    rec = build_question(exam, q, section=section, mondai=num, qtype=qtype,
                                         passage=passage if section == "dokkai" else None,
                                         passage_id=passage_id, source_url=source_url, exam_name=exam_name)
                    if rec:
                        out.append(rec)

    # --- NH: 聴解
    for blk in data.get("NH") or []:
        prev_num = None
        for item in blk.get("BlockItems") or []:
            title, _i, _r = html_to_text(item.get("Title") or "")
            num = mondai_number(norm_space(title)) or prev_num
            prev_num = num
            item_sound = absolutize(item.get("SoundUrl") or "") or None
            for q in item.get("Questions") or []:
                if not (q.get("SoundUrl") or "").strip() and item_sound:
                    q = dict(q, SoundUrl=item_sound)
                rec = build_question(exam, q, section="choukai", mondai=num, qtype="listening",
                                     passage=None, passage_id=None, source_url=source_url, exam_name=exam_name)
                if rec:
                    out.append(rec)
    return out


# ----------------------------------------------------------------------------- main
def main():
    print("robots.txt: tryjlpt.com allows all (User-agent: * / Allow: /)")
    all_questions = []
    per_exam = {}
    skipped_exams = Counter()

    legacy_lists = {1: list_exams(1), 7: list_exams(7)}
    other_lists = {2: list_exams(2), 3: list_exams(3)}
    for t, ex in {**legacy_lists, **other_lists}.items():
        print(f"list type {t}: {len(ex)} N3 exams")

    def crawl(exams, label):
        for info in exams:
            detail = exam_detail(info["id"])
            if not detail:
                skipped_exams[f"{label}: no detail"] += 1
                continue
            qs = parse_exam(info, detail)
            if not qs:
                skipped_exams[f"{label}: no inline content (dataVersion2 only, needs login)"] += 1
                continue
            per_exam[info["id"]] = (info["title"], len(qs))
            all_questions.extend(qs)

    crawl(legacy_lists[1], "type1 Đề thi chuẩn")
    crawl(legacy_lists[7], "type7 past papers")
    # type 2/3 exams were created in the new editor; probe a sample to confirm they carry no inline data
    crawl(other_lists[2][:PROBE_NON_LEGACY], f"type2 (probe {PROBE_NON_LEGACY}/{len(other_lists[2])})")
    crawl(other_lists[3][:PROBE_NON_LEGACY], f"type3 (probe {PROBE_NON_LEGACY}/{len(other_lists[3])})")

    # de-duplicate identical questions across exams
    seen = set()
    unique = []
    for q in all_questions:
        key = hashlib.sha1((q["question"] + "|" + "|".join(q["options"])).encode("utf-8")).hexdigest()
        if key in seen:
            drop("duplicate question (same stem+options in another exam)", q["id"])
            continue
        seen.add(key)
        unique.append(q)

    # validation
    for q in unique:
        assert 2 <= len(q["options"]) <= 4 and all(q["options"]), q["id"]
        assert 0 <= q["answer"] < len(q["options"]), q["id"]
        assert q["question"], q["id"]
        assert q["section"] in ("moji", "bunpo", "dokkai", "choukai"), q["id"]

    OUT.write_text(json.dumps(unique, ensure_ascii=False, indent=1), encoding="utf-8")

    # summary
    print(f"\nwrote {OUT} : {len(unique)} questions from {len(per_exam)} exams")
    for eid, (title, n) in sorted(per_exam.items()):
        print(f"  exam {eid:>5} {title:<28} {n:>3} q")
    print("per section:", dict(Counter(q["section"] for q in unique)))
    print("per type:", dict(Counter(q["type"] for q in unique)))
    print("with explanation:", sum(1 for q in unique if q["explanation"]),
          "| with transcript:", sum(1 for q in unique if q["transcript"]),
          "| with audio:", sum(1 for q in unique if q["audio"]),
          "| with image:", sum(1 for q in unique if q["image"]),
          "| with passage:", sum(1 for q in unique if q["passage"]))
    print("skipped exams:", dict(skipped_exams))
    print("dropped questions:", sum(dropped.values()))
    for k, v in dropped.most_common():
        print(f"  {v:>4}  {k}   e.g. {drop_examples[k]}")


if __name__ == "__main__":
    main()
