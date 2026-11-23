# -*- coding: utf-8 -*-
"""Tải các đề JLPT đã thi (N3, N2) trên masceron-jlpt.pages.dev -> crawl/redup/exams_<LEVEL>.json

Chạy từ thư mục gốc:  python -I scripts/crawl/masceron.py [N3 N2 ...]
Chỉ dùng thư viện chuẩn. Mỗi trang chỉ tải một lần (cache ở crawl/cache/masceron/, không commit),
nghỉ 1 giây giữa hai lần tải.

Lưu ý: robots.txt của trang này ghi "Disallow: /". Chủ repo đã quyết định vẫn tải một lần cho việc học
cá nhân (2026-11-23), nên script KHÔNG kiểm tra robots.txt. Đừng chạy lại với cache trống nếu không cần.

Cấu trúc trang (bản lưu ngoại tuyến của dethitiengnhat.com):
  main          danh sách đề sinh bằng JS: mỗi kỳ có 3 trang  dethitiengnhat_<L>/<phần>/<L>_<MM>_<YYYY>_<phần>
                phần = vocab (文字・語彙) | reading (文法・読解) | listening (聴解)
  div.big_item          tiêu đề 問題
  div.question_content  đoạn văn dùng chung cho các câu sau
  div.question_list     câu hỏi ("19. ...", "1番")
  div.answers#QS<n><k>  lựa chọn "k) ..."
  div#AS<n>   (ẩn)      đáp án, tính từ 1
  div#GT<n>   (ẩn)      "Tham khảo: ..." = câu hoàn chỉnh (ngữ pháp) hoặc script (nghe)
  div#type<n> (ẩn)      1=moji 2=bunpo 3=dokkai 4=choukai

Đầu ra: {level, source, fetched, exams:[nhãn], pages:[{level, exam:"YYYY-MM", part, url, items:[...]}]}
  item = {kind:"heading", mondai, text}
       | {kind:"passage", mondai, text}
       | {kind:"q", mondai, n, sect, stem, options:[...], answer (0-based | null), ref (GT | null)}
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE = "https://masceron-jlpt.pages.dev/"
CACHE_DIR = os.path.join(ROOT, "crawl", "cache", "masceron")
OUT_DIR = os.path.join(ROOT, "crawl", "redup")
UA = "Mozilla/5.0 (X11; Linux x86_64) JLPT-study-crawler/1.0 (personal study use)"
SLEEP = 1.0
PARTS = ("vocab", "reading", "listening")
SECT = {"1": "moji", "2": "bunpo", "3": "dokkai", "4": "choukai"}

# Giống buildArchiveData() trong main.html: 2010..2025, tháng 12 và 07, trừ các kỳ không có đề.
SKIP = {"N3": {"2010-12", "2020-07"}, "N2": {"2020-07"}, "N1": {"2020-07"}}


def exam_labels(level):
    return [f"{y}-{m}" for y in range(2025, 2009, -1) for m in ("12", "07") if f"{y}-{m}" not in SKIP[level]]


def page_url(level, label, part):
    year, month = label.split("-")
    return f"{BASE}dethitiengnhat_{level}/{part}/{level}_{month}_{year}_{part}"


_last = 0.0


def fetch(url, cache_name):
    """GET có cache trên đĩa + nghỉ giữa các lần tải. Trả None nếu trang không có."""
    global _last
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, cache_name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    wait = SLEEP - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = None
    for attempt in (1, 2):   # lỗi mạng thì thử lại một lần; 404 thì thôi
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} {url}", flush=True)
            if e.code == 404:
                break
        except Exception as e:  # noqa
            print(f"  lỗi tải (lần {attempt}) {url}: {e}", flush=True)
        finally:
            _last = time.time()
        if attempt == 1:
            time.sleep(5)
    if data is None:
        return None
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return data


# ---------------------------------------------------------------- DOM tối giản
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BLOCK = {"p", "div", "center", "tr", "li", "h1", "h2", "h3", "h4", "h5", "table", "ul", "ol"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def walk(self):
        for c in self.children:
            if isinstance(c, Node):
                yield c
                yield from c.walk()


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:  # thẻ đóng lạc thì bỏ qua
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse_html(html):
    tb = TreeBuilder()
    tb.feed(html)
    tb.close()
    return tb.root


def text_of(node, block=True):
    """Văn bản của một nút: <br> -> xuống dòng, <u>x</u> -> ＿x＿, bỏ <rt>/<rp>/<script>/<style>."""
    out = []

    def rec(n):
        for c in n.children:
            if isinstance(c, str):
                out.append(c)
                continue
            if c.tag in ("script", "style", "rt", "rp", "input", "audio", "iframe"):
                continue
            if c.tag == "br":
                out.append("\n")
                continue
            if c.tag == "u":
                inner = text_of(c, block=False).strip()
                out.append("＿" + inner + "＿" if inner else "")
                continue
            if c.tag in ("td", "th"):
                out.append(" ")
            if c.tag in BLOCK:
                out.append("\n")
            rec(c)
            if c.tag in BLOCK:
                out.append("\n")

    rec(node)
    t = "".join(out).replace("\xa0", " ").replace("\r", "")
    if block:
        lines = [re.sub(r"[ \t\f\v]+", " ", x).strip(" 　") for x in t.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n ")
    return re.sub(r"\s+", " ", t).strip(" 　")


# ---------------------------------------------------------------- phân tích một trang
FW = str.maketrans("０１２３４５６７８９", "0123456789")
RE_MONDAI = re.compile(r"[問間]\s*題\s*([0-9０-９]+)")   # trang nguồn đôi khi gõ nhầm 間題
RE_OPT = re.compile(r"^\s*[1-4１-４]\s*[)）.．、]\s*")
RE_STEM_NO = re.compile(r"^\s*(?:【\s*([0-9０-９]+)\s*】|\(?([0-9０-９]{1,3})\s*[.．)）番])\s*")
RE_REF = re.compile(r"^\s*Tham khảo\s*[:：]\s*", re.I)


def parse_page(html, level, label, part, url, notes):
    root = parse_html(html)
    hidden = {"AS": {}, "GT": {}, "type": {}}
    order = []
    for n in root.walk():
        if n.tag != "div":
            continue
        m = re.match(r"^(AS|GT|type)(\d+)$", n.attrs.get("id") or "")
        if m:
            hidden[m.group(1)][int(m.group(2))] = n
            continue
        cls = n.classes()
        if "big_item" in cls or "question_content" in cls or "question_list" in cls:
            order.append(n)
        elif "answers" in cls and re.match(r"^QS\d+$", n.attrs.get("id") or ""):
            order.append(n)

    items, mondai, cur = [], None, None
    for n in order:
        cls = n.classes()
        if "big_item" in cls:
            txt = text_of(n, block=False)
            m = RE_MONDAI.search(txt)
            if m:
                mondai = int(m.group(1).translate(FW))
            if txt:
                items.append({"kind": "heading", "mondai": mondai, "text": txt})
            cur = None
        elif "question_content" in cls:
            txt = text_of(n)
            if txt:
                items.append({"kind": "passage", "mondai": mondai, "text": txt})
            cur = None
        elif "question_list" in cls:
            cur = {"kind": "q", "mondai": mondai, "n": None, "sect": None, "stem": text_of(n), "options": [], "answer": None, "ref": None}
            items.append(cur)
        else:  # lựa chọn: id = QS<n><k>, k là chữ số cuối
            if cur is None:
                notes["lựa chọn không có câu hỏi"] += 1
                continue
            qid = n.attrs["id"][2:]
            num = int(qid[:-1]) if len(qid) > 1 else None
            if cur["n"] is None:
                cur["n"] = num
            elif num != cur["n"]:
                notes["lựa chọn lệch số câu"] += 1
                continue
            cur["options"].append(RE_OPT.sub("", text_of(n, block=False)).strip())

    for q in items:
        if q["kind"] != "q":
            continue
        n = q["n"]
        if n is None:
            m = RE_STEM_NO.match(q["stem"])
            if m:
                q["n"] = n = int((m.group(1) or m.group(2)).translate(FW))
            notes["câu không có lựa chọn"] += 1
        if n in hidden["AS"]:
            a = text_of(hidden["AS"][n], block=False).translate(FW)
            if a.isdigit() and 1 <= int(a) <= max(len(q["options"]), 1):
                q["answer"] = int(a) - 1
            else:
                notes["đáp án lạ"] += 1
        if n in hidden["GT"]:
            ref = RE_REF.sub("", text_of(hidden["GT"][n]))
            q["ref"] = ref or None
        if n in hidden["type"]:
            q["sect"] = SECT.get(text_of(hidden["type"][n], block=False))
    return {"level": level, "exam": label, "part": part, "url": url, "items": items}


def crawl_level(level):
    notes, pages, missing = Counter(), [], []
    labels = exam_labels(level)
    for label in labels:
        for part in PARTS:
            url = page_url(level, label, part)
            html = fetch(url, f"{level}_{label}_{part}.html")
            if not html or "question_list" not in html:
                missing.append(f"{label}/{part}")
                continue
            pages.append(parse_page(html, level, label, part, url, notes))
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {"level": level, "source": BASE + "main", "fetched": time.strftime("%Y-%m-%d"), "exams": labels, "pages": pages}
    path = os.path.join(OUT_DIR, f"exams_{level}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    qs = [it for p in pages for it in p["items"] if it["kind"] == "q"]
    print(f"\n=== {level}: {len(labels)} kỳ, {len(pages)} trang, {len(qs)} câu -> {path}")
    print("theo phần:", dict(Counter(p["part"] for p in pages)))
    print("câu theo loại:", dict(Counter(q["sect"] for q in qs)))
    print("có đáp án:", sum(1 for q in qs if q["answer"] is not None), "· có Tham khảo:", sum(1 for q in qs if q["ref"]))
    print("đoạn văn:", sum(1 for p in pages for it in p["items"] if it["kind"] == "passage"))
    print("trang thiếu:", missing or "không")
    print("ghi chú:", dict(notes) or "không")


if __name__ == "__main__":
    for lv in (sys.argv[1:] or ["N3", "N2"]):
        if lv not in SKIP:
            sys.exit(f"Không biết cấp độ {lv}")
        crawl_level(lv)
