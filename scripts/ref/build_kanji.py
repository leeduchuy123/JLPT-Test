"""Build crawl/raw/ref_kanji.json: JLPT N3 kanji reference (~367 kanji).

Source: davidluzgouveia/kanji-data kanji.json (KANJIDIC2-derived; kanji with jlpt_new == 3)
for on/kun/strokes/English meanings.  Vietnamese: Mazii javi kanji API (hanviet = `mean`,
meaning_vi from `detail`, example compounds).  Examples prefer N3 vocabulary from
crawl/raw/ref_vocab.json (words containing the kanji), topped up from Mazii to 4.
Run from D:/JLPT-app (after build_vocab.py):  python -I scripts/ref/build_kanji.py
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, post_json, dump, RAW_DIR

KD = "https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json"
MAZII = "https://mazii.net/api/search"
HANVIET_FIX = {"込": "VÀO (quốc tự, không có âm Hán Việt)"}
KATA = {chr(c): chr(c - 0x60) for c in range(0x30A1, 0x30F7)}  # katakana -> hiragana


def hira(s):
    return "".join(KATA.get(ch, ch) for ch in s)


def mazii_kanji(k):
    d = post_json(MAZII, {"dict": "javi", "type": "kanji", "query": k, "limit": 1, "page": 1}, sleep=0.25)
    if not d:
        return None
    for r in d.get("results") or []:
        if r.get("kanji") == k:
            return r
    return None


def vi_from_detail(detail):
    """'1. trải qua; đi qua\nVD: ...\n2. quản lý; điều hành\nVD: ...' -> 'trải qua; đi qua; quản lý; điều hành'"""
    if not detail:
        return None
    senses = []
    for line in detail.split("\n"):
        line = line.strip()
        m = re.match(r"^\d+\.\s*(.+)$", line)
        if m:
            t = m.group(1).strip().rstrip(";.").strip()
            if t and t not in senses:
                senses.append(t)
    if not senses:
        t = detail.split("\n")[0].strip()
        return t or None
    return "; ".join(senses[:3])


def main():
    kd = json.loads(fetch(KD, ext=".json").decode("utf-8"))
    n3 = sorted([(k, v) for k, v in kd.items() if v.get("jlpt_new") == 3],
                key=lambda kv: (kv[1].get("freq") or 9999, kv[0]))
    print("kanji-data N3:", len(n3))
    vocab = []
    vp = os.path.join(RAW_DIR, "ref_vocab.json")
    if os.path.exists(vp):
        with open(vp, encoding="utf-8") as f:
            vocab = json.load(f)
    else:
        print("WARNING: ref_vocab.json missing; examples will come from Mazii only")
    out, seen = [], set()
    n_han = n_vi = n_ex = 0
    for i, (k, v) in enumerate(n3):
        if k in seen:
            continue
        seen.add(k)
        mz = mazii_kanji(k) or {}
        on = [hira(x) for x in (v.get("readings_on") or [])]
        kun = list(v.get("readings_kun") or [])
        if not on and mz.get("on"):
            on = [hira(x) for x in mz["on"].split()]
        if not kun and mz.get("kun"):
            kun = mz["kun"].split()
        hanviet = (mz.get("mean") or "").strip() or HANVIET_FIX.get(k)
        meaning_vi = vi_from_detail(mz.get("detail"))
        # examples: N3 vocab containing the kanji first (shorter words first), then Mazii
        exs, used = [], set()
        for w in sorted((w for w in vocab if k in w["word"]), key=lambda w: (len(w["word"]), w["word"])):
            if w["word"] in used:
                continue
            used.add(w["word"])
            exs.append({"word": w["word"], "reading": w["reading"], "meaning_vi": (w.get("meaning_vi") or w.get("meaning_en")).rstrip(" .").strip()})
            if len(exs) >= 4:
                break
        if len(exs) < 4:
            for e in mz.get("examples") or []:
                w = (e.get("w") or "").strip()
                if not w or w in used or not e.get("m"):
                    continue
                used.add(w)
                exs.append({"word": w, "reading": (e.get("p") or "").strip(), "meaning_vi": e["m"].strip().rstrip(" .").strip()})
                if len(exs) >= 4:
                    break
        n_han += bool(hanviet); n_vi += bool(meaning_vi); n_ex += bool(exs)
        out.append({"kanji": k, "on": on, "kun": kun, "meaning_vi": meaning_vi,
                    "meaning_en": ", ".join(v.get("meanings") or []), "hanviet": hanviet,
                    "strokes": v.get("strokes") or (int(mz["stroke_count"]) if mz.get("stroke_count") else None),
                    "level": "N3", "examples": exs})
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(n3)}")
    for o in out:
        assert o["kanji"] and o["meaning_en"] and o["strokes"] and (o["on"] or o["kun"]), o
    print(f"kanji: {len(out)}  hanviet: {n_han}  meaning_vi: {n_vi}  with examples: {n_ex}  "
          f"<4 examples: {sum(1 for o in out if len(o['examples']) < 4)}")
    dump("ref_kanji.json", out)


if __name__ == "__main__":
    main()
