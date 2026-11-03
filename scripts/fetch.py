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
    a = [x for x in ("arm64-v8a", "armeabi-v7a", "x86_64", "aarch64") if x in t.lower()]
    if a: s["arch"] = ", ".join(a)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB)\s*(?:of\s*)?(?:free\s*)?(?:storage|space|disk)", t, re.I)
    if m: s["storage"] = m.group(1) + " " + m.group(2).upper()
    m = re.findall(r"snapdragon\s*\d+\w*|exynos\s*\d+|dimensity\s*\d+\w*|helio\s*\w+|adreno\s*\d+|mali-?\w+", t, re.I)
    if m: s["soc"] = ", ".join(dict.fromkeys(x.strip() for x in m))[:60]
    if re.search(r"controller|gamepad|joystick", t, re.I): s["controller"] = True
    return s

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
        elif re.search(r"\balpha\b", head, re.I): stage = "alpha"
        elif re.search(r"\bbeta\b|work.in.progress|\bwip\b|early.access", head, re.I): stage = "beta"
        else: stage = "stable"
        dl = sum(a.get("download_count", 0) for y in rels for a in y.get("assets", []))
    out.append({"id": fn, "name": r["name"], "owner": r["owner"]["login"], "url": r["html_url"], "desc": (r["description"] or "")[:300],
      "stars": r["stargazers_count"], "lang": r["language"], "license": (r.get("license") or {}).get("spdx_id"),
      "pushed": r["pushed_at"], "created": r["created_at"], "archived": r["archived"], "topics": r.get("topics", []),
      "assets": bool(NEEDS.search(readme)), "specs": specs(readme), "release": rel, "stage": stage, "downloads": dl, "first_seen": prev.get(fn) or (r["created_at"] if not prev else now)})
    time.sleep(0.1)

if not out: raise SystemExit("no data fetched; keeping previous file")
os.makedirs("data", exist_ok=True)
json.dump({"updated": datetime.now(timezone.utc).isoformat(), "count": len(out), "items": out}, open("data/ports.json", "w", encoding="utf-8"), ensure_ascii=False)
print("saved", len(out))
