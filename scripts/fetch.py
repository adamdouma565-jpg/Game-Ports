import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone

TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
QUERIES = ["topic:android-port", "topic:game-port android", "topic:decompilation android",
  '"android port" in:name,description', '"port to android" in:name,description',
  "zelda android port in:name,description", "resident evil android port in:name,description",
  "generals android port in:name,description", "mario android port in:name,description"]
MIN_STARS, MAX_REPOS = 5, 300
SPAM = re.compile(r"mod\s*apk|cracked|\bcrack\b|free\s*download|unlimited|hack(ed)?\b|generator|premium\s*unlocked|apk\s*download|torrent|warez|pirat(ed|e|ebay)|nulled|leaked", re.I)
NEEDS = re.compile(r"(own|original|legal(ly)?|your)\s+(copy|copies|game\s*files?|assets?|rom|iso|data)|requires?\s+(the\s+)?(original|game)\s+(game\s+)?(files?|assets?|data)|bring\s+your\s+own|you\s+(must|need\s+to)\s+(own|have|provide)|no\s+(game\s+)?assets?\s+(are\s+)?(included|provided)", re.I)

def get(url, accept="application/vnd.github+json"):
    h = {"Accept": accept, "User-Agent": "ports-tracker", "X-GitHub-Api-Version": "2022-11-28"}
    if TOKEN: h["Authorization"] = "Bearer " + TOKEN
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        print("skip", url, e); return None

def specs(t):
    s = {}
    m = re.search(r"android\s*(?:os\s*|version\s*)?(\d+(?:\.\d+)?)\s*(?:\+|or\s+(?:higher|above|later|newer)|and\s+(?:up|above|higher))", t, re.I) or re.search(r"min(?:imum)?\s*(?:android|sdk)[^\n]{0,30}?(\d+(?:\.\d+)?)", t, re.I)
    if m: s["android"] = "Android " + m.group(1) + "+"
    m = re.search(r"(\d+)\s*GB\s*(?:of\s*)?RAM", t, re.I) or re.search(r"RAM[^\n]{0,25}?(\d+)\s*GB", t, re.I)
    if m: s["ram"] = m.group(1) + " GB"
    g = []
    if re.search(r"vulkan", t, re.I): g.append("Vulkan")
    m = re.search(r"OpenGL\s*ES\s*(\d(?:\.\d)?)", t, re.I)
    if m: g.append("OpenGL ES " + m.group(1))
    if g: s["gpu"] = " / ".join(g)
    tl = t.lower(); abis = []
    if re.search(r"arm64|aarch64|armv8", tl): abis.append("arm64")
    if re.search(r"armeabi|armv7|arm32|arm\s*32|32[- ]?bit\s+arm", tl): abis.append("armv7")
    if "x86_64" in tl: abis.append("x86_64")
    if abis: s["abis"] = abis; s["arch"] = ", ".join({"arm64": "arm64-v8a", "armv7": "armeabi-v7a (32-bit)", "x86_64": "x86_64"}[x] for x in abis)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB)\s*(?:of\s*)?(?:free\s*)?(?:storage|space|disk)", t, re.I)
    if m: s["storage"] = m.group(1) + " " + m.group(2).upper()
    m = re.findall(r"snapdragon\s*\d{3,4}\+?|snapdragon\s*[5-8]s?\s*(?:gen\s*\d|elite)|exynos\s*\d{3,4}|dimensity\s*\d{3,4}\w?|helio\s*[gp]\d{2,3}\w?|tensor\s*g\d|adreno\s*\d{3}|mali[- ]?[gt]\d{2,3}", t, re.I)
    if m: s["soc"] = ", ".join(dict.fromkeys(re.sub(r"\s+", " ", x.strip().title()) for x in m[:6]))[:70]
    if re.search(r"controller|gamepad|joystick", t, re.I): s["controller"] = True
    return s

KNOWN = [
 (r"ship of harkinian|shipwright|ocarina of time|\boot\b|\bsoh\b", "The Legend of Zelda: Ocarina of Time"),
 (r"2ship|majora", "The Legend of Zelda: Majora's Mask"),
 (r"twilight princess", "The Legend of Zelda: Twilight Princess"),
 (r"wind waker", "The Legend of Zelda: The Wind Waker"),
 (r"skyward sword", "The Legend of Zelda: Skyward Sword"),
 (r"breath of the wild|\bbotw\b", "The Legend of Zelda: Breath of the Wild"),
 (r"resident evil 4|\bre4\b", "Resident Evil 4"), (r"resident evil 2|\bre2\b", "Resident Evil 2"),
 (r"zero hour|generals", "Command & Conquer: Generals"), (r"red alert", "Command & Conquer: Red Alert"),
 (r"super mario 64|\bsm64\b", "Super Mario 64"), (r"mario kart", "Mario Kart"),
 (r"diablo ii|diablo 2|\bd2r\b", "Diablo II"), (r"dragon ball z.*burst|dbz.*burst", "Dragon Ball Z: Burst Limit"),
 (r"half-life|half life", "Half-Life"), (r"\bquake\b", "Quake"), (r"\bdoom\b", "DOOM"),
]
def game_title(name, desc, topics):
    blob = " ".join([name or "", desc or "", " ".join(topics or [])])
    for pat, title in KNOWN:
        if re.search(pat, blob, re.I): return title
    d = (desc or "").strip()
    m = re.search(r"(?i:port(?:ed)?\s+of|port\s+for)\s+(?:the\s+)?([A-Z0-9][\w:'&\-\. ]{2,50}?)(?:(?i:\s+(?:to|for|on)\s+android)|[,.;(]|\s-\s|$)", d)
    if m: return m.group(1).strip(" :-")
    m = re.match(r"([A-Z0-9][\w:'&\-\. ]{2,50}?)\s+(?:android\s+|native\s+)?(?:port|recomp\w*|decomp\w*|remake|fork)\b", d, re.I)
    if m: return m.group(1).strip(" :-")
    w = re.sub(r"(?i)\b(android|port|mobile|apk|recomp\w*|decomp\w*|fork|native|for|app)\b", " ", re.sub(r"([a-z])([A-Z])", r"\1 \2", re.sub(r"[-_.]+", " ", name or "")))
    return " ".join(w.split()).title() or name

