// DawnLine: вход через Steam, магазин модов, баланс, проверка DayZ-сервера,
// отзывы, лайки и комментарии. Cloudflare Worker + база D1.
// Как развернуть — в worker/README.md.
//
// Переменные (Settings → Variables):
//   SITE_URL         — адрес сайта, например https://danill228228.github.io/rusforma_vehicles_cfgeventspawn/
//   ADMIN_STEAM_IDS  — Steam ID администраторов через запятую
//   SESSION_SECRET   — секрет (Secret): длинная случайная строка для подписи входа
//   STEAM_API_KEY    — (Secret) ключ Steam Web API: ники и автоматическая проверка серверов
//   PAYMENT_INFO     — (необязательно) текст «как оплатить», который видит игрок при пополнении
// Привязка базы: D1 с именем переменной DB.

const STEAM_OPENID = "https://steamcommunity.com/openid/login";
const STEAM_API = "https://api.steampowered.com";
const DAYZ_APPID = 221100;
const SESSION_DAYS = 30;
const MAX_TEXT = 1000;
const COOLDOWN_SEC = 20;
const CHECK_COOLDOWN_SEC = 30;
const TOPUP_MIN = 50;
const TOPUP_MAX = 100000;

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, mod TEXT NOT NULL, steamid TEXT NOT NULL, text TEXT NOT NULL, ts INTEGER NOT NULL)`,
  `CREATE INDEX IF NOT EXISTS idx_comments_mod ON comments (mod, ts)`,
  `CREATE TABLE IF NOT EXISTS users (steamid TEXT PRIMARY KEY, name TEXT NOT NULL, avatar TEXT NOT NULL, updated INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS bans (steamid TEXT PRIMARY KEY, ts INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS balances (steamid TEXT PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0))`,
  `CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT NOT NULL, amount INTEGER NOT NULL, kind TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL)`,
  `CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions (steamid, ts)`,
  `CREATE TABLE IF NOT EXISTS purchases (steamid TEXT NOT NULL, mod TEXT NOT NULL, price INTEGER NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (steamid, mod))`,
  `CREATE TABLE IF NOT EXISTS topups (id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT NOT NULL, amount INTEGER NOT NULL, code TEXT NOT NULL, status TEXT NOT NULL, ts INTEGER NOT NULL, done_ts INTEGER)`,
  `CREATE TABLE IF NOT EXISTS servers (steamid TEXT PRIMARY KEY, ip TEXT NOT NULL, port INTEGER NOT NULL, qport INTEGER NOT NULL, code TEXT NOT NULL, status TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL, checked_ts INTEGER NOT NULL DEFAULT 0)`,
  `CREATE TABLE IF NOT EXISTS reviews (steamid TEXT NOT NULL, mod TEXT NOT NULL, rating INTEGER NOT NULL, text TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (steamid, mod))`,
  `CREATE TABLE IF NOT EXISTS likes (steamid TEXT NOT NULL, mod TEXT NOT NULL, PRIMARY KEY (steamid, mod))`,
  `CREATE TABLE IF NOT EXISTS delivery (mod TEXT PRIMARY KEY, url TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '')`
];

let schemaReady = false;

async function ensureSchema(db) {
  if (schemaReady) return;
  await db.batch(SCHEMA.map(sql => db.prepare(sql)));
  schemaReady = true;
}

/* ---------- ответы ---------- */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type",
  "Access-Control-Max-Age": "86400"
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...CORS }
  });
}

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

const fail = (status, error) => { throw new HttpError(status, error); };

async function body(request) {
  try { return (await request.json()) || {}; } catch (e) { return {}; }
}

/* ---------- подпись входа ---------- */

const enc = new TextEncoder();

function b64url(bytes) {
  let s = "";
  for (const b of new Uint8Array(bytes)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function hmac(secret, data) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64url(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
}

function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function makeToken(env, steamid) {
  const exp = Math.floor(Date.now() / 1000) + SESSION_DAYS * 86400;
  const data = `${steamid}.${exp}`;
  return `${data}.${await hmac(env.SESSION_SECRET, data)}`;
}

async function readToken(env, request) {
  const auth = request.headers.get("Authorization") || "";
  const m = auth.match(/^Bearer\s+(\d{17})\.(\d+)\.([\w-]+)$/);
  if (!m) return null;
  const [, steamid, exp, sig] = m;
  if (Number(exp) < Date.now() / 1000) return null;
  const good = await hmac(env.SESSION_SECRET, `${steamid}.${exp}`);
  return safeEqual(sig, good) ? steamid : null;
}

const isAdmin = (env, steamid) =>
  !!steamid && String(env.ADMIN_STEAM_IDS || "").split(",").map(s => s.trim()).includes(steamid);

function randomCode(prefix, len) {
  const abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(len));
  return prefix + Array.from(bytes, b => abc[b % abc.length]).join("");
}

/* ---------- товары: цены берутся из data.json сайта ---------- */

let productsCache = { at: 0, list: null };

async function products(env) {
  if (productsCache.list && Date.now() - productsCache.at < 60000) return productsCache.list;
  const url = new URL("data.json", siteUrl(env)).toString();
  const res = await fetch(`${url}?t=${Date.now()}`, { cf: { cacheTtl: 0 } });
  if (!res.ok) throw new HttpError(503, "Не удалось получить список модов");
  const data = await res.json();
  productsCache = { at: Date.now(), list: Array.isArray(data.mods) ? data.mods : [] };
  return productsCache.list;
}

async function product(env, mod) {
  const p = (await products(env)).find(x => x.id === mod);
  if (!p) fail(404, "Мод не найден");
  return p;
}

const priceOf = p => (Number.isInteger(p.price) && p.price >= 0 ? p.price : null);

/* ---------- Steam: вход ---------- */

function siteUrl(env) {
  const u = new URL(env.SITE_URL);
  if (u.protocol !== "https:" && u.hostname !== "127.0.0.1" && u.hostname !== "localhost") throw new Error("SITE_URL должен начинаться с https://");
  return u;
}

function startLogin(request, env) {
  const self = new URL(request.url);
  const params = new URLSearchParams({
    "openid.ns": "http://specs.openid.net/auth/2.0",
    "openid.mode": "checkid_setup",
    "openid.return_to": `${self.origin}/auth/steam/callback`,
    "openid.realm": self.origin,
    "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
    "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select"
  });
  return Response.redirect(`${env.STEAM_OPENID_URL || STEAM_OPENID}?${params}`, 302);
}

async function finishLogin(request, env) {
  const self = new URL(request.url);
  const q = self.searchParams;
  const back = siteUrl(env);
  const backWith = hash => { back.hash = hash; return Response.redirect(back.toString(), 302); };

  if (q.get("openid.mode") !== "id_res") return backWith("cabinet&steam_error=cancel");
  if (!(q.get("openid.return_to") || "").startsWith(`${self.origin}/auth/steam/callback`)) return backWith("cabinet&steam_error=bad");
  const m = (q.get("openid.claimed_id") || "").match(/^https:\/\/steamcommunity\.com\/openid\/id\/(\d{17})$/);
  if (!m) return backWith("cabinet&steam_error=bad");

  // Спрашиваем у самого Steam, что ответ настоящий
  const check = new URLSearchParams();
  for (const [k, v] of q) if (k.startsWith("openid.")) check.set(k, v);
  check.set("openid.mode", "check_authentication");
  const res = await fetch(env.STEAM_OPENID_URL || STEAM_OPENID, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: check.toString()
  });
  if (!/is_valid\s*:\s*true/.test(await res.text())) return backWith("cabinet&steam_error=bad");

  const steamid = m[1];
  await ensureSchema(env.DB);
  await saveProfile(env, steamid);
  return backWith(`cabinet&steam=${await makeToken(env, steamid)}`);
}

function cleanAvatar(url) {
  return /^https:\/\/(avatars\.(steamstatic|akamai\.steamstatic|cloudflare\.steamstatic)\.com|steamcdn-a\.akamaihd\.net)\//.test(url || "") ? url : "";
}

async function fetchProfile(env, steamid) {
  try {
    if (env.STEAM_API_KEY) {
      const r = await fetch(`${env.STEAM_API_URL || STEAM_API}/ISteamUser/GetPlayerSummaries/v2/?key=${encodeURIComponent(env.STEAM_API_KEY)}&steamids=${steamid}`);
      const p = (await r.json()).response.players[0];
      if (p) return { name: p.personaname, avatar: p.avatarmedium };
    }
    const base = env.STEAM_PROFILE_URL || "https://steamcommunity.com/profiles/";
    const xml = await (await fetch(`${base}${steamid}/?xml=1`)).text();
    const pick = tag => {
      const mm = xml.match(new RegExp(`<${tag}>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?</${tag}>`));
      return mm ? mm[1].trim() : "";
    };
    return { name: pick("steamID"), avatar: pick("avatarMedium") };
  } catch (e) {
    return { name: "", avatar: "" };
  }
}

async function saveProfile(env, steamid) {
  const p = await fetchProfile(env, steamid);
  const name = String(p.name || "").replace(/[\u0000-\u001f]/g, "").slice(0, 64) || `Игрок …${steamid.slice(-4)}`;
  await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO users (steamid, name, avatar, updated) VALUES (?1, ?2, ?3, ?4)
       ON CONFLICT(steamid) DO UPDATE SET name = ?2, avatar = ?3, updated = ?4`
    ).bind(steamid, name, cleanAvatar(p.avatar), Date.now()),
    env.DB.prepare(`INSERT OR IGNORE INTO balances (steamid, balance) VALUES (?1, 0)`).bind(steamid)
  ]);
}

