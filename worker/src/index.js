// DawnLine — сервер магазина модов DayZ.
// Вход через Steam, товары и фото, верификация покупателей, баланс (Stripe: BLIK, Google Pay, карты;
// вручную: Boosty и реквизиты), покупки с выдачей ссылки, отзывы и лайки, админка.
// Cloudflare Worker; данные хранятся в Durable Object со встроенной SQLite.
//
// Переменные (Settings → Variables and Secrets):
//   SITE_URL          — адрес сайта, например https://danill228228.github.io/rusforma_vehicles_cfgeventspawn/
//   SESSION_SECRET    — (Secret) длинная случайная строка для подписи входа
//   ADMIN_CLAIM_CODE  — (Secret) одноразовый код: кто введёт его в кабинете, станет администратором
//   ADMIN_STEAM_IDS   — (необязательно) Steam ID администраторов через запятую
//   STEAM_API_KEY     — (Secret, необязательно) ключ Steam Web API для ников и аватаров
//   STRIPE_SECRET_KEY — (Secret, необязательно) ключ Stripe для оплаты BLIK, Google Pay и картой
//   CURRENCY          — валюта (по умолчанию pln), CURRENCY_SIGN — её знак (по умолчанию zł)

const STEAM_OPENID = "https://steamcommunity.com/openid/login";
const STEAM_API = "https://api.steampowered.com";
const STRIPE_API = "https://api.stripe.com";
const SESSION_DAYS = 30;
const TOPUP_MIN = 5;
const TOPUP_MAX = 5000;
const MAX_IMAGE_BYTES = 1500000;

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS users (steamid TEXT PRIMARY KEY, name TEXT NOT NULL, avatar TEXT NOT NULL, updated INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS bans (steamid TEXT PRIMARY KEY, ts INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS admins (steamid TEXT PRIMARY KEY, ts INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS balances (steamid TEXT PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0))`,
  `CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT NOT NULL, amount INTEGER NOT NULL, kind TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL)`,
  `CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions (steamid, ts)`,
  `CREATE TABLE IF NOT EXISTS topups (id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT NOT NULL, amount INTEGER NOT NULL, code TEXT NOT NULL, status TEXT NOT NULL, ts INTEGER NOT NULL, done_ts INTEGER)`,
  `CREATE TABLE IF NOT EXISTS card_payments (session TEXT PRIMARY KEY, steamid TEXT NOT NULL, amount INTEGER NOT NULL, status TEXT NOT NULL, ts INTEGER NOT NULL, done_ts INTEGER)`,
  `CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', price INTEGER NOT NULL, images TEXT NOT NULL DEFAULT '[]', visible INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0, ts INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS images (id TEXT PRIMARY KEY, mime TEXT NOT NULL, data BLOB NOT NULL, ts INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS delivery (mod TEXT PRIMARY KEY, url TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '')`,
  `CREATE TABLE IF NOT EXISTS purchases (steamid TEXT NOT NULL, mod TEXT NOT NULL, price INTEGER NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (steamid, mod))`,
  `CREATE TABLE IF NOT EXISTS reviews (steamid TEXT NOT NULL, mod TEXT NOT NULL, rating INTEGER NOT NULL, text TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (steamid, mod))`,
  `CREATE TABLE IF NOT EXISTS likes (steamid TEXT NOT NULL, mod TEXT NOT NULL, PRIMARY KEY (steamid, mod))`,
  `CREATE TABLE IF NOT EXISTS verifications (steamid TEXT PRIMARY KEY, project TEXT NOT NULL, discord TEXT NOT NULL, about TEXT NOT NULL, ip TEXT NOT NULL, port INTEGER NOT NULL, qport INTEGER NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL)`
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
  return safeEqual(sig, await hmac(env.SESSION_SECRET, `${steamid}.${exp}`)) ? steamid : null;
}

function randomCode(prefix, len) {
  const abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(len));
  return prefix + Array.from(bytes, b => abc[b % abc.length]).join("");
}

/* ---------- настройки и администраторы ---------- */

const isAdmin = (env, steamid) =>
  !!steamid && (String(env.ADMIN_STEAM_IDS || "").split(",").map(s => s.trim()).includes(steamid) || !!(env.__admins && env.__admins.has(steamid)));

function needAdmin(env, steamid) {
  if (!isAdmin(env, steamid)) fail(403, "Только для администратора");
}

