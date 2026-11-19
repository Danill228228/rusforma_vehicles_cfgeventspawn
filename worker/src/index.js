// DawnLine: вход через Steam и комментарии под модами.
// Cloudflare Worker + база D1. Как развернуть — в worker/README.md.
//
// Переменные (Settings → Variables):
//   SITE_URL         — адрес сайта, куда возвращать после входа, например https://danill228228.github.io/rusforma_vehicles_cfgeventspawn/
//   ADMIN_STEAM_IDS  — Steam ID администраторов через запятую (могут удалять комментарии и блокировать)
//   SESSION_SECRET   — секрет (Secret): длинная случайная строка для подписи входа
//   STEAM_API_KEY    — (необязательно, Secret) ключ Steam Web API для имени и аватара игрока
// Привязка базы: D1 с именем переменной DB.

const STEAM_OPENID = "https://steamcommunity.com/openid/login";
const SESSION_DAYS = 30;
const MAX_TEXT = 1000;
const COOLDOWN_SEC = 20;

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, mod TEXT NOT NULL, steamid TEXT NOT NULL, text TEXT NOT NULL, ts INTEGER NOT NULL)`,
  `CREATE INDEX IF NOT EXISTS idx_comments_mod ON comments (mod, ts)`,
  `CREATE TABLE IF NOT EXISTS users (steamid TEXT PRIMARY KEY, name TEXT NOT NULL, avatar TEXT NOT NULL, updated INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS bans (steamid TEXT PRIMARY KEY, ts INTEGER NOT NULL)`
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

const fail = (status, error) => json({ error }, status);

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
  const body = `${steamid}.${exp}`;
  return `${body}.${await hmac(env.SESSION_SECRET, body)}`;
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

/* ---------- Steam ---------- */

function siteUrl(env) {
  const u = new URL(env.SITE_URL);
  if (u.protocol !== "https:" && u.hostname !== "127.0.0.1" && u.hostname !== "localhost") throw new Error("SITE_URL должен начинаться с https://");
  return u;
}

function startLogin(request, env) {
  const self = new URL(request.url);
  const returnTo = `${self.origin}/auth/steam/callback`;
  const params = new URLSearchParams({
    "openid.ns": "http://specs.openid.net/auth/2.0",
    "openid.mode": "checkid_setup",
    "openid.return_to": returnTo,
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

  if (q.get("openid.mode") !== "id_res") return backWith("mods&steam_error=cancel");
  const returnTo = q.get("openid.return_to") || "";
  if (!returnTo.startsWith(`${self.origin}/auth/steam/callback`)) return backWith("mods&steam_error=bad");
  const claimed = q.get("openid.claimed_id") || "";
  const m = claimed.match(/^https:\/\/steamcommunity\.com\/openid\/id\/(\d{17})$/);
  if (!m) return backWith("mods&steam_error=bad");

  // Спрашиваем у самого Steam, что ответ настоящий
  const check = new URLSearchParams();
  for (const [k, v] of q) if (k.startsWith("openid.")) check.set(k, v);
  check.set("openid.mode", "check_authentication");
  const res = await fetch(env.STEAM_OPENID_URL || STEAM_OPENID, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: check.toString()
  });
  const text = await res.text();
  if (!/is_valid\s*:\s*true/.test(text)) return backWith("mods&steam_error=bad");

  const steamid = m[1];
  await ensureSchema(env.DB);
  await saveProfile(env, steamid);
  return backWith(`mods&steam=${await makeToken(env, steamid)}`);
}

function cleanAvatar(url) {
  return /^https:\/\/(avatars\.(steamstatic|akamai\.steamstatic|cloudflare\.steamstatic)\.com|steamcdn-a\.akamaihd\.net)\//.test(url || "") ? url : "";
}

async function fetchProfile(env, steamid) {
  try {
    if (env.STEAM_API_KEY) {
      const r = await fetch(`https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key=${encodeURIComponent(env.STEAM_API_KEY)}&steamids=${steamid}`);
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
  await env.DB.prepare(
    `INSERT INTO users (steamid, name, avatar, updated) VALUES (?1, ?2, ?3, ?4)
     ON CONFLICT(steamid) DO UPDATE SET name = ?2, avatar = ?3, updated = ?4`
  ).bind(steamid, name, cleanAvatar(p.avatar), Date.now()).run();
}

/* ---------- комментарии ---------- */

const validMod = mod => typeof mod === "string" && /^[\w-]{1,64}$/.test(mod);

async function listComments(env, mod) {
  if (!validMod(mod)) return fail(400, "Неверный мод");
  const { results } = await env.DB.prepare(
    `SELECT c.id, c.steamid, c.text, c.ts, u.name, u.avatar FROM comments c
     LEFT JOIN users u ON u.steamid = c.steamid WHERE c.mod = ?1 ORDER BY c.ts ASC LIMIT 500`
  ).bind(mod).all();
  return json({ comments: results });
}

async function counts(env) {
  const { results } = await env.DB.prepare(`SELECT mod, COUNT(*) AS n FROM comments GROUP BY mod`).all();
  const out = {};
  for (const r of results) out[r.mod] = r.n;
  return json({ counts: out });
}

async function addComment(request, env, steamid) {
  let body;
  try { body = await request.json(); } catch (e) { return fail(400, "Неверный запрос"); }
  const mod = body && body.mod;
  const text = String((body && body.text) || "").replace(/\r\n?/g, "\n").trim();
  if (!validMod(mod)) return fail(400, "Неверный мод");
  if (!text) return fail(400, "Пустой комментарий");
  if (text.length > MAX_TEXT) return fail(400, `Не больше ${MAX_TEXT} символов`);

  const banned = await env.DB.prepare(`SELECT 1 FROM bans WHERE steamid = ?1`).bind(steamid).first();
  if (banned) return fail(403, "Ты не можешь оставлять комментарии");

  const last = await env.DB.prepare(`SELECT MAX(ts) AS ts FROM comments WHERE steamid = ?1`).bind(steamid).first();
  if (!isAdmin(env, steamid) && last && last.ts && Date.now() - last.ts < COOLDOWN_SEC * 1000) {
    return fail(429, `Подожди ${COOLDOWN_SEC} секунд между комментариями`);
  }

  const ts = Date.now();
  const r = await env.DB.prepare(`INSERT INTO comments (mod, steamid, text, ts) VALUES (?1, ?2, ?3, ?4)`).bind(mod, steamid, text, ts).run();
  return json({ ok: true, id: r.meta.last_row_id, ts }, 201);
}

async function deleteComment(env, steamid, id) {
  const row = await env.DB.prepare(`SELECT steamid FROM comments WHERE id = ?1`).bind(id).first();
  if (!row) return fail(404, "Комментарий не найден");
  if (row.steamid !== steamid && !isAdmin(env, steamid)) return fail(403, "Можно удалять только свои комментарии");
  await env.DB.prepare(`DELETE FROM comments WHERE id = ?1`).bind(id).run();
  return json({ ok: true });
}

async function ban(env, steamid, target, removeAll) {
  if (!isAdmin(env, steamid)) return fail(403, "Только для администратора");
  if (!/^\d{17}$/.test(target || "")) return fail(400, "Неверный Steam ID");
  if (isAdmin(env, target)) return fail(400, "Нельзя заблокировать администратора");
  const stmts = [env.DB.prepare(`INSERT OR REPLACE INTO bans (steamid, ts) VALUES (?1, ?2)`).bind(target, Date.now())];
  if (removeAll) stmts.push(env.DB.prepare(`DELETE FROM comments WHERE steamid = ?1`).bind(target));
  await env.DB.batch(stmts);
  return json({ ok: true });
}

/* ---------- маршруты ---------- */

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (!env.SESSION_SECRET || env.SESSION_SECRET.length < 24) return fail(500, "Не задан SESSION_SECRET (не короче 24 символов)");
    if (!env.DB) return fail(500, "Не подключена база D1 (переменная DB)");

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    try {
      if (path === "/auth/steam" && request.method === "GET") return startLogin(request, env);
      if (path === "/auth/steam/callback" && request.method === "GET") return await finishLogin(request, env);

      await ensureSchema(env.DB);
      const me = await readToken(env, request);

      if (path === "/" ) return json({ ok: true, service: "dawnline-comments" });

      if (path === "/me" && request.method === "GET") {
        if (!me) return fail(401, "Нужно войти через Steam");
        const u = await env.DB.prepare(`SELECT name, avatar FROM users WHERE steamid = ?1`).bind(me).first();
        const banned = await env.DB.prepare(`SELECT 1 FROM bans WHERE steamid = ?1`).bind(me).first();
        return json({ steamid: me, name: u ? u.name : "", avatar: u ? u.avatar : "", admin: isAdmin(env, me), banned: !!banned });
      }

      if (path === "/comments/counts" && request.method === "GET") return await counts(env);
      if (path === "/comments" && request.method === "GET") return await listComments(env, url.searchParams.get("mod"));

      if (path === "/comments" && request.method === "POST") {
        if (!me) return fail(401, "Нужно войти через Steam");
        return await addComment(request, env, me);
      }

      const del = path.match(/^\/comments\/(\d+)$/);
      if (del && request.method === "DELETE") {
        if (!me) return fail(401, "Нужно войти через Steam");
        return await deleteComment(env, me, Number(del[1]));
      }

      if (path === "/ban" && request.method === "POST") {
        if (!me) return fail(401, "Нужно войти через Steam");
        const body = await request.json().catch(() => ({}));
        return await ban(env, me, String(body.steamid || ""), !!body.removeAll);
      }

      return fail(404, "Не найдено");
    } catch (e) {
      return fail(500, "Ошибка сервера");
    }
  }
};