/* ---------- профиль ---------- */

async function balanceOf(env, steamid) {
  const r = await env.DB.prepare(`SELECT balance FROM balances WHERE steamid = ?1`).bind(steamid).first();
  return r ? r.balance : 0;
}

async function serverOf(env, steamid) {
  return env.DB.prepare(`SELECT ip, port, qport, code, status, name, note, ts FROM servers WHERE steamid = ?1`).bind(steamid).first();
}

async function me(env, steamid) {
  const u = await env.DB.prepare(`SELECT name, avatar FROM users WHERE steamid = ?1`).bind(steamid).first();
  const banned = await env.DB.prepare(`SELECT 1 FROM bans WHERE steamid = ?1`).bind(steamid).first();
  return {
    steamid,
    name: u ? u.name : "",
    avatar: u ? u.avatar : "",
    admin: isAdmin(env, steamid),
    banned: !!banned,
    balance: await balanceOf(env, steamid),
    server: await serverOf(env, steamid),
    autoCheck: !!env.STEAM_API_KEY
  };
}

/* ---------- проверка DayZ-сервера ---------- */

const isIPv4 = ip => /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/.test(ip);
const isPort = p => Number.isInteger(p) && p >= 1 && p <= 65535;

async function setServer(env, steamid, b) {
  const ip = String(b.ip || "").trim();
  const port = Number(b.port), qport = Number(b.qport);
  if (!isIPv4(ip)) fail(400, "Укажи IP сервера, например 123.45.67.89");
  if (!isPort(port)) fail(400, "Port — число от 1 до 65535");
  if (!isPort(qport)) fail(400, "QPort — число от 1 до 65535");
  const taken = await env.DB.prepare(`SELECT steamid FROM servers WHERE ip = ?1 AND qport = ?2 AND status = 'verified' AND steamid <> ?3`).bind(ip, qport, steamid).first();
  if (taken) fail(409, "Этот сервер уже подтверждён другим аккаунтом. Напиши администратору.");
  const old = await serverOf(env, steamid);
  const same = old && old.ip === ip && old.port === port && old.qport === qport;
  if (same && old.status === "verified") return { server: old };
  const code = same ? old.code : randomCode("DL-", 6);
  await env.DB.prepare(
    `INSERT INTO servers (steamid, ip, port, qport, code, status, name, note, ts, checked_ts) VALUES (?1, ?2, ?3, ?4, ?5, 'code', '', '', ?6, 0)
     ON CONFLICT(steamid) DO UPDATE SET ip = ?2, port = ?3, qport = ?4, code = ?5, status = 'code', name = '', note = '', ts = ?6, checked_ts = 0`
  ).bind(steamid, ip, port, qport, code, Date.now()).run();
  return { server: await serverOf(env, steamid) };
}

