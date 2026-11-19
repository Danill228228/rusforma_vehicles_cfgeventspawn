// Встраивает data.json в index.html, чтобы сайт работал и при открытии файла двойным кликом.
// Запуск из корня репозитория: node tools/embed-data.mjs
import { readFileSync, writeFileSync } from "node:fs";

const html = readFileSync("index.html", "utf8");
const data = JSON.parse(readFileSync("data.json", "utf8"));
const safe = obj => JSON.stringify(obj).replace(/</g, "\\u003c");

const result = html.replace(
  /(<script id="embedded-data" type="application\/json">)[\s\S]*?(<\/script>)/,
  (_, a, b) => a + safe(data) + b);

writeFileSync("index.html", result);
console.log(result === html ? "index.html уже актуален" : `Готово: данные от ${data.updatedAt}`);
