import os, re, json, time, html
import feedparser, requests

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE, "config.json")
SEEN_PATH = os.path.join(BASE, "seen.json")
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_seen(seen):
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(seen)[-5000:], f)


def discount_of(text):
    nums = [int(n) for n in re.findall(r"(\d{1,2})\s*%", text)]
    return max(nums) if nums else 0


def add_affiliate(url, cfg):
    tag = cfg.get("affiliate", {}).get("amazon_tag", "")
    if tag and re.search(r"amazon\.[a-z.]+/", url):
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}tag={tag}"
    return url


def passes(title, cfg):
    t = title.lower()
    inc = [k.lower() for k in cfg.get("keywords_include", [])]
    exc = [k.lower() for k in cfg.get("keywords_exclude", [])]
    if inc and not any(k in t for k in inc):
        return False
    if any(k in t for k in exc):
        return False
    return discount_of(title) >= cfg.get("min_discount_percent", 0)


def send(text):
    if not TOKEN or not CHAT_ID:
        print(text)
        return
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=20,
    )
    if r.status_code == 429:
        time.sleep(r.json().get("parameters", {}).get("retry_after", 5))


def run_once(cfg, seen, first_run):
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        try:
            feed = feedparser.parse(src["url"], agent="Mozilla/5.0 DealsBot")
        except Exception as e:
            print("error", src["name"], e)
            continue
        for e in reversed(feed.entries[:25]):
            uid = e.get("id") or e.get("link")
            if not uid or uid in seen:
                continue
            seen.add(uid)
            title = html.unescape(e.get("title", "")).strip()
            if first_run or not passes(title, cfg):
                continue
            link = add_affiliate(e.get("link", ""), cfg)
            send(f"🔥 <b>{html.escape(title)}</b>\n📍 {html.escape(src['name'])}\n{link}")
            time.sleep(1)
    save_seen(seen)


def main():
    seen = set(load_json(SEEN_PATH, []))
    first_run = not seen
    if os.environ.get("RUN_ONCE"):
        run_once(load_json(CFG_PATH, {"sources": []}), seen, first_run)
        return
    while True:
        cfg = load_json(CFG_PATH, {"sources": []})
        run_once(cfg, seen, first_run)
        first_run = False
        time.sleep(cfg.get("interval_seconds", 120))


if __name__ == "__main__":
    main()
