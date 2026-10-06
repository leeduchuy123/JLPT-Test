"""Crawler (blocked): Migii JLPT N3 practice -> crawl/raw/migii.json

Source page : https://jlpt.migii.net/vi/practice/n3  (Angular SPA, base href /vi/)
API base    : https://jlpt.migii.net/api/   (BASE_API_URL_1 in chunk-4P5BCTP2.js)

Endpoints discovered in the JS bundles (chunk-ATRCLOFK.js practice service, chunk-VRB7ZS6B.js exam service):
  GET  /api//question/question/countQuestionDetail                      -> plain JSON, question counts per tag/level/kind
  GET  /api/question/v2/practice?kind=<kind>&lang=<lang>&level=<1-5>&limit=<n>
  GET  /api/question/v2/practice/wrong-question?tag=..&lang=..&level=..&limit=..   (needs account history)
  GET  /api/question/v2/evaluate?kind=..&lang=..&level=..&limit=..
  POST /api/question/v2/details   {ids:[...], lang}
  GET  /api/exam/list-exam?level=<n>&type=<t>                           -> plain JSON list
  GET  /api/exam/v2?id=<examId>&lang=<lang>                             -> encrypted
  GET  https://admin.migii.net/api/theory/...                            (grammar/vocab theory, not questions)
  kind values (Vietnamese labels, returned by the API's own 400 validation message):
      cách đọc kanji, điền từ theo văn cảnh, thay đổi cách nói, ứng dụng từ, cách viết từ, hình thành từ,
      lựa chọn ngữ pháp, lắp ghép câu, ngữ pháp theo đoạn văn, đoạn văn ngắn, đoạn văn vừa, đoạn văn dài,
      đọc hiểu tổng hợp, đọc hiểu chủ đề, tìm thông tin, nghe hiểu chủ đề, nghe hiểu điểm chính,
      nghe hiểu khái quát, trả lời nhanh, nghe hiểu tổng hợp, nghe hiểu diễn đạt
  lang values: cn, de, en, es, fr, id, ko, my, pt, ru, tw, vn

Why this crawler yields no questions
------------------------------------
The question endpoints answer anonymous requests (HTTP 200, no token needed) but every payload is an
encrypted envelope {iv, authTag, encryptedAesKey, encryptedData}. The app decrypts it client-side
(QuestionDecryptService): RSA-OAEP-unwrap the AES key with a private key that is itself shipped
AES-GCM-encrypted in /vi/assets/members/member.json (key = sha256(member[0].name), iv = member[2].id,
tag = member[3].id, ciphertext = member[0].id + member[1].id), then AES-GCM-decrypt encryptedData.
That is a deliberate anti-scraping protection, so this script does NOT reproduce it; it only probes,
caches the raw responses and reports the envelope. Decide separately whether to go further.

The mock-exam pages (/*/official-test) are disallowed by https://jlpt.migii.net/robots.txt and were not touched.

Run:  cd D:/JLPT-app && python -I scripts/crawl/migii.py
"""
import json
import os
import site
import sys
import time

sys.path.append(site.getusersitepackages())  # python -I hides the user site where requests lives
sys.stdout.reconfigure(encoding="utf-8")

import requests  # noqa: E402

SOURCE = "migii"
LEVEL = 3
ROOT = r"D:/JLPT-app"
CACHE = os.path.join(ROOT, "crawl", "cache", SOURCE)
OUT = os.path.join(ROOT, "crawl", "raw", f"{SOURCE}.json")
API = "https://jlpt.migii.net/api/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JLPT-study-bot/0.1 (personal study tool)"
SLEEP = 1.0
PROBE_KIND = "cách đọc kanji"

os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})


class StopCrawl(Exception):
    pass


def fetch_json(url: str, cache_name: str, params: dict | None = None) -> dict:
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    r = session.get(url, params=params, timeout=60)
    if r.status_code in (401, 403, 429):
        raise StopCrawl(f"HTTP {r.status_code} for {r.url}")
    data = r.json()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    time.sleep(SLEEP)
    return data


def is_encrypted_envelope(d) -> bool:
    return isinstance(d, dict) and {"iv", "authTag", "encryptedAesKey", "encryptedData"} <= set(d)


def main() -> None:
    questions: list[dict] = []
    try:
        counts = fetch_json(API + "/question/question/countQuestionDetail", "countQuestionDetail.json")
        n3 = {}
        for tag in counts.get("Questions", {}).get("tag", []):
            for d in tag.get("detail", []):
                if d.get("level") == LEVEL:
                    n3[tag["tag"]] = d.get("count")
        print(f"countQuestionDetail (public): N{LEVEL} question bank size per tag = {n3}")
        kinds_n3 = {k["kind"]: d["count"] for k in counts.get("Questions", {}).get("kind", [])
                    for d in k.get("detail", []) if d.get("level") == LEVEL}
        if kinds_n3:
            print(f"  per kind: {kinds_n3}")

        probe = fetch_json(API + "question/v2/practice", f"practice_probe_n{LEVEL}.json",
                           params={"kind": PROBE_KIND, "lang": "vn", "level": LEVEL, "limit": 2})
        data = probe.get("data")
        if is_encrypted_envelope(data):
            print("\nquestion/v2/practice -> HTTP 200 without auth, but payload is an encrypted envelope:")
            print("  keys:", sorted(data.keys()),
                  f"| encryptedData {len(data['encryptedData']) // 2} bytes, encryptedAesKey "
                  f"{len(data['encryptedAesKey']) // 2} bytes (RSA-2048 OAEP), AES-GCM iv/tag")
            print("  Not decrypting (client-side anti-scraping protection, see module docstring). "
                  "No questions extracted.")
        else:
            print("\nUnexpected: payload is not the known encrypted envelope; inspect", probe)
    except StopCrawl as e:
        print("STOP:", e)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
    print(f"\nWrote {len(questions)} questions -> {OUT}")
    print("per section/type: {}")
    print("with explanation: 0")
    print("dropped: all N3 practice content unreachable without reproducing the app's payload decryption")


if __name__ == "__main__":
    main()
