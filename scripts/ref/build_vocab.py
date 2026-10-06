"""Build crawl/raw/ref_vocab.json: JLPT N3 vocabulary reference.

Source (word/reading/English): elzup/jlpt-word-list  src/n3.csv  (MIT, derived from the
Tanos JLPT lists).  Vietnamese meaning + part of speech: Mazii javi dictionary API
(POST https://mazii.net/api/search), rate-limited to ~4 req/s and cached on disk.
Run from D:/JLPT-app:  python -I scripts/ref/build_vocab.py
"""
import sys, os, csv, io, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, post_json, dump

SRC = "https://raw.githubusercontent.com/elzup/jlpt-word-list/master/src/n3.csv"
MAZII = "https://mazii.net/api/search"

# Mazii "kind" abbreviations (JMdict style) -> compact POS label
KIND_MAP = [
    (r"\bvs\b", "n/vs"), (r"\bv1\b|\bv5\w*\b|\bvk\b|\bvz\b|\bv[st]-\w+", "v"),
    (r"adj-i|adj-ix", "adj-i"), (r"adj-na", "adj-na"), (r"adj-no", "n"), (r"adj-t|adj-f|adj-pn", "adj"),
    (r"\badv\b|adv-to", "adv"), (r"\bn\b|n-adv|n-t|n-suf|n-pref", "n"), (r"\bpn\b", "pron"),
    (r"\bconj\b", "conj"), (r"\bprt\b", "prt"), (r"\bint\b", "int"), (r"\bexp\b", "exp"),
    (r"\bsuf\b|\bpref\b|\bctr\b", "suf/pref"), (r"\bnum\b", "num"),
]


def pos_from_kind(kind):
    if not kind:
        return None
    if isinstance(kind, (list, tuple)):
        kind = ", ".join(str(x) for x in kind)
    k = str(kind).lower()
    if re.search(r"\bn\b", k) and re.search(r"\bvs\b", k):
        return "n/vs"
    for pat, lab in KIND_MAP:
        if re.search(pat, k):
            return lab
    return None


def pos_heuristic(word, meaning_en):
    m = (meaning_en or "").lower()
    if re.match(r"^to \w", m):
        return "v"
    if word.endswith("い") and re.search(r"[\u4e00-\u9fff\u3041-\u3096]い$", word) and not word.endswith("しい") is False:
        pass
    if word.endswith("い") and ("-" in m or re.search(r"(ful|ous|ive|ic|ish|y)\b", m)):
        return "adj-i"
    if word.endswith("しい"):
        return "adj-i"
    if re.search(r"\bsuffix\b|\bprefix\b|\bcounter\b", m):
        return "suf/pref"
    if word.endswith("に") or word.endswith("と") or m.endswith("ly"):
        return "adv"
    return "n"


def normalize_word(word, reading):
    """Clean quirks of the source list: '(かん)' = interjection marker, 'A; B' alt spellings, '～' affix mark."""
    forced_pos = None
    if "(かん)" in word or "（かん）" in word:
        word = re.sub(r"\s*[（(]かん[)）]", "", word).strip()
        reading = re.sub(r"\s*[（(]かん[)）]", "", reading).strip()
        forced_pos = "int"
    if ";" in word or "；" in word:
        word = re.split(r"[;；]", word)[0].strip()
        reading = re.split(r"[;；]", reading)[0].strip()
    if word.startswith("～") or word.startswith("〜"):
        word = word.lstrip("～〜").strip()
        reading = reading.lstrip("～〜").strip()
        forced_pos = "suf/pref"
    if word.endswith("～") or word.endswith("〜"):
        word = word.rstrip("～〜").strip()
        reading = reading.rstrip("～〜").strip()
        forced_pos = "suf/pref"
    return word, reading, forced_pos


def load_source():
    raw = fetch(SRC, ext=".csv")
    if raw is None:
        sys.exit("could not download source csv")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    out, seen = [], set()
    for r in rows:
        word = (r.get("expression") or "").strip()
        reading = (r.get("reading") or "").strip()
        meaning = (r.get("meaning") or "").strip()
        if not word or not meaning:
            continue
        if not reading:
            reading = word
        word, reading, forced_pos = normalize_word(word, reading)
        key = (word, reading)
        if key in seen:
            continue
        seen.add(key)
        out.append({"word": word, "reading": reading, "meaning_en": meaning, "forced_pos": forced_pos})
    return out


