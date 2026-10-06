"""Shared helpers for the ref dataset builders (run with `python -I`)."""
import os, sys, json, time, hashlib
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

# `python -I` skips the user site-packages where requests/bs4/lxml live; add it back.
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    import site
    sys.path.append(site.getusersitepackages())
    import requests  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(ROOT, "crawl", "raw")
CACHE_DIR = os.path.join(ROOT, "crawl", "cache", "ref")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,vi;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _cache_path(key, ext):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    return os.path.join(CACHE_DIR, f"{h}{ext}")


def fetch(url, sleep=0.0, ext=".bin", timeout=40):
    """GET with a disk cache; returns bytes or None."""
    p = _cache_path("GET " + url, ext)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    r = None
    for attempt in range(6):
        try:
            r = SESSION.get(url, timeout=timeout)
        except Exception as e:
            print("  fetch error", url, e)
            r = None
        if sleep:
            time.sleep(sleep)
        if r is not None and r.status_code == 200:
            break
        # 202/429/5xx: back off and retry
        time.sleep(4.0 * (attempt + 1))
    if r is None or r.status_code != 200:
        print("  HTTP", None if r is None else r.status_code, url)
        return None
    with open(p, "wb") as f:
        f.write(r.content)
    return r.content


def post_json(url, body, sleep=0.25, timeout=30):
    """POST JSON with a disk cache keyed on url+body; returns parsed JSON or None."""
    key = "POST " + url + " " + json.dumps(body, ensure_ascii=False, sort_keys=True)
    p = _cache_path(key, ".json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        r = SESSION.post(url, json=body, timeout=timeout)
    except Exception as e:
        print("  post error", body, e)
        return None
    if sleep:
        time.sleep(sleep)
    if r.status_code != 200:
        print("  HTTP", r.status_code, body)
        return None
    try:
        data = r.json()
    except Exception:
        return None
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def dump(name, data):
    out = os.path.join(RAW_DIR, name)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"wrote {out} ({len(data)} items)")
    return out
