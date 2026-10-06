"""Shared helpers for the N3 crawlers (mlc, nihongopro, japanesequizzes, gyanmirai).

Run from D:/JLPT-app:  python -I scripts/crawl/<slug>.py
`-I` ignores the user site-packages where requests/bs4/lxml live, so we add it back explicitly.
"""
import hashlib
import json
import os
import re
import site
import sys
import time
import urllib.robotparser
from collections import Counter
from html import unescape
from urllib.parse import urlparse

sys.path.append(site.getusersitepackages())
import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JLPT-app-crawler/0.1 (+personal study project; contact via site form)"
SLEEP = 0.8


class Fetcher:
    def __init__(self, slug):
        self.slug = slug
        self.cache_dir = os.path.join(ROOT, "crawl", "cache", slug)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.sess = requests.Session()
        self.sess.headers["User-Agent"] = UA
        self._robots = {}
        self._last = 0.0

    def _rp(self, url):
        host = urlparse(url).scheme + "://" + urlparse(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.sess.get(host + "/robots.txt", timeout=30)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except Exception:
                rp.parse([])
            self._robots[host] = rp
        return self._robots[host]

    def allowed(self, url):
        return self._rp(url).can_fetch(UA, url) and self._rp(url).can_fetch("*", url)

    def get(self, url, binary=False):
        """Return page text (or bytes), served from cache when available. None if disallowed/failed."""
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("//", 1)[-1])[:80]
        path = os.path.join(self.cache_dir, f"{safe}_{key}" + (".bin" if binary else ".html"))
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            return data if binary else data.decode("utf-8", "replace")
        if not self.allowed(url):
            print("  robots.txt disallows", url)
            return None
        wait = SLEEP - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.sess.get(url, timeout=40)
        except Exception as e:
            print("  fetch error", url, e)
            return None
        finally:
            self._last = time.time()
        if r.status_code != 200:
            print("  HTTP", r.status_code, url)
            return None
        if binary:
            data = r.content
        else:
            r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
            data = r.text.encode("utf-8")
        with open(path, "wb") as f:
            f.write(data)
        return data if binary else data.decode("utf-8", "replace")


# ---------- text helpers ----------
def flatten_ruby(soup_or_tag):
    """<ruby>漢<rt>かん</rt></ruby> -> 漢 . Returns True if any ruby was flattened."""
    found = False
    for rt in soup_or_tag.find_all(["rt", "rp"]):
        rt.decompose()
        found = True
    for rb in soup_or_tag.find_all(["rb", "ruby"]):
        rb.unwrap()
    return found


def mark_underline(tag):
    """Wrap underlined/red target words as ＿word＿ so the target is still visible in plain text."""
    for u in tag.find_all(["u"]):
        u.replace_with("＿" + u.get_text() + "＿")
    for sp in tag.find_all(True):
        style = (sp.get("style") or "").replace(" ", "").lower()
        color = (sp.get("color") or "").lower()
        if "text-decoration:underline" in style or color in ("#ff0000", "red"):
            sp.replace_with("＿" + sp.get_text() + "＿")


def clean(text):
    text = unescape(text or "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_numbering(opt):
    return re.sub(r"^\s*(?:[1-4１-４]|[A-Da-d]|[①②③④])\s*[.．)）、]?\s*", "", opt).strip()


def sha_id(*parts):
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def make_q(source, sid, source_url, section, qtype, question, options, answer, *, exam=None, mondai=None,
           passage=None, passage_id=None, explanation=None, audio=None, image=None, transcript=None, furigana=False):
    return {
        "id": f"{source}:{sid}", "source": source, "source_url": source_url, "exam": exam,
        "section": section, "mondai": mondai, "type": qtype, "passage": passage, "passage_id": passage_id,
        "question": question, "options": options, "answer": answer, "explanation": explanation,
        "audio": audio, "image": image, "transcript": transcript, "furigana": bool(furigana),
    }


def validate(q):
    """Return None if OK, else reason string."""
    if not isinstance(q["question"], str) or not q["question"].strip():
        return "empty question"
    opts = q["options"]
    if not (2 <= len(opts) <= 4):
        return f"{len(opts)} options"
    if any((not isinstance(o, str)) or not o.strip() for o in opts):
        return "empty option"
    if not isinstance(q["answer"], int) or not (0 <= q["answer"] < len(opts)):
        return "answer out of range"
    if len(set(opts)) != len(opts):
        return "duplicate options"
    return None


def finish(slug, questions, dropped):
    """Validate, dedupe, write raw/<slug>.json, print summary."""
    out, seen = [], set()
    for q in questions:
        why = validate(q)
        if why:
            dropped[why] += 1
            continue
        if q["id"] in seen:
            dropped["duplicate id"] += 1
            continue
        seen.add(q["id"])
        out.append(q)
    path = os.path.join(ROOT, "crawl", "raw", f"{slug}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n=== {slug}: wrote {len(out)} questions -> {path}")
    print("per section:", dict(Counter(q["section"] for q in out)))
    print("per type   :", dict(Counter(q["type"] for q in out)))
    print("with explanation:", sum(1 for q in out if q["explanation"]))
    print("dropped:", dict(dropped) if dropped else "none")
    return out