def thumb(readme, fn, branch):
    for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)|<img[^>]+src=[\"']([^\"']+)", readme):
        u = (m.group(1) or m.group(2) or "").strip()
        if not re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", u, re.I): continue
        if re.search(r"shields\.io|badge|travis|workflows|codecov|logo|icon|sponsor|donate|patreon|paypal|ko-fi|discord", u, re.I): continue
        if u.startswith("//"): u = "https:" + u
        if not u.startswith("http"): u = "https://raw.githubusercontent.com/%s/%s/%s" % (fn, branch, u.lstrip("./"))
        return u
    return None


now = datetime.now(timezone.utc).isoformat()
try:
    prev = {x["id"]: x.get("first_seen") for x in json.load(open("data/ports.json", encoding="utf-8")).get("items", [])}
except Exception:
    prev = {}
repos = {}
for q in QUERIES:
    for page in (1, 2, 3):
        u = API + "/search/repositories?" + urllib.parse.urlencode({"q": q + " fork:false stars:>=%d" % MIN_STARS, "sort": "updated", "order": "desc", "per_page": 100, "page": page})
        txt = get(u); time.sleep(2.5)
        if not txt: break
        found = json.loads(txt).get("items", [])
        for r in found: repos[r["full_name"]] = r
        if len(found) < 100: break

ok = [r for r in repos.values() if not r.get("disabled") and not SPAM.search((r["name"] or "") + " " + (r["description"] or ""))]
ok.sort(key=lambda r: r["stargazers_count"], reverse=True)
out = []
for r in ok[:MAX_REPOS]:
    fn = r["full_name"]
    readme = (get(API + "/repos/" + fn + "/readme", "application/vnd.github.raw+json") or "")[:20000]
    rel, stage, dl = None, "nobuild", 0
    j = get(API + "/repos/" + fn + "/releases?per_page=5")
    rels = [x for x in (json.loads(j) if j else []) if not x.get("draft") and x.get("tag_name")]
    if rels:
        x = rels[0]
        rel = {"tag": x["tag_name"], "date": x.get("published_at") or x.get("created_at"), "url": x.get("html_url")}
        label = x["tag_name"] + " " + (x.get("name") or "")
        head = readme[:3000]
        if re.search(r"alpha|\ba\d+\b|\bdev\b|experimental|\bwip\b", label, re.I): stage = "alpha"
        elif x.get("prerelease") or re.search(r"beta|\brc\d*\b|preview|nightly|snapshot|pre-?release", label, re.I): stage = "beta"
        elif re.match(r"v?0\.\d", x["tag_name"]): stage = "beta"
        elif re.search(r"\balpha\b", head, re.I): stage = "alpha"
        elif re.search(r"\bbeta\b|work.in.progress|\bwip\b|early.access", head, re.I): stage = "beta"
        else: stage = "stable"
        dl = sum(a.get("download_count", 0) for y in rels for a in y.get("assets", []))
    out.append({"id": fn, "name": r["name"], "owner": r["owner"]["login"], "url": r["html_url"], "desc": (r["description"] or "")[:300],
      "stars": r["stargazers_count"], "lang": r["language"], "license": (r.get("license") or {}).get("spdx_id"),
      "pushed": r["pushed_at"], "created": r["created_at"], "archived": r["archived"], "topics": r.get("topics", []),
      "assets": bool(NEEDS.search(readme)), "specs": specs(readme), "game": game_title(r["name"], r["description"], r.get("topics", [])), "avatar": r["owner"]["avatar_url"], "thumb": thumb(readme, fn, r.get("default_branch") or "main"), "release": rel, "stage": stage, "downloads": dl, "first_seen": prev.get(fn) or (r["created_at"] if not prev else now)})
    time.sleep(0.1)

if not out: raise SystemExit("no data fetched; keeping previous file")
os.makedirs("data", exist_ok=True)
json.dump({"updated": datetime.now(timezone.utc).isoformat(), "count": len(out), "items": out}, open("data/ports.json", "w", encoding="utf-8"), ensure_ascii=False)
print("saved", len(out))