async function checkServer(env, steamid) {
  const s = await serverOf(env, steamid);
  if (!s) fail(400, "Сначала укажи IP, Port и QPort");
  if (s.status === "verified") return { server: s };
  const row = await env.DB.prepare(`SELECT checked_ts FROM servers WHERE steamid = ?1`).bind(steamid).first();
  if (row && Date.now() - row.checked_ts < CHECK_COOLDOWN_SEC * 1000) fail(429, `Проверять можно раз в ${CHECK_COOLDOWN_SEC} секунд`);
  await env.DB.prepare(`UPDATE servers SET checked_ts = ?2 WHERE steamid = ?1`).bind(steamid, Date.now()).run();

  // Без ключа Steam — заявка уходит администратору
  if (!env.STEAM_API_KEY) {
    await env.DB.prepare(`UPDATE servers SET status = 'pending', note = '' WHERE steamid = ?1`).bind(steamid).run();
    return { server: await serverOf(env, steamid), manual: true };
  }

  const filter = `\\appid\\${DAYZ_APPID}\\addr\\${s.ip}:${s.qport}`;
  let list = [];
  try {
    const r = await fetch(`${env.STEAM_API_URL || STEAM_API}/IGameServersService/GetServerList/v1/?key=${encodeURIComponent(env.STEAM_API_KEY)}&limit=5&filter=${encodeURIComponent(filter)}`);
    list = ((await r.json()).response || {}).servers || [];
  } catch (e) {
    fail(502, "Steam сейчас не отвечает, попробуй позже");
  }
  const found = list.find(x => String(x.addr) === `${s.ip}:${s.qport}`) || list[0];
  let note = "";
  if (!found) note = "Steam не видит сервер с таким IP и QPort. Проверь, что сервер запущен и QPort указан верно.";
  else if (Number(found.gameport) && Number(found.gameport) !== s.port) note = `У сервера другой Port: ${found.gameport}.`;
  else if (!String(found.name || "").includes(s.code)) note = `Сервер найден («${String(found.name).slice(0, 80)}»), но в названии нет кода ${s.code}.`;

  if (note) {
    await env.DB.prepare(`UPDATE servers SET note = ?2 WHERE steamid = ?1`).bind(steamid, note).run();
    return { server: await serverOf(env, steamid), ok: false };
  }
  const name = String(found.name).replace(s.code, "").replace(/\s{2,}/g, " ").trim().slice(0, 120);
  await env.DB.prepare(`UPDATE servers SET status = 'verified', name = ?2, note = '' WHERE steamid = ?1`).bind(steamid, name).run();
  return { server: await serverOf(env, steamid), ok: true };
}