async function getSetting(env, key) {
  const r = await env.DB.prepare(`SELECT value FROM settings WHERE key = ?1`).bind(key).first();
  return r ? r.value : null;
}

async function setSetting(env, key, value) {
  await env.DB.prepare(`INSERT INTO settings (key, value) VALUES (?1, ?2) ON CONFLICT(key) DO UPDATE SET value = ?2`).bind(key, value).run();
}

async function adminClaimable(env) {
  return !!env.ADMIN_CLAIM_CODE && (await getSetting(env, "admin_claimed")) === null;
}

async function claimAdmin(env, steamid, code) {
  if (!(await adminClaimable(env))) fail(409, "Код администратора уже использован");
  if (!safeEqual(String(code || "").trim(), String(env.ADMIN_CLAIM_CODE))) fail(403, "Неверный код");
  await env.DB.batch([
    env.DB.prepare(`INSERT OR IGNORE INTO admins (steamid, ts) VALUES (?1, ?2)`).bind(steamid, Date.now()),
    env.DB.prepare(`INSERT INTO settings (key, value) VALUES ('admin_claimed', ?1) ON CONFLICT(key) DO UPDATE SET value = ?1`).bind(steamid)
  ]);
  return { ok: true };
}

const currency = env => String(env.CURRENCY || "pln").toLowerCase();
const sign = env => String(env.CURRENCY_SIGN || "zł");

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

  if (q.get("openid.mode") !== "id_res") return backWith("/ucp?steam_error=cancel");
  if (!(q.get("openid.return_to") || "").startsWith(`${self.origin}/auth/steam/callback`)) return backWith("/ucp?steam_error=bad");
  const m = (q.get("openid.claimed_id") || "").match(/^https:\/\/steamcommunity\.com\/openid\/id\/(\d{17})$/);
  if (!m) return backWith("/ucp?steam_error=bad");

  // Спрашиваем у самого Steam, что ответ настоящий
  const check = new URLSearchParams();
  for (const [k, v] of q) if (k.startsWith("openid.")) check.set(k, v);
  check.set("openid.mode", "check_authentication");
  const res = await fetch(env.STEAM_OPENID_URL || STEAM_OPENID, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: check.toString()
  });
  if (!/is_valid\s*:\s*true/.test(await res.text())) return backWith("/ucp?steam_error=bad");

  const steamid = m[1];
  await ensureSchema(env.DB);
  await saveProfile(env, steamid);
  return backWith(`/ucp?steam=${await makeToken(env, steamid)}`);
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

async function verificationOf(env, steamid) {
  return env.DB.prepare(`SELECT project, discord, about, ip, port, qport, status, note, ts FROM verifications WHERE steamid = ?1`).bind(steamid).first();
}

async function banned(env, steamid) {
  return !!(await env.DB.prepare(`SELECT 1 FROM bans WHERE steamid = ?1`).bind(steamid).first());
}

async function me(env, steamid) {
  const u = await env.DB.prepare(`SELECT name, avatar FROM users WHERE steamid = ?1`).bind(steamid).first();
  return {
    steamid,
    name: u ? u.name : "",
    avatar: u ? u.avatar : "",
    admin: isAdmin(env, steamid),
    banned: await banned(env, steamid),
    balance: await balanceOf(env, steamid),
    verification: await verificationOf(env, steamid),
    cardPayments: !!env.STRIPE_SECRET_KEY,
    currency: currency(env),
    adminClaimable: !isAdmin(env, steamid) && (await adminClaimable(env))
  };
}

/* ---------- верификация покупателя ---------- */

const isIPv4 = ip => /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/.test(ip);
const isPort = p => Number.isInteger(p) && p >= 1 && p <= 65535;

