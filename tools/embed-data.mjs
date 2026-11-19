// Встраивает data.json и точки спавна из rusforma_vehicles_cfgeventspawn в index.html,
// чтобы сайт работал и при открытии файла двойным кликом.
// Запуск из корня репозитория: node tools/embed-data.mjs
import { readFileSync, writeFileSync } from "node:fs";

const html = readFileSync("index.html", "utf8");
const data = JSON.parse(readFileSync("data.json", "utf8"));

// Читает файл последовательно: точка относится к последнему открытому <event>.
// Так файл разбирается правильно, даже если где-то пропущен </event>.
function parseSpawns(src) {
  const out = [];
  let event = null, pending = null;
  const re = /<event name="([^"]+)"\s*>|<!--\s*([\s\S]*?)\s*-->|<pos x="([-\d.]+)" z="([-\d.]+)"[^>]*\/>/g;
  for (const t of src.matchAll(re)) {
    if (t[1] !== undefined) { event = t[1]; pending = null; continue; }
    if (t[2] !== undefined) {
      const m = t[2].match(/^Vehicle \d+:\s*(.+)$/);
      pending = m ? m[1].trim() : null;
      continue;
    }
    if (!event) continue;
    const label = pending || event.replace(/^Vehicle(CrSk_)?/, "");
    out.push({ name: label.replace(/_/g, " "), x: Math.round(+t[3] * 10) / 10, z: Math.round(+t[4] * 10) / 10 });
    pending = null;
  }
  return out;
}

const points = parseSpawns(readFileSync("rusforma_vehicles_cfgeventspawn", "utf8"));
const safe = obj => JSON.stringify(obj).replace(/</g, "\\u003c");

let result = html.replace(
  /(<script id="embedded-data" type="application\/json">)[\s\S]*?(<\/script>)/,
  (_, a, b) => a + safe(data) + b);
result = result.replace(
  /(<script id="map-data" type="application\/json">)[\s\S]*?(<\/script>)/,
  (_, a, b) => a + safe(points) + b);

if (result === html) console.log("index.html уже актуален");
writeFileSync("index.html", result);
console.log(`Готово: данные от ${data.updatedAt}, точек спавна: ${points.length}`);