/* ---------- покупки ---------- */

async function buy(env, steamid, mod) {
  const p = await product(env, mod);
  const price = priceOf(p);
  if (price === null || p.status !== "ready") fail(400, "Этот мод пока нельзя купить");
  const s = await serverOf(env, steamid);
  if (!s || s.status !== "verified") fail(403, "Сначала подтверди свой DayZ-сервер в кабинете");
  const banned = await env.DB.prepare(`SELECT 1 FROM bans WHERE steamid = ?1`).bind(steamid).first();
  if (banned) fail(403, "Аккаунт заблокирован");

  const ts = Date.now();
  // Всё в одной транзакции: списать, только если хватает денег и мод ещё не куплен
  await env.DB.batch([
    env.DB.prepare(`INSERT OR IGNORE INTO balances (steamid, balance) VALUES (?1, 0)`).bind(steamid),
    env.DB.prepare(
      `UPDATE balances SET balance = balance - ?2
       WHERE steamid = ?1 AND balance >= ?2 AND NOT EXISTS (SELECT 1 FROM purchases WHERE steamid = ?1 AND mod = ?3)`
    ).bind(steamid, price, mod),
    env.DB.prepare(`INSERT INTO purchases (steamid, mod, price, ts) SELECT ?1, ?2, ?3, ?4 WHERE changes() = 1`).bind(steamid, mod, price, ts),
    env.DB.prepare(
      `INSERT INTO transactions (steamid, amount, kind, note, ts)
       SELECT ?1, -?3, 'purchase', ?5, ?4 WHERE EXISTS (SELECT 1 FROM purchases WHERE steamid = ?1 AND mod = ?2 AND ts = ?4)`
    ).bind(steamid, mod, price, ts, `Покупка: ${String(p.name || mod).slice(0, 80)}`)
  ]);
  const done = await env.DB.prepare(`SELECT ts FROM purchases WHERE steamid = ?1 AND mod = ?2`).bind(steamid, mod).first();
  if (done && done.ts === ts) return { ok: true, balance: await balanceOf(env, steamid) };
  if (done) fail(409, "Этот мод уже куплен");
  fail(402, "Недостаточно средств на балансе");
}

async function myPurchases(env, steamid) {
  const { results } = await env.DB.prepare(
    `SELECT p.mod, p.price, p.ts, d.url, d.note FROM purchases p LEFT JOIN delivery d ON d.mod = p.mod WHERE p.steamid = ?1 ORDER BY p.ts DESC`
  ).bind(steamid).all();
  return { purchases: results };
}