async function submitVerification(env, steamid, b) {
  const project = String(b.project || "").trim().replace(/\s+/g, " ");
  const discord = String(b.discord || "").trim();
  const about = String(b.about || "").trim();
  const ip = String(b.ip || "").trim();
  const port = Number(b.port), qport = Number(b.qport);
  if (!/^[A-Za-z ]{2,40}$/.test(project)) fail(400, "Название проекта: только английские буквы и пробелы, от 2 до 40 символов");
  if (!/^\d{17,20}$/.test(discord)) fail(400, "Discord ID: только цифры (17–20 цифр)");
  if (about.length < 10 || about.length > 200) fail(400, "Расскажи о проекте: от 10 до 200 символов");
  if (!/^[\p{L}\p{N}\s.,!?:;()"'«»\-–—+/%№#@]+$/u.test(about)) fail(400, "В описании разрешены буквы, цифры, пробелы и основные знаки препинания");
  if (!isIPv4(ip)) fail(400, "Укажи IP сервера, например 123.45.67.89");
  if (!isPort(port)) fail(400, "Port — число от 1 до 65535");
  if (!isPort(qport)) fail(400, "QPort — число от 1 до 65535");
  if (await banned(env, steamid)) fail(403, "Аккаунт заблокирован");
  const old = await verificationOf(env, steamid);
  if (old && old.status === "approved") fail(409, "Аккаунт уже верифицирован");
  if (old && old.status === "pending") fail(409, "Заявка уже отправлена и ждёт проверки");
  await env.DB.prepare(
    `INSERT INTO verifications (steamid, project, discord, about, ip, port, qport, status, note, ts) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, 'pending', '', ?8)
     ON CONFLICT(steamid) DO UPDATE SET project = ?2, discord = ?3, about = ?4, ip = ?5, port = ?6, qport = ?7, status = 'pending', note = '', ts = ?8`
  ).bind(steamid, project, discord, about, ip, port, qport, Date.now()).run();
  return { verification: await verificationOf(env, steamid) };
}

/* ---------- товары и фото ---------- */

function productRow(r, stats) {
  let images = [];
  try { images = JSON.parse(r.images); } catch (e) { /* пусто */ }
  return {
    id: r.id, title: r.title, description: r.description, price: r.price, images, visible: !!r.visible, sort: r.sort,
    likes: (stats && stats.likes[r.id]) || 0,
    rating: (stats && stats.reviews[r.id]) || null
  };
}

async function stats(env) {
  const [l, r] = await env.DB.batch([
    env.DB.prepare(`SELECT mod, COUNT(*) AS n FROM likes GROUP BY mod`),
    env.DB.prepare(`SELECT mod, COUNT(*) AS n, AVG(rating) AS avg FROM reviews GROUP BY mod`)
  ]);
  return {
    likes: Object.fromEntries(l.results.map(x => [x.mod, x.n])),
    reviews: Object.fromEntries(r.results.map(x => [x.mod, { n: x.n, avg: Math.round(x.avg * 10) / 10 }]))
  };
}

async function listProducts(env, all) {
  const s = await stats(env);
  const { results } = await env.DB.prepare(`SELECT * FROM products ${all ? "" : "WHERE visible = 1"} ORDER BY sort ASC, ts DESC`).all();
  return { products: results.map(r => productRow(r, s)), currency: currency(env), sign: sign(env) };
}

async function getProduct(env, id, all) {
  const r = await env.DB.prepare(`SELECT * FROM products WHERE id = ?1`).bind(id).first();
  if (!r || (!r.visible && !all)) fail(404, "Продукт не найден");
  return productRow(r, await stats(env));
}

const validId = id => typeof id === "string" && /^[\w-]{1,64}$/.test(id);

async function saveProduct(env, b) {
  const title = String(b.title || "").trim();
  const description = String(b.description || "").trim();
  const price = Math.round(Number(b.price));
  const images = Array.isArray(b.images) ? b.images.map(String).filter(u => /^(https:\/\/|img\/)[^\s"'<>]+$/.test(u)).slice(0, 12) : [];
  if (title.length < 2 || title.length > 80) fail(400, "Название: от 2 до 80 символов");
  if (description.length > 4000) fail(400, "Описание: не больше 4000 символов");
  if (!Number.isFinite(price) || price < 0 || price > 1000000) fail(400, "Цена — целое число от 0");
  const id = b.id && validId(b.id) ? b.id : randomCode("p-", 8).toLowerCase();
  await env.DB.prepare(
    `INSERT INTO products (id, title, description, price, images, visible, sort, ts) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
     ON CONFLICT(id) DO UPDATE SET title = ?2, description = ?3, price = ?4, images = ?5, visible = ?6, sort = ?7`
  ).bind(id, title, description, price, JSON.stringify(images), b.visible === false ? 0 : 1, Math.round(Number(b.sort) || 0), Date.now()).run();
  if (b.delivery) {
    const url = String(b.delivery.url || "").trim();
    if (url && !/^https:\/\//i.test(url)) fail(400, "Ссылка на скачивание должна начинаться с https://");
    await env.DB.prepare(`INSERT INTO delivery (mod, url, note) VALUES (?1, ?2, ?3) ON CONFLICT(mod) DO UPDATE SET url = ?2, note = ?3`)
      .bind(id, url.slice(0, 500), String(b.delivery.note || "").slice(0, 2000)).run();
  }
  return { id };
}

async function uploadImage(env, b) {
  const m = String(b.data || "").match(/^data:(image\/(jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/);
  if (!m) fail(400, "Нужна картинка JPEG, PNG или WebP");
  const bin = atob(m[3]);
  if (bin.length > MAX_IMAGE_BYTES) fail(400, "Картинка слишком большая");
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const id = randomCode("", 16).toLowerCase();
  await env.DB.prepare(`INSERT INTO images (id, mime, data, ts) VALUES (?1, ?2, ?3, ?4)`).bind(id, m[1], bytes.buffer, Date.now()).run();
  return { url: `img/${id}` };
}

async function serveImage(env, id) {
  const r = await env.DB.prepare(`SELECT mime, data FROM images WHERE id = ?1`).bind(id).first();
  if (!r) return new Response("Not found", { status: 404, headers: CORS });
  return new Response(r.data, { headers: { "Content-Type": r.mime, "Cache-Control": "public, max-age=31536000, immutable", ...CORS } });
}

/* ---------- покупки ---------- */

async function buy(env, steamid, mod) {
  if (!validId(mod)) fail(400, "Неверный продукт");
  const p = await getProduct(env, mod, false);
  if (await banned(env, steamid)) fail(403, "Аккаунт заблокирован");
  const v = await verificationOf(env, steamid);
  if (!v || v.status !== "approved") fail(403, "Сначала пройди верификацию в личном кабинете");
  const price = p.price;
  const ts = Date.now();
  // Одна транзакция: списать, только если хватает денег и продукт ещё не куплен
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
    ).bind(steamid, mod, price, ts, `Покупка: ${p.title.slice(0, 80)}`)
  ]);
  const done = await env.DB.prepare(`SELECT ts FROM purchases WHERE steamid = ?1 AND mod = ?2`).bind(steamid, mod).first();
  if (done && done.ts === ts) return { ok: true, balance: await balanceOf(env, steamid) };
  if (done) fail(409, "Этот продукт уже куплен");
  fail(402, "Недостаточно средств на балансе");
}

async function myPurchases(env, steamid) {
  const { results } = await env.DB.prepare(
    `SELECT p.mod, p.price, p.ts, pr.title, d.url, d.note FROM purchases p
     LEFT JOIN products pr ON pr.id = p.mod LEFT JOIN delivery d ON d.mod = p.mod
     WHERE p.steamid = ?1 ORDER BY p.ts DESC`
  ).bind(steamid).all();
  return { purchases: results };
}

/* ---------- баланс ---------- */

async function credit(env, steamid, amount, kind, note) {
  await env.DB.batch([
    env.DB.prepare(`INSERT OR IGNORE INTO balances (steamid, balance) VALUES (?1, 0)`).bind(steamid),
    env.DB.prepare(`UPDATE balances SET balance = balance + ?2 WHERE steamid = ?1`).bind(steamid, amount),
    env.DB.prepare(`INSERT INTO transactions (steamid, amount, kind, note, ts) VALUES (?1, ?2, ?3, ?4, ?5)`).bind(steamid, amount, kind, note, Date.now())
  ]);
}

function checkAmount(env, amount) {
  amount = Math.round(Number(amount));
  if (!Number.isFinite(amount) || amount < TOPUP_MIN || amount > TOPUP_MAX) fail(400, `Сумма от ${TOPUP_MIN} до ${TOPUP_MAX} ${sign(env)}`);
  return amount;
}

async function manualInfo(env) {
  return { info: (await getSetting(env, "payment_info")) || "", boosty: (await getSetting(env, "boosty_url")) || "" };
}

async function createTopup(env, steamid, amount) {
  amount = checkAmount(env, amount);
  const open = await env.DB.prepare(`SELECT COUNT(*) AS n FROM topups WHERE steamid = ?1 AND status = 'pending'`).bind(steamid).first();
  if (open && open.n >= 3) fail(429, "У тебя уже есть 3 заявки на проверке");
  const code = randomCode("TOP-", 5);
  await env.DB.prepare(`INSERT INTO topups (steamid, amount, code, status, ts) VALUES (?1, ?2, ?3, 'pending', ?4)`).bind(steamid, amount, code, Date.now()).run();
  return { code, amount, ...(await manualInfo(env)) };
}

async function myMoney(env, steamid) {
  // Если игрок закрыл страницу сразу после оплаты — проверяем недавние оплаты сами
  const open = await env.DB.prepare(`SELECT session FROM card_payments WHERE steamid = ?1 AND status = 'pending' AND ts > ?2 ORDER BY ts DESC LIMIT 3`).bind(steamid, Date.now() - 2 * 86400000).all();
  for (const r of open.results) { try { await confirmCard(env, steamid, r.session); } catch (e) { /* проверим позже */ } }
  const tx = await env.DB.prepare(`SELECT amount, kind, note, ts FROM transactions WHERE steamid = ?1 ORDER BY ts DESC LIMIT 50`).bind(steamid).all();
  const tp = await env.DB.prepare(`SELECT amount, code, status, ts FROM topups WHERE steamid = ?1 ORDER BY ts DESC LIMIT 20`).bind(steamid).all();
  return { balance: await balanceOf(env, steamid), transactions: tx.results, topups: tp.results, ...(await manualInfo(env)) };
}

async function stripe(env, method, path, form) {
  const res = await fetch(`${env.STRIPE_API_URL || STRIPE_API}${path}`, {
    method,
    headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`, ...(form ? { "Content-Type": "application/x-www-form-urlencoded" } : {}) },
    body: form ? new URLSearchParams(form).toString() : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new HttpError(502, data.error && data.error.message ? `Stripe: ${data.error.message}` : "Платёжный сервис не ответил");
  return data;
}

async function cardCheckout(env, steamid, amount) {
  if (!env.STRIPE_SECRET_KEY) fail(400, "Оплата картой пока не подключена");
  amount = checkAmount(env, amount);
  const recent = await env.DB.prepare(`SELECT COUNT(*) AS n FROM card_payments WHERE steamid = ?1 AND ts > ?2`).bind(steamid, Date.now() - 3600000).first();
  if (recent && recent.n >= 10) fail(429, "Слишком много попыток оплаты, попробуй через час");
  const site = siteUrl(env);
  const base = `${site.origin}${site.pathname}`;
  const cur = currency(env);
  const form = {
    mode: "payment",
    "line_items[0][quantity]": "1",
    "line_items[0][price_data][currency]": cur,
    "line_items[0][price_data][unit_amount]": String(amount * 100),
    "line_items[0][price_data][product_data][name]": `Пополнение баланса DawnLine: ${amount} ${sign(env)}`,
    "payment_method_types[0]": "card",
    success_url: `${base}#/ucp?topup=success&session={CHECKOUT_SESSION_ID}`,
    cancel_url: `${base}#/ucp?topup=cancel`,
    client_reference_id: steamid,
    "metadata[steamid]": steamid,
    locale: "auto"
  };
  if (cur === "pln") form["payment_method_types[1]"] = "blik"; // BLIK работает только в злотых
  const session = await stripe(env, "POST", "/v1/checkout/sessions", form);
  await env.DB.prepare(`INSERT INTO card_payments (session, steamid, amount, status, ts) VALUES (?1, ?2, ?3, 'pending', ?4)`).bind(session.id, steamid, amount, Date.now()).run();
  return { url: session.url };
}

// Баланс пополняется только после того, как сам Stripe подтвердил оплату
async function confirmCard(env, steamid, sessionId) {
  if (!/^cs_\w{10,200}$/.test(sessionId || "")) fail(400, "Неверный номер оплаты");
  const row = await env.DB.prepare(`SELECT steamid, amount, status FROM card_payments WHERE session = ?1`).bind(sessionId).first();
  if (!row) fail(404, "Оплата не найдена");
  if (row.steamid !== steamid && !isAdmin(env, steamid)) fail(403, "Это не твоя оплата");
  if (row.status === "done") return { paid: true, already: true, amount: row.amount };
  if (row.status !== "pending") return { paid: false, status: row.status };
  const s = await stripe(env, "GET", `/v1/checkout/sessions/${encodeURIComponent(sessionId)}`);
  const good = s.payment_status === "paid" && s.amount_total === row.amount * 100 &&
               String(s.currency).toLowerCase() === currency(env) && s.client_reference_id === row.steamid;
  if (good) {
    await env.DB.batch([
      env.DB.prepare(`INSERT OR IGNORE INTO balances (steamid, balance) VALUES (?1, 0)`).bind(row.steamid),
      env.DB.prepare(`UPDATE card_payments SET status = 'done', done_ts = ?2 WHERE session = ?1 AND status = 'pending'`).bind(sessionId, Date.now()),
      env.DB.prepare(`UPDATE balances SET balance = balance + ?2 WHERE steamid = ?1 AND changes() = 1`).bind(row.steamid, row.amount),
      env.DB.prepare(`INSERT INTO transactions (steamid, amount, kind, note, ts) SELECT ?1, ?2, 'topup', ?3, ?4 WHERE changes() = 1`)
        .bind(row.steamid, row.amount, `Оплата онлайн (${sessionId.slice(-8)})`, Date.now())
    ]);
    return { paid: true, amount: row.amount };
  }
  if (s.status === "expired") {
    await env.DB.prepare(`UPDATE card_payments SET status = 'expired' WHERE session = ?1 AND status = 'pending'`).bind(sessionId).run();
    return { paid: false, status: "expired" };
  }
  return { paid: false, status: "pending" };
}

/* ---------- отзывы и лайки ---------- */

async function listReviews(env, mod, limit) {
  const sql = `SELECT r.steamid, r.mod, r.rating, r.text, r.ts, u.name, u.avatar, p.title FROM reviews r
               LEFT JOIN users u ON u.steamid = r.steamid LEFT JOIN products p ON p.id = r.mod`;
  const q = mod ? env.DB.prepare(`${sql} WHERE r.mod = ?1 ORDER BY r.ts DESC LIMIT 200`).bind(mod)
                : env.DB.prepare(`${sql} ORDER BY r.ts DESC LIMIT ?1`).bind(limit);
  return { reviews: (await q.all()).results };
}

async function addReview(env, steamid, b) {
  if (!validId(b.mod)) fail(400, "Неверный продукт");
  if (await banned(env, steamid)) fail(403, "Аккаунт заблокирован");
  const bought = await env.DB.prepare(`SELECT 1 FROM purchases WHERE steamid = ?1 AND mod = ?2`).bind(steamid, b.mod).first();
  if (!bought) fail(403, "Отзыв может оставить только покупатель");
  const rating = Math.round(Number(b.rating));
  if (!(rating >= 1 && rating <= 5)) fail(400, "Оценка от 1 до 5");
  const text = String(b.text || "").replace(/\r\n?/g, "\n").trim();
  if (text.length < 3 || text.length > 1000) fail(400, "Отзыв: от 3 до 1000 символов");
  await env.DB.prepare(
    `INSERT INTO reviews (steamid, mod, rating, text, ts) VALUES (?1, ?2, ?3, ?4, ?5)
     ON CONFLICT(steamid, mod) DO UPDATE SET rating = ?3, text = ?4, ts = ?5`
  ).bind(steamid, b.mod, rating, text, Date.now()).run();
  return { ok: true };
}

async function toggleLike(env, steamid, mod) {
  if (!validId(mod)) fail(400, "Неверный продукт");
  const had = await env.DB.prepare(`SELECT 1 FROM likes WHERE steamid = ?1 AND mod = ?2`).bind(steamid, mod).first();
  if (had) await env.DB.prepare(`DELETE FROM likes WHERE steamid = ?1 AND mod = ?2`).bind(steamid, mod).run();
  else await env.DB.prepare(`INSERT OR IGNORE INTO likes (steamid, mod) VALUES (?1, ?2)`).bind(steamid, mod).run();
  return { liked: !had };
}

/* ---------- администратор ---------- */

async function adminOverview(env) {
  const [ver, topups, sales, users, cards] = await env.DB.batch([
    env.DB.prepare(`SELECT v.*, u.name FROM verifications v LEFT JOIN users u ON u.steamid = v.steamid WHERE v.status = 'pending' ORDER BY v.ts`),
    env.DB.prepare(`SELECT t.id, t.steamid, t.amount, t.code, t.ts, u.name FROM topups t LEFT JOIN users u ON u.steamid = t.steamid WHERE t.status = 'pending' ORDER BY t.ts`),
    env.DB.prepare(`SELECT p.steamid, p.mod, p.price, p.ts, u.name, pr.title FROM purchases p LEFT JOIN users u ON u.steamid = p.steamid LEFT JOIN products pr ON pr.id = p.mod ORDER BY p.ts DESC LIMIT 30`),
    env.DB.prepare(`SELECT COUNT(*) AS n FROM users`),
    env.DB.prepare(`SELECT c.steamid, c.amount, c.done_ts, u.name FROM card_payments c LEFT JOIN users u ON u.steamid = c.steamid WHERE c.status = 'done' ORDER BY c.done_ts DESC LIMIT 20`)
  ]);
  const del = await env.DB.prepare(`SELECT mod, url, note FROM delivery`).all();
  return {
    verifications: ver.results, topups: topups.results, sales: sales.results, users: users.results[0].n, cards: cards.results,
    delivery: del.results, cardPayments: !!env.STRIPE_SECRET_KEY, ...(await manualInfo(env)), ...(await listProducts(env, true))
  };
}

async function adminVerification(env, b) {
  if (!/^\d{17}$/.test(b.steamid || "")) fail(400, "Неверный Steam ID");
  const status = b.action === "approve" ? "approved" : b.action === "reject" ? "rejected" : null;
  if (!status) fail(400, "Неверное действие");
  const note = status === "rejected" ? String(b.note || "Заявка отклонена администратором").slice(0, 200) : "";
  const r = await env.DB.prepare(`UPDATE verifications SET status = ?2, note = ?3 WHERE steamid = ?1`).bind(b.steamid, status, note).run();
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
  return { ok: true };
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

async function adminUser(env, steamid) {
  if (!/^\d{17}$/.test(steamid || "")) fail(400, "Неверный Steam ID");
  return { ...(await me(env, steamid)), ...(await myPurchases(env, steamid)) };
}

async function adminSettings(env, b) {
  const boosty = String(b.boosty || "").trim();
  if (boosty && !/^https:\/\/boosty\.to\/[\w.-]+(\/[\w./?=&%-]*)?$/i.test(boosty)) fail(400, "Ссылка на Boosty должна быть вида https://boosty.to/твой_ник");
  await setSetting(env, "payment_info", String(b.paymentInfo || "").slice(0, 1000));
  await setSetting(env, "boosty_url", boosty.slice(0, 300));
  return { ok: true };
}

async function ban(env, b) {
  const target = String(b.steamid || "");
  if (!/^\d{17}$/.test(target)) fail(400, "Неверный Steam ID");
  if (isAdmin(env, target)) fail(400, "Нельзя заблокировать администратора");
  await env.DB.batch([
    env.DB.prepare(`INSERT OR REPLACE INTO bans (steamid, ts) VALUES (?1, ?2)`).bind(target, Date.now()),
    env.DB.prepare(`DELETE FROM reviews WHERE steamid = ?1`).bind(target)
  ]);
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
  const img = path.match(/^\/img\/([a-z0-9]{16})$/);
  if (img && M === "GET") return serveImage(env, img[1]);

  env.__admins = new Set((await env.DB.prepare(`SELECT steamid FROM admins`).all()).results.map(r => r.steamid));
  const uid = await readToken(env, request);
  const need = () => { if (!uid) fail(401, "Нужно войти через Steam"); return uid; };

  if (path === "/") return json({ ok: true, service: "dawnline" });
  if (path === "/products" && M === "GET") return json(await listProducts(env, false));
  const prod = path.match(/^\/products\/([\w-]{1,64})$/);
  if (prod && M === "GET") return json({ product: await getProduct(env, prod[1], false), ...(await listReviews(env, prod[1])) });
  if (path === "/reviews" && M === "GET") return json(await listReviews(env, null, Math.min(100, Number(url.searchParams.get("limit")) || 6)));

  if (path === "/me" && M === "GET") return json(await me(env, need()));
  if (path === "/likes/mine" && M === "GET") {
    const { results } = await env.DB.prepare(`SELECT mod FROM likes WHERE steamid = ?1`).bind(need()).all();
    return json({ likes: results.map(r => r.mod) });
  }
  if (path === "/likes" && M === "POST") return json(await toggleLike(env, need(), (await body(request)).mod));
  if (path === "/reviews" && M === "POST") return json(await addReview(env, need(), await body(request)));
  const delRev = path.match(/^\/reviews\/([\w-]{1,64})$/);
  if (delRev && M === "DELETE") {
    await env.DB.prepare(`DELETE FROM reviews WHERE steamid = ?1 AND mod = ?2`).bind(need(), delRev[1]).run();
    return json({ ok: true });
  }
  if (path === "/verify" && M === "POST") return json(await submitVerification(env, need(), await body(request)));
  if (path === "/buy" && M === "POST") return json(await buy(env, need(), (await body(request)).mod));
  if (path === "/purchases" && M === "GET") return json(await myPurchases(env, need()));
  if (path === "/money" && M === "GET") return json(await myMoney(env, need()));
  if (path === "/topup" && M === "POST") return json(await createTopup(env, need(), (await body(request)).amount), 201);
  if (path === "/topup/card" && M === "POST") return json(await cardCheckout(env, need(), (await body(request)).amount), 201);
  if (path === "/topup/confirm" && M === "POST") return json(await confirmCard(env, need(), String((await body(request)).session || "")));
  if (path === "/admin/claim" && M === "POST") return json(await claimAdmin(env, need(), (await body(request)).code));

  if (path.startsWith("/admin/")) {
    needAdmin(env, need());
    if (path === "/admin/overview" && M === "GET") return json(await adminOverview(env));
    if (path === "/admin/user" && M === "GET") return json(await adminUser(env, url.searchParams.get("steamid")));
    const delProd = path.match(/^\/admin\/product\/([\w-]{1,64})$/);
    if (delProd && M === "DELETE") {
      await env.DB.prepare(`DELETE FROM products WHERE id = ?1`).bind(delProd[1]).run();
      return json({ ok: true });
    }
    const b = await body(request);
    if (path === "/admin/product" && M === "POST") return json(await saveProduct(env, b));
    if (path === "/admin/image" && M === "POST") return json(await uploadImage(env, b));
    if (path === "/admin/verification" && M === "POST") return json(await adminVerification(env, b));
    if (path === "/admin/topup" && M === "POST") return json(await adminTopup(env, b));
    if (path === "/admin/balance" && M === "POST") return json(await adminBalance(env, b));
    if (path === "/admin/refund" && M === "POST") return json(await adminRefund(env, b));
    if (path === "/admin/settings" && M === "POST") return json(await adminSettings(env, b));
    if (path === "/admin/ban" && M === "POST") return json(await ban(env, b));
  }

  fail(404, "Не найдено");
}

/* ---------- хранилище: SQLite внутри Durable Object ---------- */

// Прослойка с тем же интерфейсом, что у Cloudflare D1: prepare().bind().first()/all()/run() и batch().
function sqliteDb(storage) {
  const sql = storage.sql;
  class Statement {
    constructor(query, args) { this.query = query; this.args = args || []; }
    bind(...args) { return new Statement(this.query, args); }
    exec() {
      const results = sql.exec(this.query, ...this.args).toArray();
      const meta = { changes: 0, last_row_id: null };
      if (/^\s*(INSERT|UPDATE|DELETE|REPLACE)/i.test(this.query)) {
        meta.changes = sql.exec("SELECT changes() AS n").one().n;
        meta.last_row_id = sql.exec("SELECT last_insert_rowid() AS id").one().id;
      }
      return { results, meta };
    }
    async first() { return this.exec().results[0] || null; }
    async all() { return this.exec(); }
    async run() { return this.exec(); }
  }
  return {
    prepare: query => new Statement(query),
    // Все запросы пачки выполняются в одной транзакции
    batch: async statements => storage.transactionSync(() => statements.map(st => st.exec()))
  };
}

async function handle(request, env) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  if (!env.SESSION_SECRET || env.SESSION_SECRET.length < 24) return json({ error: "Не задан SESSION_SECRET (не короче 24 символов)" }, 500);
  try {
    return await route(request, env);
  } catch (e) {
    if (e instanceof HttpError) return json({ error: e.message }, e.status);
    return json({ error: "Ошибка сервера" }, 500);
  }
}

// Все данные магазина в одном объекте: запросы идут по очереди, баланс и покупки не «разъедутся»
export class Shop {
  constructor(ctx, env) {
    this.env = { ...env, DB: sqliteDb(ctx.storage) };
  }

  fetch(request) {
    return handle(request, this.env);
  }
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (!env.SHOP) return json({ error: "Не подключено хранилище SHOP (Durable Object)" }, 500);
    return env.SHOP.get(env.SHOP.idFromName("main")).fetch(request);
  }
};