# Manual fixes for words where Mazii's first sense is misleading (homographs / prefixes).
OVERRIDES = {
    ("不", "ふ"): "bất…, không… (tiền tố phủ định)", ("不", "ぶ"): "bất…, không… (tiền tố phủ định)",
    ("描く", "えがく"): "vẽ; miêu tả", ("描く", "かく"): "vẽ; miêu tả",
    ("注ぐ", "そそぐ"): "rót; đổ vào; dồn (sức, tâm trí)", ("注ぐ", "つぐ"): "rót (nước, rượu)",
    ("抱く", "いだく"): "ôm ấp; ấp ủ (ý nghĩ, tình cảm)", ("抱く", "だく"): "ôm; bế",
    ("得る", "える"): "đạt được; có được; có thể", ("得る", "うる"): "đạt được; có được; có thể",
    ("為る", "する"): "làm; thực hiện", ("為る", "なる"): "trở thành; trở nên",
    ("生", "せい"): "sự sống; sinh (sinh viên, học sinh)", ("生", "なま"): "tươi sống; chưa qua chế biến",
    ("円", "えん"): "yên (đơn vị tiền Nhật); hình tròn", ("円", "まる"): "hình tròn; vòng tròn",
    ("角", "かく"): "góc (hình học)", ("角", "すみ"): "góc (phòng, đường)",
    ("管", "かん"): "ống; ống dẫn", ("管", "くだ"): "ống; ống dẫn",
    ("球", "きゅう"): "quả cầu; hình cầu; bóng", ("球", "たま"): "quả bóng; quả cầu",
    ("額", "がく"): "số tiền; khung (tranh)", ("額", "ひたい"): "trán",
    ("品", "しな"): "hàng hóa; đồ vật; món", ("品", "ひん"): "phẩm chất; sự thanh lịch",
    ("数", "すう"): "số; con số", ("数", "かず"): "số; số lượng",
    ("末", "すえ"): "cuối; kết cục", ("末", "まつ"): "cuối (tháng, năm)",
    ("音", "おん"): "âm; âm thanh", ("音", "ね"): "tiếng; âm thanh (êm tai)",
    ("金", "かね"): "tiền; kim loại", ("金", "きん"): "vàng; kim loại",
    ("柄", "え"): "cán; chuôi", ("柄", "がら"): "hoa văn; vóc dáng; tính cách",
    ("縁", "えん"): "duyên; mối quan hệ", ("縁", "ふち"): "mép; rìa; viền",
    ("節", "せつ"): "mùa; đoạn; khi", ("節", "ふし"): "đốt; khớp; giai điệu",
    ("対", "たい"): "đối với; tỉ số (… đối …)", ("対", "つい"): "cặp; đôi",
    ("分", "ぶ"): "phần; phân (tỉ lệ)", ("分", "ぶん"): "phần; phân chia; phận",
    ("無", "む"): "vô; không có", ("無", "ぶ"): "vô; không có",
    ("他", "た"): "khác; cái khác", ("他", "ほか"): "khác; nơi khác; ngoài ra",
    ("上", "うわ"): "bên trên; mặt ngoài (tiền tố)", ("上", "かみ"): "phần trên; thượng (nguồn, tập)",
    ("上", "じょう"): "thượng; phần trên; tập thượng", ("下", "しも"): "phần dưới; hạ (nguồn, tập)",
    ("下", "げ"): "hạ; phần dưới; tập hạ", ("後", "ご"): "sau; sau khi", ("後", "のち"): "sau đó; về sau",
    ("方々", "かたがた"): "các vị; quý vị", ("方々", "ほうぼう"): "khắp nơi; đây đó",
    ("行き", "いき"): "sự đi; chuyến đi (đến…)", ("行き", "ゆき"): "sự đi; chuyến đi (đến…)",
    ("唯", "ただ"): "chỉ; chỉ là; miễn phí", ("唯", "たった"): "chỉ; vẻn vẹn",
    ("と", "と"): "và; với; rằng; khi… thì… (trợ từ)",
    ("申し込む", "もうしこむ"): "đăng ký; xin; đề nghị; cầu hôn",
    ("しまった", "しまった"): "chết rồi!; hỏng rồi!; thôi chết!",
    ("すみません", "すみません"): "xin lỗi; cảm ơn (làm phiền)",
    ("よろしく", "よろしく"): "mong được giúp đỡ; gửi lời hỏi thăm",
    ("はあ", "はあ"): "dạ; hả?; ôi (thở dài)",
    ("可愛そう", "かわいそう"): "đáng thương; tội nghiệp",
    ("観", "かん"): "…quan (quan điểm, cách nhìn): 人生観, 世界観",
    ("敗", "はい"): "…bại, …thua (đếm số trận thua)",
    ("あいにく", "あいにく"): "không may; thật đáng tiếc",
    ("あちこち", "あちこち"): "đây đó; khắp nơi",
    ("あんまり", "あんまり"): "không… lắm; quá mức",
    ("いずれ", "いずれ"): "sớm muộn gì; một ngày nào đó; cái nào",
    ("いつでも", "いつでも"): "bất cứ lúc nào; lúc nào cũng",
    ("およそ", "およそ"): "khoảng; đại khái; nói chung",
    ("そして", "そして"): "và; rồi thì; sau đó",
    ("そのうえ", "そのうえ"): "hơn nữa; thêm vào đó",
    ("そのまま", "そのまま"): "cứ như vậy; giữ nguyên",
    ("たびたび", "たびたび"): "nhiều lần; thường xuyên",
    ("つまり", "つまり"): "tóm lại; tức là",
    ("ぶつける", "ぶつける"): "đâm vào; va vào; ném trúng",
    ("まさか", "まさか"): "không lẽ; chẳng lẽ; làm gì có chuyện",
}
POS_OVERRIDES = {("と", "と"): "prt", ("可愛そう", "かわいそう"): "adj-na", ("あんまり", "あんまり"): "adv"}
POS_WORDS = {"noun": "n", "verb": "v", "adjective": "adj-i", "adverb": "adv", "pronoun": "pron",
             "conjunction": "conj", "interjection": "int", "particle": "prt"}