/* ---------- баланс ---------- */

async function createTopup(env, steamid, amount) {
  amount = Math.round(Number(amount));
  if (!Number.isFinite(amount) || amount < TOPUP_MIN || amount > TOPUP_MAX) fail(400, `Сумма от ${TOPUP_MIN} до ${TOPUP_MAX} ₽`);
  const open = await env.DB.prepare(`SELECT COUNT(*) AS n FROM topups WHERE steamid = ?1 AND status = 'pending'`).bind(steamid).first();
  if (open && open.n >= 3) fail(429, "У тебя уже есть 3 заявки на проверке");
  const code = randomCode("TOP-", 5);
  const r = await env.DB.prepare(`INSERT INTO topups (steamid, amount, code, status, ts) VALUES (?1, ?2, ?3, 'pending', ?4)`).bind(steamid, amount, code, Date.now()).run();
  return { id: r.meta.last_row_id, code, amount, info: String(env.PAYMENT_INFO || "") };
}

async function myMoney(env, steamid) {
  const tx = await env.DB.prepare(`SELECT amount, kind, note, ts FROM transactions WHERE steamid = ?1 ORDER BY ts DESC LIMIT 50`).bind(steamid).all();
  const tp = await env.DB.prepare(`SELECT id, amount, code, status, ts FROM topups WHERE steamid = ?1 ORDER BY ts DESC LIMIT 20`).bind(steamid).all();
  return { balance: await balanceOf(env, steamid), transactions: tx.results, topups: tp.results, info: String(env.PAYMENT_INFO || "") };
}

async function credit(env, steamid, amount, kind, note) {
  await env.DB.batch([
    env.DB.prepare(`INSERT OR IGNORE INTO balances (steamid, balance) VALUES (?1, 0)`).bind(steamid),
    env.DB.prepare(`UPDATE balances SET balance = balance + ?2 WHERE steamid = ?1`).bind(steamid, amount),
    env.DB.prepare(`INSERT INTO transactions (steamid, amount, kind, note, ts) VALUES (?1, ?2, ?3, ?4, ?5)`).bind(steamid, amount, kind, note, Date.now())
  ]);
}

/* ---------- отзывы, лайки, комментарии ---------- */

const validMod = mod => typeof mod === "string" && /^[\w-]{1,64}$/.test(mod);

function cleanText(t) {
  const text = String(t || "").replace(/\r\n?/g, "\n").trim();
  if (!text) fail(400, "Пустой текст");
  if (text.length > MAX_TEXT) fail(400, `Не больше ${MAX_TEXT} символов`);
  return text;
}

async function notBanned(env, steamid) {
  const b = await env.DB.prepare(`SELECT 1 FROM bans WHERE steamid = ?1`).bind(steamid).first();
  if (b) fail(403, "Ты не можешь оставлять комментарии и отзывы");
}

async function stats(env) {
  const [c, l, r] = await env.DB.batch([
    env.DB.prepare(`SELECT mod, COUNT(*) AS n FROM comments GROUP BY mod`),
    env.DB.prepare(`SELECT mod, COUNT(*) AS n FROM likes GROUP BY mod`),
    env.DB.prepare(`SELECT mod, COUNT(*) AS n, AVG(rating) AS avg FROM reviews GROUP BY mod`)
  ]);
  const map = (rows, f) => Object.fromEntries(rows.results.map(x => [x.mod, f(x)]));
  return {
    comments: map(c, x => x.n),
    likes: map(l, x => x.n),
    reviews: map(r, x => ({ n: x.n, avg: Math.round(x.avg * 10) / 10 }))
  };
}

async function listReviews(env, mod) {
  const sql = `SELECT r.steamid, r.mod, r.rating, r.text, r.ts, u.name, u.avatar FROM reviews r LEFT JOIN users u ON u.steamid = r.steamid`;
  const q = mod ? env.DB.prepare(`${sql} WHERE r.mod = ?1 ORDER BY r.ts DESC LIMIT 200`).bind(mod)
                : env.DB.prepare(`${sql} ORDER BY r.ts DESC LIMIT 6`);
  return { reviews: (await q.all()).results };
}

