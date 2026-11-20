#!/usr/bin/env node
// Картинки «ДО / ПОСЛЕ» для журнала работ: текст или код с номерами строк, либо готовое изображение,
// в рамке с заголовком, меткой и временем (МСК). Рендер — Chromium через Playwright (уже установлен).
//
// node AI_Company_DayZMods/Company/Tools/shot.js --out x.png --title "BUG-0005 · сохранение люка" --kind before \
//      --meta "RF_HumveeHatch.c" (--text file.txt | --image pic.png) [--start 38] [--hl 40-45,50] [--width 1100] [--note "..."]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const k = process.argv[i];
  if (k.startsWith('--')) args[k.slice(2)] = (process.argv[i + 1] && !process.argv[i + 1].startsWith('--')) ? process.argv[++i] : true;
}
if (!args.out || (!args.text && !args.image)) {
  console.error('нужно --out и --text или --image'); process.exit(2);
}
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const kind = args.kind === 'after' ? 'after' : args.kind === 'before' ? 'before' : 'info';
const badge = { before: ['ДО', '#b3261e'], after: ['ПОСЛЕ', '#1e7a36'], info: ['ИНФО', '#4a5568'] }[kind];
const stamp = args.time || new Date().toLocaleString('ru-RU', { timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) + ' МСК';
const width = parseInt(args.width || '1100', 10);

const hl = new Set();
String(args.hl || '').split(',').filter(Boolean).forEach(part => {
  const [a, b] = part.split('-').map(Number);
  for (let n = a; n <= (b || a); n++) hl.add(n);
});

let body;
if (args.text) {
  const lines = fs.readFileSync(args.text, 'utf8').replace(/\r/g, '').replace(/\n$/, '').split('\n');
  const start = args.start ? parseInt(args.start, 10) : null;
  body = '<div class="code">' + lines.map((ln, i) => {
    const n = start !== null ? start + i : null;
    const cls = n !== null && hl.has(n) ? ' hl' : '';
    return `<div class="ln${cls}">${n !== null ? `<span class="no">${n}</span>` : ''}<span class="tx">${esc(ln) || ' '}</span></div>`;
  }).join('') + '</div>';
} else {
  const data = fs.readFileSync(args.image).toString('base64');
  const mime = args.image.toLowerCase().endsWith('.jpg') ? 'image/jpeg' : 'image/png';
  body = `<div class="img"><img src="data:${mime};base64,${data}"></div>`;
}

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
  body { margin:0; background:#ffffff; font-family:'DejaVu Sans',sans-serif; }
  .card { width:${width}px; border:1px solid #d0d4da; border-radius:8px; overflow:hidden; }
  .head { display:flex; align-items:center; gap:12px; padding:12px 16px; background:#f3f4f6; border-bottom:1px solid #d0d4da; }
  .badge { background:${badge[1]}; color:#fff; font-weight:700; font-size:14px; padding:4px 10px; border-radius:4px; letter-spacing:.5px; }
  .title { font-weight:700; font-size:17px; color:#1f2328; flex:1; }
  .stamp { font-size:13px; color:#57606a; white-space:nowrap; }
  .meta { padding:8px 16px; font-size:13px; color:#57606a; border-bottom:1px solid #e5e7eb; }
  .code { background:#0f1419; padding:10px 0; font-family:'DejaVu Sans Mono',monospace; font-size:13px; line-height:1.5; color:#d6dde6; }
  .ln { display:flex; padding:0 16px; white-space:pre; }
  .ln.hl { background:${kind === 'after' ? 'rgba(46,160,67,.28)' : 'rgba(248,81,73,.28)'}; }
  .no { color:#6e7681; width:44px; flex:none; text-align:right; padding-right:14px; user-select:none; }
  .tx { white-space:pre-wrap; word-break:break-all; }
  .img { background:#0f1419; text-align:center; padding:8px; } .img img { max-width:100%; }
  .note { padding:10px 16px; font-size:13px; color:#1f2328; background:#fffbe6; border-top:1px solid #e5e7eb; }
</style></head><body><div class="card" id="card">
  <div class="head"><span class="badge">${badge[0]}</span><span class="title">${esc(args.title || '')}</span><span class="stamp">${esc(stamp)}</span></div>
  ${args.meta ? `<div class="meta">${esc(args.meta)}</div>` : ''}
  ${body}
  ${args.note ? `<div class="note">${esc(args.note)}</div>` : ''}
</div></body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: width + 40, height: 600 }, deviceScaleFactor: 2 });
  await page.setContent(html, { waitUntil: 'load' });
  fs.mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
  await (await page.$('#card')).screenshot({ path: args.out });
  await browser.close();
  console.log(`${args.out} (${kind}, ${stamp})`);
})().catch(e => { console.error(e.message); process.exit(1); });
