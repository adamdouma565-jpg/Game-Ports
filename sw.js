const CACHE = "game-ports-v2";
const SHELL = ["./", "./index.html", "./manifest.json", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});

// الصفحة نفسها: الشبكة أولًا ثم النسخة المخزنة. الأخبار (من نطاقات أخرى) لا تُخزَّن.
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy));
      return r;
    }).catch(() => caches.match(e.request).then(m => m || caches.match("./index.html")))
  );
});

const TXT = {ar:{n:"🆕 بورت جديد: ",u:"🚀 تحديث: ",un:"🚀 تحديثات جديدة: "},en:{n:"🆕 New port: ",u:"🚀 Update: ",un:"🚀 New updates: "}};
const getJ = async k => { const r = await (await caches.open("gp-data")).match(k); return r ? r.json() : null; };
const putJ = async (k, v) => (await caches.open("gp-data")).put(k, new Response(JSON.stringify(v)));
async function check() {
  const cfg = await getJ("cfg"); if (!cfg || !(cfg.notif.newp || cfg.notif.fol || cfg.notif.all)) return;
  let d; try { d = await (await fetch(new URL("data/ports.json", self.registration.scope), {cache: "no-store"})).json(); } catch (e) { return; }
  const items = d.items || [], x = TXT[cfg.lang] || TXT.en, prev = await getJ("snap"), cur = {};
  items.forEach(i => cur[i.id] = i.release ? i.release.tag : "");
  await putJ("snap", cur); if (!prev) return;
  const names = a => a.slice(0, 3).map(i => i.owner + "/" + i.name).join("، ");
  const show = (arr, one, many, tag) => arr.length && self.registration.showNotification(arr.length === 1 ? one + arr[0].name : many + arr.length, {body: names(arr), tag, icon: "icon-192.png", badge: "icon-192.png", data: {url: "./"}});
  if (cfg.notif.newp) await show(items.filter(i => !(i.id in prev)), x.n, x.n, "gp-new");
  await show(items.filter(i => (i.id in prev) && cur[i.id] && prev[i.id] !== cur[i.id] && (cfg.notif.all || (cfg.notif.fol && cfg.follows.includes(i.id)))), x.u, x.un, "gp-upd");
}
self.addEventListener("periodicsync", e => { if (e.tag === "gp-check") e.waitUntil(check()); });
self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(clients.matchAll({type: "window", includeUncontrolled: true}).then(l => l.length ? l[0].focus() : clients.openWindow("./")));
});