async function addReview(env, steamid, b) {
  if (!validMod(b.mod)) fail(400, "Неверный мод");
  await notBanned(env, steamid);
  const bought = await env.DB.prepare(`SELECT 1 FROM purchases WHERE steamid = ?1 AND mod = ?2`).bind(steamid, b.mod).first();
  if (!bought) fail(403, "Отзыв может оставить только покупатель мода");
  const rating = Math.round(Number(b.rating));
  if (!(rating >= 1 && rating <= 5)) fail(400, "Оценка от 1 до 5");
  const text = cleanText(b.text);
  await env.DB.prepare(
    `INSERT INTO reviews (steamid, mod, rating, text, ts) VALUES (?1, ?2, ?3, ?4, ?5)
     ON CONFLICT(steamid, mod) DO UPDATE SET rating = ?3, text = ?4, ts = ?5`
  ).bind(steamid, b.mod, rating, text, Date.now()).run();
  return { ok: true };
}

async function toggleLike(env, steamid, mod) {
  if (!validMod(mod)) fail(400, "Неверный мод");
  const had = await env.DB.prepare(`SELECT 1 FROM likes WHERE steamid = ?1 AND mod = ?2`).bind(steamid, mod).first();
  if (had) await env.DB.prepare(`DELETE FROM likes WHERE steamid = ?1 AND mod = ?2`).bind(steamid, mod).run();
  else await env.DB.prepare(`INSERT OR IGNORE INTO likes (steamid, mod) VALUES (?1, ?2)`).bind(steamid, mod).run();
  return { liked: !had };
}

async function listComments(env, mod) {
  if (!validMod(mod)) fail(400, "Неверный мод");
  const { results } = await env.DB.prepare(
    `SELECT c.id, c.steamid, c.text, c.ts, u.name, u.avatar FROM comments c
     LEFT JOIN users u ON u.steamid = c.steamid WHERE c.mod = ?1 ORDER BY c.ts ASC LIMIT 500`
  ).bind(mod).all();
  return { comments: results };
}

async function addComment(env, steamid, b) {
  if (!validMod(b.mod)) fail(400, "Неверный мод");
  const text = cleanText(b.text);
  await notBanned(env, steamid);
  const last = await env.DB.prepare(`SELECT MAX(ts) AS ts FROM comments WHERE steamid = ?1`).bind(steamid).first();
  if (!isAdmin(env, steamid) && last && last.ts && Date.now() - last.ts < COOLDOWN_SEC * 1000) {
    fail(429, `Подожди ${COOLDOWN_SEC} секунд между комментариями`);
  }
  const ts = Date.now();
  const r = await env.DB.prepare(`INSERT INTO comments (mod, steamid, text, ts) VALUES (?1, ?2, ?3, ?4)`).bind(b.mod, steamid, text, ts).run();
  return { ok: true, id: r.meta.last_row_id, ts };
}

async function deleteComment(env, steamid, id) {
  const row = await env.DB.prepare(`SELECT steamid FROM comments WHERE id = ?1`).bind(id).first();
  if (!row) fail(404, "Комментарий не найден");
  if (row.steamid !== steamid && !isAdmin(env, steamid)) fail(403, "Можно удалять только свои комментарии");
  await env.DB.prepare(`DELETE FROM comments WHERE id = ?1`).bind(id).run();
  return { ok: true };
}

/* ---------- администратор ---------- */

function needAdmin(env, steamid) {
  if (!isAdmin(env, steamid)) fail(403, "Только для администратора");
}

async function adminOverview(env) {
  const [servers, topups, sales, users] = await env.DB.batch([
    env.DB.prepare(`SELECT s.steamid, s.ip, s.port, s.qport, s.code, s.status, s.ts, u.name FROM servers s LEFT JOIN users u ON u.steamid = s.steamid WHERE s.status = 'pending' ORDER BY s.ts`),
    env.DB.prepare(`SELECT t.id, t.steamid, t.amount, t.code, t.ts, u.name FROM topups t LEFT JOIN users u ON u.steamid = t.steamid WHERE t.status = 'pending' ORDER BY t.ts`),
    env.DB.prepare(`SELECT p.steamid, p.mod, p.price, p.ts, u.name FROM purchases p LEFT JOIN users u ON u.steamid = p.steamid ORDER BY p.ts DESC LIMIT 30`),
    env.DB.prepare(`SELECT COUNT(*) AS n FROM users`)
  ]);
  const del = await env.DB.prepare(`SELECT mod, url, note FROM delivery`).all();
  return { servers: servers.results, topups: topups.results, sales: sales.results, users: users.results[0].n, delivery: del.results };
}