def _candidates(word, reading):
    """Mazii entries whose headword matches; reading-matching ones first."""
    data = post_json(MAZII, {"dict": "javi", "type": "word", "query": word, "limit": 3, "page": 1}, sleep=0.25)
    items = (data or {}).get("data") or []
    exact = [it for it in items if it.get("word") == word]
    good = [it for it in exact if reading in (it.get("phonetic") or "").split()]
    if not good and exact and reading != word:
        # second stage: more results, and a query by reading, to find the right homograph
        for q in (word, reading):
            data = post_json(MAZII, {"dict": "javi", "type": "word", "query": q, "limit": 20, "page": 1}, sleep=0.25)
            for it in (data or {}).get("data") or []:
                if it.get("word") == word and reading in (it.get("phonetic") or "").split():
                    good.append(it)
            if good:
                break
    if not good and not exact:
        good = [it for it in items if word in (it.get("phonetic") or "").split() or it.get("word") == reading]
    return good or exact


def mazii_lookup(word, reading):
    """Returns (meaning_vi, kind, synset_pos)."""
    cands = _candidates(word, reading)
    if not cands:
        return OVERRIDES.get((word, reading)), None, None
    best = cands[0]
    means = [m for m in (best.get("means") or []) if (m.get("mean") or "").strip()]
    kind = None
    for m in means:
        if m.get("kind"):
            kind = m["kind"]
            break
    spos = None
    for sset in best.get("synsets") or []:
        if sset.get("pos"):
            spos = sset["pos"]
            break
    vi = OVERRIDES.get((word, reading))
    if not vi:
        # up to 3 distinct senses from the entry, joined with "; "
        senses = []
        for m in means:
            for part in re.split(r"\s*;\s*", m["mean"].strip().rstrip(" .")):
                part = part.strip()
                if part and part.lower() not in [x.lower() for x in senses]:
                    senses.append(part)
                if len(senses) >= 3:
                    break
            if len(senses) >= 3:
                break
        vi = "; ".join(senses) or (best.get("short_mean") or "").strip() or None
    return vi, kind, spos


def main():
    words = load_source()
    print("source rows:", len(words))
    n_vi = 0
    n_kind = 0
    for i, w in enumerate(words):
        vi, kind, spos = mazii_lookup(w["word"], w["reading"])
        if vi:
            n_vi += 1
        pos = pos_from_kind(kind)
        if not pos and spos:
            pos = POS_WORDS.get(str(spos).lower())
            if pos == "adj-i" and not w["word"].endswith("い"):
                pos = "adj-na"
        if w.get("forced_pos"):
            pos = w["forced_pos"]
        if (w["word"], w["reading"]) in POS_OVERRIDES:
            pos = POS_OVERRIDES[(w["word"], w["reading"])]
        if pos:
            n_kind += 1
        else:
            pos = pos_heuristic(w["word"], w["meaning_en"])
        w["meaning_vi"] = vi
        w["pos"] = pos
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(words)}  vi={n_vi}")
    # merge homographs that share the same English gloss (e.g. 日本 にほん/にっぽん) -> one entry
    merged = {}
    for w in words:
        key = (w["word"], w["meaning_en"])
        if key in merged:
            m = merged[key]
            if w["reading"] not in m["reading"].split("・"):
                m["reading"] += "・" + w["reading"]
            if not m["meaning_vi"] and w["meaning_vi"]:
                m["meaning_vi"] = w["meaning_vi"]
            continue
        merged[key] = dict(w)
    out = [{"word": w["word"], "reading": w["reading"], "meaning_vi": w["meaning_vi"],
            "meaning_en": w["meaning_en"], "pos": w["pos"], "level": "N3"} for w in merged.values()]
    print(f"merged {len(words) - len(out)} homograph duplicates")
    # validation
    for o in out:
        for k in ("word", "reading", "meaning_en", "pos"):
            assert o[k], (k, o)
    print(f"meaning_vi coverage: {sum(1 for o in out if o['meaning_vi'])}/{len(out)}  pos from Mazii/overrides: {n_kind}/{len(words)} rows")
    dump("ref_vocab.json", out)


if __name__ == "__main__":
    main()