async function adminServer(env, b) {
  if (!/^\d{17}$/.test(b.steamid || "")) fail(400, "Неверный Steam ID");
  const status = b.action === "approve" ? "verified" : b.action === "reject" ? "rejected" : null;
  if (!status) fail(400, "Неверное действие");
  const note = status === "rejected" ? String(b.note || "Заявка отклонена администратором").slice(0, 200) : "";
  const r = await env.DB.prepare(`UPDATE servers SET status = ?2, note = ?3 WHERE steamid = ?1`).bind(b.steamid, status, note).run();
  if (!r.meta.changes) fail(404, "Заявка не найдена");
  return { ok: true };
}

async function adminTopup(env, b) {
  const t = await env.DB.prepare(`SELECT steamid, amount, code, status FROM topups WHERE id = ?1`).bind(Number(b.id)).first();
  if (!t) fail(404, "Заявка не найдена");
  if (t.status !== "pending") fail(409, "Заявка уже обработана");
  if (b.action === "approve") {
    const done = await env.DB.prepare(`UPDATE topups SET status = 'done', done_ts = ?2 WHERE id = ?1 AND status = 'pending'`).bind(Number(b.id), Date.now()).run();
    if (done.meta.changes) await credit(env, t.steamid, t.amount, "topup", `Пополнение ${t.code}`);
  } else if (b.action === "reject") {
    await env.DB.prepare(`UPDATE topups SET status = 'rejected', done_ts = ?2 WHERE id = ?1`).bind(Number(b.id), Date.now()).run();
  } else fail(400, "Неверное действие");
  return { ok: true };
}

async function adminBalance(env, b) {
  if (!/^\d{17}$/.test(b.steamid || "")) fail(400, "Неверный Steam ID");
  const amount = Math.round(Number(b.amount));
  if (!Number.isFinite(amount) || amount === 0 || Math.abs(amount) > 1000000) fail(400, "Неверная сумма");
  if (amount < 0 && (await balanceOf(env, b.steamid)) + amount < 0) fail(400, "Нельзя уйти в минус");
  await credit(env, b.steamid, amount, "admin", String(b.note || "Изменено администратором").slice(0, 120));
  return { ok: true, balance: await balanceOf(env, b.steamid) };
}

async function adminRefund(env, b) {
  const p = await env.DB.prepare(`SELECT price FROM purchases WHERE steamid = ?1 AND mod = ?2`).bind(b.steamid, b.mod).first();
  if (!p) fail(404, "Покупка не найдена");
  await env.DB.batch([
    env.DB.prepare(`DELETE FROM purchases WHERE steamid = ?1 AND mod = ?2`).bind(b.steamid, b.mod),
    env.DB.prepare(`DELETE FROM reviews WHERE steamid = ?1 AND mod = ?2`).bind(b.steamid, b.mod),
    env.DB.prepare(`UPDATE balances SET balance = balance + ?2 WHERE steamid = ?1`).bind(b.steamid, p.price),
    env.DB.prepare(`INSERT INTO transactions (steamid, amount, kind, note, ts) VALUES (?1, ?2, 'refund', ?3, ?4)`).bind(b.steamid, p.price, `Возврат: ${b.mod}`, Date.now())
  ]);
  return { ok: true };
}

async function adminDelivery(env, b) {
  if (!validMod(b.mod)) fail(400, "Неверный мод");
  const url = String(b.url || "").trim();
  if (url && !/^https:\/\//i.test(url)) fail(400, "Ссылка должна начинаться с https://");
  await env.DB.prepare(
    `INSERT INTO delivery (mod, url, note) VALUES (?1, ?2, ?3) ON CONFLICT(mod) DO UPDATE SET url = ?2, note = ?3`
  ).bind(b.mod, url.slice(0, 500), String(b.note || "").slice(0, 1000)).run();
  return { ok: true };
}

async function adminUser(env, steamid) {
  if (!/^\d{17}$/.test(steamid || "")) fail(400, "Неверный Steam ID");
  const info = await me(env, steamid);
  return { ...info, ...(await myPurchases(env, steamid)), ...(await myMoney(env, steamid)) };
}

async function ban(env, target, removeAll) {
  if (!/^\d{17}$/.test(target || "")) fail(400, "Неверный Steam ID");
  if (isAdmin(env, target)) fail(400, "Нельзя заблокировать администратора");
  const stmts = [env.DB.prepare(`INSERT OR REPLACE INTO bans (steamid, ts) VALUES (?1, ?2)`).bind(target, Date.now())];
  if (removeAll) stmts.push(env.DB.prepare(`DELETE FROM comments WHERE steamid = ?1`).bind(target), env.DB.prepare(`DELETE FROM reviews WHERE steamid = ?1`).bind(target));
  await env.DB.batch(stmts);
  return { ok: true };
}

/* ---------- маршруты ---------- */

async function route(request, env) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const M = request.method;

  if (path === "/auth/steam" && M === "GET") return startLogin(request, env);
  if (path === "/auth/steam/callback" && M === "GET") return finishLogin(request, env);

  await ensureSchema(env.DB);
  const uid = await readToken(env, request);
  const need = () => { if (!uid) fail(401, "Нужно войти через Steam"); return uid; };

  if (path === "/") return json({ ok: true, service: "dawnline" });
  if (path === "/stats" && M === "GET") return json(await stats(env));
  if (path === "/comments/counts" && M === "GET") return json({ counts: (await stats(env)).comments });
  if (path === "/comments" && M === "GET") return json(await listComments(env, url.searchParams.get("mod")));
  if (path === "/reviews" && M === "GET") {
    const mod = url.searchParams.get("mod");
    if (mod && !validMod(mod)) fail(400, "Неверный мод");
    return json(await listReviews(env, mod));
  }

  if (path === "/me" && M === "GET") return json(await me(env, need()));
  if (path === "/likes/mine" && M === "GET") {
    const { results } = await env.DB.prepare(`SELECT mod FROM likes WHERE steamid = ?1`).bind(need()).all();
    return json({ likes: results.map(r => r.mod) });
  }
  if (path === "/likes" && M === "POST") return json(await toggleLike(env, need(), (await body(request)).mod));
  if (path === "/comments" && M === "POST") return json(await addComment(env, need(), await body(request)), 201);
  const del = path.match(/^\/comments\/(\d+)$/);
  if (del && M === "DELETE") return json(await deleteComment(env, need(), Number(del[1])));
  if (path === "/reviews" && M === "POST") return json(await addReview(env, need(), await body(request)));
  const delRev = path.match(/^\/reviews\/([\w-]{1,64})$/);
  if (delRev && M === "DELETE") {
    await env.DB.prepare(`DELETE FROM reviews WHERE steamid = ?1 AND mod = ?2`).bind(need(), delRev[1]).run();
    return json({ ok: true });
  }

  if (path === "/server" && M === "POST") return json(await setServer(env, need(), await body(request)));
  if (path === "/server/check" && M === "POST") return json(await checkServer(env, need()));
  if (path === "/buy" && M === "POST") return json(await buy(env, need(), (await body(request)).mod));
  if (path === "/purchases" && M === "GET") return json(await myPurchases(env, need()));
  if (path === "/money" && M === "GET") return json(await myMoney(env, need()));
  if (path === "/topup" && M === "POST") return json(await createTopup(env, need(), (await body(request)).amount), 201);

  if (path.startsWith("/admin/") || path === "/ban") {
    needAdmin(env, need());
    if (path === "/admin/overview" && M === "GET") return json(await adminOverview(env));
    if (path === "/admin/user" && M === "GET") return json(await adminUser(env, url.searchParams.get("steamid")));
    const b = await body(request);
    if (path === "/admin/server" && M === "POST") return json(await adminServer(env, b));
    if (path === "/admin/topup" && M === "POST") return json(await adminTopup(env, b));
    if (path === "/admin/balance" && M === "POST") return json(await adminBalance(env, b));
    if (path === "/admin/refund" && M === "POST") return json(await adminRefund(env, b));
    if (path === "/admin/delivery" && M === "POST") return json(await adminDelivery(env, b));
    if (path === "/ban" && M === "POST") return json(await ban(env, String(b.steamid || ""), !!b.removeAll));
  }

  fail(404, "Не найдено");
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (!env.SESSION_SECRET || env.SESSION_SECRET.length < 24) return json({ error: "Не задан SESSION_SECRET (не короче 24 символов)" }, 500);
    if (!env.DB) return json({ error: "Не подключена база D1 (переменная DB)" }, 500);
    try {
      return await route(request, env);
    } catch (e) {
      if (e instanceof HttpError) return json({ error: e.message }, e.status);
      return json({ error: "Ошибка сервера" }, 500);
    }
  }
};
