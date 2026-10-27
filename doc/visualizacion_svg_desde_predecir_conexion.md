# Generar las vistas SVG de una conexión desde `predecir_conexion`

Guía autocontenida para que un agente pueda, **sin tocar el servidor**, tomar la salida de la
herramienta MCP `predecir_conexion` (o de `POST /predict`) y generar las tres vistas 2D
(frontal, lateral y superior) como SVG, exactamente igual que las dibuja el visor web.

- Código del cliente de referencia: `production/server/web/scripts/main.js` (funciones
  `viewModel`, `drawFront`, `drawSide`, `drawTop`, `svgRect`, `svgLine`, `svgText`,
  `svgPoly`, `svgCircle`, `dimV`, `dimH`).
- El script de este documento es un **port literal** de ese código a Node.js, sin DOM.
- No requiere modificar ni reiniciar el servidor. Solo usa dos endpoints ya existentes:
  la predicción y `GET /profiles`.

> Nota: la herramienta MCP `disenar_escenarios_carga` **no** devuelve SVG. Los planos se
> generan aquí (o en el visor web) y se convierten a PDF en el cliente (sección 5), sin
> `svglib`/`cairosvg`. Si vienes de esa herramienta, cada escenario trae `codame` (las
> columnas CODAME): pásalo como `row` a `renderConnection`.

---

## 1. Qué devuelve `predecir_conexion`

La herramienta MCP `predecir_conexion` recibe `rows` (filas de entrada del modelo) y `model`
(opcional), y devuelve:

```json
{
  "model_name": "V11",
  "rows": [ { "...": "62 columnas CODAME" } ],
  "checks": [ { "...": "comprobación AISC por fila" } ]
}
```

Para dibujar se usa **`rows`** (columnas CODAME). `checks` no interviene en el dibujo.

Si no se dispone de cliente MCP, el equivalente REST es:

```http
POST /predict
Content-Type: application/json

{ "model": "V11", "rows": [ { ...inputs... } ] }
```

`/predict` devuelve además `rows_raw`; el dibujo usa `rows` (predicción ya ajustada), que es
lo mismo que muestra el visor al abrir una fila.

### Ejemplo mínimo de `prediction.json`

```json
{
  "model_name": "V11",
  "rows": [
    {
      "Unicode": "TEST001",
      "BEAM": "HEA120",
      "COLUMN": "HEA160",
      "BoltName_ep": "M20",
      "dev": 35.0,
      "p2_ep": 100.0,
      "b_ep": 160.0,
      "ThicknessName_t_ep": "15mm",
      "Lh": 92.14510296266427,
      "pfo": 35.0,
      "pfi": 52.02715873718262,
      "pb": 100.0,
      "p3": 90.0,
      "p4": 0.0,
      "p5": 0.0,
      "p6": 0.0,
      "p7": 0.0,
      "p8": 0.0,
      "p9": 0.0,
      "p10": 0.0,
      "p11": 0.0,
      "p12": 0.0,
      "ThicknessName_t_webstiff": "0mm",
      "Bws": 0.0,
      "Lws": 0.0,
      "ThicknessName_t_compstiff": "0mm",
      "ThicknessName_t_BeamHcompstiff": "0mm",
      "ThicknessName_t_tenstiff": "0mm"
    }
  ],
  "checks": []
}
```

### Campos CODAME que consume el dibujo

| Uso interno | Campo de la fila |
|---|---|
| separación al borde `e` | `dev` |
| gramil horizontal `g` | `p2_ep` |
| ancho chapa `Bp` | `b_ep` |
| espesor chapa `tp` | `ThicknessName_t_ep` (`"15mm"` o `15`) |
| altura cartela `Lh` | `Lh` |
| primera fila → ala superior | `pfo` |
| ala superior → segunda fila | `pfi` |
| 2ª → 3ª fila | `pb` |
| separaciones siguientes | `p3` … `p12` |
| rigidizador alma pilar | `ThicknessName_t_webstiff` |
| placa alma `Bws`, `Lws` | `Bws`, `Lws` |
| rigidizador compresión | `ThicknessName_t_compstiff` |
| rigidizador alma viga | `ThicknessName_t_BeamHcompstiff` |
| rigidizador tracción | `ThicknessName_t_tenstiff` |
| diámetro tornillo | `BoltName_ep` (`"M20"` → 20, por defecto 24) |
| perfiles | `BEAM`, `COLUMN` |

---

## 2. Flujo que sigue el cliente

1. `state.results = data.rows` (o `prediction.rows`).
2. `openViewer(i)`:
   - pide la geometría de `row.BEAM` y `row.COLUMN` a `GET /profiles`;
   - copia los campos editables de la fila a `VIEW.vals`;
   - construye `VIEW.sec` con `d_mm`, `bf_mm`, `tw_mm`, `tf_mm` de cada perfil.
3. `viewModel()` calcula en **mm**: `p1`, `steps`, `Lp`, `rows`, `beamTop`, `beamBot`, etc.
4. `drawFront/drawSide/drawTop` convierten mm→px con una escala por vista y emiten
   primitivas SVG (`rect`, `circle`, `line`, `polygon`, `text`).
5. `$("vFront").innerHTML = s` (etc.).

El script de abajo reproduce los pasos 2–4 sin DOM: recibe la fila + perfiles y devuelve los
tres SVG completos.

### Geometría de perfiles

El visor no adivina las cotas: las pide al catálogo del servidor.

```bash
curl "http://localhost:8080/profiles?names=HEA120,HEA160"
```

```json
{
  "profiles": {
    "HEA120": { "type": "HE", "d_mm": 114.0, "bf_mm": 120.0, "tw_mm": 5.0, "tf_mm": 8.0, "r1_mm": 12.0 },
    "HEA160": { "type": "HE", "d_mm": 152.0, "bf_mm": 160.0, "tw_mm": 6.0, "tf_mm": 9.0, "r1_mm": 15.0 }
  }
}
```

> Nota: en el catálogo EU el ancho de ala puede venir en `b_mm` con `bf_mm = 0`. El endpoint
> `/profiles` ya lo normaliza a `bf_mm`; si se pasa un JSON de catálogo crudo, el script hace
> el fallback `bf_mm || b_mm`.

Si un perfil no aparece, el cliente dibuja con ceros y avisa; el script emite un aviso por
consola. Para imágenes correctas, hay que resolver ambos perfiles.

---

## 3. Script completo: `render.js`

Guardar como `render.js`. Solo necesita Node.js ≥ 18 (usa `fetch` global). No tiene
dependencias npm.

```javascript
#!/usr/bin/env node
'use strict';
/*
 * render.js - Genera las 3 vistas SVG de una conexion a partir de una fila
 * CODAME devuelta por `predecir_conexion` (o por POST /predict), replicando
 * exactamente el dibujo del visor web (scripts/main.js).
 *
 * Uso:
 *   node render.js --pred prediction.json --profiles profiles.json --out out
 *   node render.js --pred prediction.json --server http://localhost:8080 --out out
 */

const fs = require('fs');
const path = require('path');

const P_KEYS = ['p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'p10', 'p11', 'p12'];

/* ---------------- utilidades ---------------- */
function vNum(v) {
  const s = String(v == null ? '' : v).toLowerCase().replace('mm', '').replace(',', '.').trim();
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}
function fmt(n) { return String(Math.round(n * 10) / 10); }
function escXml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* ---------------- primitivas SVG (igual que el cliente) ---------------- */
function svgRect(x, y, w, h, fill, stroke, sw) {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill || 'none'}" stroke="${stroke || 'black'}" stroke-width="${sw || 1}"/>`;
}
function svgCircle(cx, cy, r, fill) {
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" stroke="black" stroke-width="1"/>`;
}
function svgLine(x1, y1, x2, y2, stroke, dash, sw) {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke || 'black'}" stroke-width="${sw || 1}" stroke-dasharray="${dash || ''}"/>`;
}
function svgPoly(points, fill) {
  return `<polygon points="${points}" fill="${fill}" stroke="black" stroke-width="1"/>`;
}
function svgText(x, y, t, anchor, color, size) {
  return `<text x="${x}" y="${y}" font-size="${size || 11}" font-family="Segoe UI,Arial" fill="${color || '#1B2733'}" text-anchor="${anchor || 'start'}">${escXml(t)}</text>`;
}
function dimV(x, y1, y2, label, side) {
  side = side || 'left';
  const tx = side === 'left' ? x - 4 : x + 4;
  const anc = side === 'left' ? 'end' : 'start';
  return svgLine(x, y1, x, y2, '#D52B1E') +
    svgLine(x - 3, y1, x + 3, y1, '#D52B1E') +
    svgLine(x - 3, y2, x + 3, y2, '#D52B1E') +
    svgText(tx, (y1 + y2) / 2 + 4, label, anc, '#D52B1E');
}
function dimH(y, x1, x2, label) {
  return svgLine(x1, y, x2, y, '#D52B1E') +
    svgLine(x1, y - 3, x1, y + 3, '#D52B1E') +
    svgLine(x2, y - 3, x2, y + 3, '#D52B1E') +
    svgText((x1 + x2) / 2, y - 5, label, 'middle', '#D52B1E');
}

/* ---------------- modelo de dibujo (port de viewModel) ---------------- */
function viewModel(row, beam, col) {
  const V = row || {};
  const bfOf = p => (p && (p.bf_mm || p.b_mm)) || 0;
  const S = {
    beam_d: beam ? beam.d_mm : 0, beam_bf: bfOf(beam),
    beam_tw: beam ? beam.tw_mm : 0, beam_tf: beam ? beam.tf_mm : 0,
    col_d: col ? col.d_mm : 0, col_bf: bfOf(col),
    col_tw: col ? col.tw_mm : 0, col_tf: col ? col.tf_mm : 0,
  };
  const tf = vNum(S.beam_tf), bf = vNum(S.beam_bf), tw = vNum(S.beam_tw), bd = vNum(S.beam_d);
  const ctf = vNum(S.col_tf), cbf = vNum(S.col_bf), ctw = vNum(S.col_tw), cd = vNum(S.col_d);
  const e = vNum(V.dev), g = vNum(V.p2_ep), Bp = vNum(V.b_ep), tp = vNum(V.ThicknessName_t_ep), Lh = vNum(V.Lh);
  const pfo = vNum(V.pfo), pfi = vNum(V.pfi), pb = vNum(V.pb);
  const p1 = pfo + tf + pfi;
  const steps = [p1, pb, ...P_KEYS.map(k => vNum(V[k]))].filter(x => x > 0);
  const sumP = steps.reduce((a, b) => a + b, 0);
  const Lp = 2 * e + sumP;
  const rows = [e];
  let y = e;
  steps.forEach(s => { y += s; rows.push(y); });
  const beamTop = e + pfo, beamBot = beamTop + bd;
  const boltDia = parseInt(String(V.BoltName_ep || '').replace(/\D/g, ''), 10) || 24;
  return {
    tf, bf, tw, bd, ctf, cbf, ctw, cd, e, g, Bp, tp, Lh, pfo, pfi, pb, p1, steps, sumP, Lp, rows,
    beamTop, beamBot, boltDia,
    Hhaunch: Math.max(0, Lp - beamBot),
    tws: vNum(V.ThicknessName_t_webstiff), ts: vNum(V.ThicknessName_t_compstiff),
    tbs: vNum(V.ThicknessName_t_BeamHcompstiff), tst: vNum(V.ThicknessName_t_tenstiff),
    bws: vNum(V.Bws), lws: vNum(V.Lws),
  };
}

/* ---------------- vistas (port literal de drawFront/drawSide/drawTop) ---------------- */
function drawFront(m, row) {
  const W = 520, H = 620, cx = 230, top = 40;
  const maxH = Math.max(m.Lp, m.beamBot, 1);
  const scale = Math.min(0.9, (H - 90) / maxH, (W - 200) / Math.max(m.Bp, 1));
  const Y = v => top + v * scale, X = v => cx + v * scale;
  let s = '';
  s += svgRect(cx - (m.Bp / 2) * scale, top, m.Bp * scale, m.Lp * scale, '#cfd8e3');
  s += svgRect(cx - (m.bf / 2) * scale, Y(m.beamTop), m.bf * scale, m.tf * scale, 'none', '#33475b', 1.5);
  s += svgRect(cx - (m.tw / 2) * scale, Y(m.beamTop + m.tf), m.tw * scale, Math.max(0, (m.bd - 2 * m.tf)) * scale, 'none', '#33475b', 1.5);
  s += svgRect(cx - (m.bf / 2) * scale, Y(m.beamBot - m.tf), m.bf * scale, m.tf * scale, 'none', '#33475b', 1.5);
  if (m.Lh > 0) {
    const hz = m.Lh;
    s += svgRect(cx - (m.tw / 2) * scale, Y(m.beamBot), m.tw * scale, Math.max(0, hz - m.tf) * scale, 'none', '#1e88e5', 1.5);
    s += svgRect(cx - (m.bf / 2) * scale, Y(m.beamBot + hz - m.tf), m.bf * scale, m.tf * scale, 'none', '#1e88e5', 1.5);
  }
  const r = Math.max(3, (m.boltDia / 2) * scale * 0.8);
  m.rows.forEach(yy => {
    s += svgCircle(X(-m.g / 2), Y(yy), r, '#ff4500');
    s += svgCircle(X(m.g / 2), Y(yy), r, '#ff4500');
  });
  const xL = cx - (m.Bp / 2) * scale - 18;
  const xR = cx + (m.Bp / 2) * scale + 22;
  s += dimV(xL, Y(0), Y(m.rows[0]), 'e=' + fmt(m.e));
  s += dimV(xL, Y(m.rows[0]), Y(m.beamTop), 'pfo=' + fmt(m.pfo));
  if (m.rows[1] != null && m.rows[1] > m.beamTop + m.tf)
    s += dimV(xL, Y(m.beamTop + m.tf), Y(m.rows[1]), 'pfi=' + fmt(m.pfi));
  const pit = ['p2=' + fmt(m.pb), ...P_KEYS.map(k => k + '=' + fmt(vNum(row && row[k])))];
  for (let i = 1; i < m.rows.length - 1; i++)
    s += dimV(xL, Y(m.rows[i]), Y(m.rows[i + 1]), pit[i - 1] || '');
  s += dimV(xR, Y(m.beamTop), Y(m.beamBot), 'd_viga=' + fmt(m.bd), 'right');
  if (m.Lh > 0)
    s += dimV(xR, Y(m.beamBot), Y(m.beamBot + m.Lh), 'Lh=' + fmt(m.Lh), 'right');
  s += dimV(xR + 72, Y(0), Y(m.Lp), 'Lp=' + fmt(m.Lp), 'right');
  s += dimH(top - 14, X(-m.Bp / 2), X(m.Bp / 2), 'Bp=' + fmt(m.Bp));
  s += dimH(Y(m.Lp) + 18, X(-m.g / 2), X(m.g / 2), 'g=' + fmt(m.g));
  return s;
}

function drawSide(m) {
  const W = 580, H = 620, top = 40;
  const t = Math.tan(Math.PI / 3);
  const hxMM = m.Lh * t;
  let scale = Math.min(0.85, (H - 110) / Math.max(m.Lp, 1));
  const denom = m.cd + m.tp + Math.max(hxMM, 0);
  if (denom > 0) scale = Math.min(scale, (W - 160) / denom);
  scale = Math.max(scale, 0.12);
  const cRight = m.cd * scale + 90;
  const Y = v => top + v * scale;
  let s = '';
  const colTop = top - 20, colBot = top + m.Lp * scale + 20;
  s += svgRect(cRight - m.cd * scale, colTop, m.cd * scale, colBot - colTop, '#e6e6e6', 'gray');
  s += svgRect(cRight - m.ctf * scale, colTop, m.ctf * scale, colBot - colTop, '#b0c4de');
  s += svgRect(cRight - m.cd * scale, colTop, m.ctf * scale, colBot - colTop, '#b0c4de');
  if (m.tws > 0 && m.bws > 0 && m.lws > 0) {
    const wx = cRight - (m.cd / 2) * scale - (m.bws / 2) * scale;
    const wy = Y(m.beamTop + m.bd / 2) - (m.lws / 2) * scale;
    s += svgRect(wx, wy, m.bws * scale, m.lws * scale, '#4169e1', '#1e3a8a', 1.2);
    const bwsY = Math.min(wy, Y(m.beamTop)) - 18;
    s += dimH(bwsY, wx, wx + m.bws * scale, 'Bws=' + fmt(m.bws));
    s += dimV(wx - 8, wy, wy + m.lws * scale, 'Lws=' + fmt(m.lws), 'left');
  }
  s += svgRect(cRight, top, m.tp * scale, m.Lp * scale, '#708090');
  const vigaX = cRight + m.tp * scale;
  const beamPx = W - vigaX;
  s += svgRect(vigaX, Y(m.beamTop), beamPx, m.tf * scale, '#b0c4de');
  s += svgRect(vigaX, Y(m.beamTop + m.tf), beamPx, Math.max(0, (m.bd - 2 * m.tf)) * scale, '#b0c4de');
  s += svgRect(vigaX, Y(m.beamBot - m.tf), beamPx, m.tf * scale, '#b0c4de');
  if (m.Lh > 0) {
    const hx = vigaX + hxMM * scale;
    s += svgPoly(`${vigaX},${Y(m.beamBot)} ${hx},${Y(m.beamBot)} ${vigaX},${Y(m.beamBot + m.Lh)}`, '#a2b5cd');
  }
  if (m.tst > 0) s += svgRect(cRight - m.cd * scale + m.ctf * scale, Y(m.beamTop), Math.max(0, (m.cd - 2 * m.ctf)) * scale, m.tst * scale, '#00008b');
  if (m.ts > 0) s += svgRect(cRight - m.cd * scale + m.ctf * scale, Y(m.beamBot - m.ts), Math.max(0, (m.cd - 2 * m.ctf)) * scale, m.ts * scale, '#00008b');
  if (m.tbs > 0) s += svgRect(vigaX + beamPx - 30, Y(m.beamTop + m.tf), m.tbs * scale, Math.max(0, (m.bd - 2 * m.tf)) * scale, '#00008b');
  m.rows.forEach(yy => { s += svgLine(cRight - m.ctf * scale - 10, Y(yy), vigaX, Y(yy), '#ff4500', '4,2'); });
  const xL = cRight - m.cd * scale - 18;
  s += dimV(xL, Y(0), Y(m.rows[0]), 'e=' + fmt(m.e));
  s += dimV(xL, Y(m.rows[0]), Y(m.beamTop), 'pfo=' + fmt(m.pfo));
  if (m.Lh > 0)
    s += dimV(vigaX + hxMM * scale, Y(m.beamBot), Y(m.beamBot + m.Lh), 'Lh=' + fmt(m.Lh), 'right');
  s += dimH(top - 14, cRight, vigaX, 'tp=' + fmt(m.tp));
  return s;
}

function drawTop(m) {
  const W = 500, cy = 180;
  const x0 = 50, beamPx = 190;
  const avail = W - x0 - beamPx - 70;
  const scale = Math.min(0.8, avail / Math.max(m.cd + m.tp, 1));
  const cx = x0 + m.cd * scale;
  const yTop = v => cy - v * scale;
  const steel = '#b0c4de', plate = '#708090', stiff = '#00008b', webStiff = '#4169e1';
  let s = '';
  s += svgRect(cx - m.cd * scale, cy - (m.cbf / 2) * scale, m.ctf * scale, m.cbf * scale, steel, '#33475b', 1);
  s += svgRect(cx - m.ctf * scale, cy - (m.cbf / 2) * scale, m.ctf * scale, m.cbf * scale, steel);
  s += svgRect(cx - m.cd * scale + m.ctf * scale, yTop(m.ctw / 2), Math.max(0, (m.cd - 2 * m.ctf)) * scale, m.ctw * scale, steel);
  if (m.tws > 0) s += svgRect(cx - m.cd * scale + m.ctf * scale, yTop(m.ctw / 2) - m.tws * scale, Math.max(0, (m.cd - 2 * m.ctf)) * scale, m.tws * scale, webStiff);
  s += svgRect(cx, cy - (m.Bp / 2) * scale, m.tp * scale, m.Bp * scale, plate);
  s += svgRect(cx + m.tp * scale, cy - (m.bf / 2) * scale, beamPx, m.bf * scale, steel);
  s += svgLine(cx + m.tp * scale, cy, cx + m.tp * scale + beamPx, cy, 'black', '5,5');
  if (m.tbs > 0) s += svgRect(cx + m.tp * scale + beamPx - 30, cy - (m.bf / 2) * scale, m.tbs * scale, m.bf * scale, stiff);
  s += dimH(cy + m.Bp * scale / 2 + 16, cx, cx + m.tp * scale, 'tp=' + fmt(m.tp));
  if (m.tbs > 0) {
    const tx = cx + m.tp * scale + beamPx - 30 + m.tbs * scale;
    s += svgLine(tx, cy - (m.bf / 2) * scale, tx + 18, cy - (m.bf / 2) * scale - 12, '#D52B1E');
    s += svgText(tx + 20, cy - (m.bf / 2) * scale - 14, 'tbs=' + fmt(m.tbs), 'start', '#D52B1E');
  }
  if (m.tws > 0) {
    const wx = cx - m.cd * scale + (m.cd - 2 * m.ctf) * scale * 0.5;
    const wy = yTop(m.ctw / 2) - m.tws * scale;
    s += svgLine(wx, wy, wx, wy - 18, '#D52B1E');
    s += svgText(wx + 4, wy - 20, 'tws=' + fmt(m.tws), 'start', '#D52B1E');
  }
  return s;
}

/* ---------------- API ---------------- */
function standaloneSvg(inner, W, H) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">\n${inner}\n</svg>\n`;
}

function renderConnection(row, beam, col) {
  const m = viewModel(row, beam, col);
  return {
    front: standaloneSvg(drawFront(m, row), 520, 620),
    side: standaloneSvg(drawSide(m), 580, 620),
    top: standaloneSvg(drawTop(m), 500, 380),
    model: m,
  };
}

async function fetchProfiles(names, server) {
  const uniq = [...new Set(names.filter(Boolean).map(n => String(n).trim()))];
  const url = server.replace(/\/$/, '') + '/profiles?names=' + encodeURIComponent(uniq.join(','));
  const r = await fetch(url);
  if (!r.ok) throw new Error('GET /profiles -> HTTP ' + r.status);
  const d = await r.json();
  return d.profiles || {};
}

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : def;
}

async function main() {
  const predPath = arg('--pred');
  if (!predPath) {
    console.error('Uso: node render.js --pred prediction.json [--profiles profiles.json | --server URL] [--out dir]');
    process.exit(2);
  }
  const pred = JSON.parse(fs.readFileSync(predPath, 'utf8'));
  const rows = Array.isArray(pred) ? pred : (pred.rows || []);
  if (!rows.length) throw new Error('La prediccion no trae filas (rows vacio)');

  let profiles;
  const profPath = arg('--profiles');
  if (profPath) {
    const raw = JSON.parse(fs.readFileSync(profPath, 'utf8'));
    profiles = raw.profiles || raw;
  } else {
    const server = arg('--server', 'http://localhost:8080');
    profiles = await fetchProfiles(rows.map(r => r.BEAM).concat(rows.map(r => r.COLUMN)), server);
  }

  const out = arg('--out', 'out');
  fs.mkdirSync(out, { recursive: true });

  rows.forEach((row, i) => {
    const beam = profiles[row.BEAM] || null;
    const col = profiles[row.COLUMN] || null;
    if (!beam) console.warn(`[aviso] perfil de viga no encontrado: ${row.BEAM}`);
    if (!col) console.warn(`[aviso] perfil de pilar no encontrado: ${row.COLUMN}`);
    const svgs = renderConnection(row, beam, col);
    const base = String(row.Unicode || row.UNICODE || ('conexion_' + (i + 1))).replace(/[^\w.-]+/g, '_');
    fs.writeFileSync(path.join(out, `${base}_front.svg`), svgs.front, 'utf8');
    fs.writeFileSync(path.join(out, `${base}_side.svg`), svgs.side, 'utf8');
    fs.writeFileSync(path.join(out, `${base}_top.svg`), svgs.top, 'utf8');
    console.log(`[ok] ${base}: front/side/top  (Lp=${fmt(svgs.model.Lp)} mm, Lh=${fmt(svgs.model.Lh)} mm)`);
  });
}

module.exports = { renderConnection, viewModel, drawFront, drawSide, drawTop, fetchProfiles };

if (require.main === module) {
  main().catch(e => { console.error(e); process.exit(1); });
}
```

---

## 4. Ejecución

### 4.1 Con un fichero de perfiles

```bash
# profiles.json = respuesta de GET /profiles (o un mapa { "HEA120": {...} })
node render.js --pred prediction.json --profiles profiles.json --out out
```

### 4.2 Pidiendo los perfiles al servidor

```bash
node render.js --pred prediction.json --server http://localhost:8080 --out out
```

### 4.3 Salida

```
out/
  TEST001_front.svg   # 520 x 620
  TEST001_side.svg    # 580 x 620
  TEST001_top.svg     # 500 x 380
```

Cada archivo es un SVG independiente (`xmlns` + `viewBox`), listo para abrir en navegador,
Inkscape o incrustar en un informe. El script imprime por consola el `Lp` y `Lh` calculados
para verificar que la geometría es coherente.

### 4.4 Uso como módulo

```javascript
const { renderConnection } = require('./render.js');
const svgs = renderConnection(row, beam, col);
fs.writeFileSync('x_front.svg', svgs.front);
```

---

## 5. De SVG a PDF (sin svglib ni cairosvg)

> El servidor **no** devuelve SVG: los planos se generan en el cliente con `render.js`
> (sección 3) o se toman del visor web. La conversión a PDF tampoco necesita librerías de
> Python: cualquier navegador moderno renderiza el SVG y lo imprime a PDF.

### 5.1 Empaquetar las 3 vistas en un HTML autocontenido

`render.js` deja `out/<Unicode>_front.svg`, `_side.svg` y `_top.svg`. Para imprimir en PDF
basta envolverlos en un HTML. Guarda este `to_html.js` junto a `render.js`:

```javascript
#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');

const dir = process.argv[2] || 'out';
const bases = [...new Set(fs.readdirSync(dir)
  .filter(f => f.endsWith('_front.svg'))
  .map(f => f.replace(/_front\.svg$/, '')))];

for (const base of bases) {
  const read = s => fs.readFileSync(path.join(dir, `${base}_${s}.svg`), 'utf8');
  const html = `<!doctype html>
<html><head><meta charset="utf-8"><title>${base}</title>
<style>
  @page { size: A4 landscape; margin: 8mm; }
  body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; }
  .row { display: flex; gap: 6mm; align-items: flex-start; }
  .vista { flex: 1; text-align: center; }
  .vista h3 { margin: 0 0 2mm; font-size: 12px; color: #1B2733; }
  .vista svg { width: 100%; height: auto; max-height: 180mm; }
</style></head>
<body>
  <div class="row">
    <div class="vista"><h3>Frontal</h3>${read('front')}</div>
    <div class="vista"><h3>Lateral</h3>${read('side')}</div>
    <div class="vista"><h3>Superior</h3>${read('top')}</div>
  </div>
</body></html>`;
  fs.writeFileSync(path.join(dir, `${base}.html`), html, 'utf8');
  console.log(`[ok] ${base}.html`);
}
```

```bash
node to_html.js out
```

### 5.2 Convertir a PDF con Edge o Chrome (headless)

No hace falta `svglib` ni `cairosvg`: el navegador ya renderiza el SVG. En Windows, Edge
suele estar instalado:

```powershell
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
Get-ChildItem out\*.html | ForEach-Object {
  $pdf = [IO.Path]::ChangeExtension($_.FullName, ".pdf")
  $url = "file:///" + $_.FullName.Replace('\', '/')
  & $edge --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$pdf" $url
}
```

Con Chrome es la misma orden cambiando el ejecutable:

```powershell
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
# & $chrome --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$pdf" $url
```

Notas:
- `--no-pdf-header-footer` quita encabezados/pies del navegador (en algunas versiones se
  llama `--print-to-pdf-no-header`).
- Si tu navegador no acepta `--headless=new`, usa `--headless`.
- La URL debe ser absoluta (`file:///...`).
- Si el navegador está abierto, añade `--user-data-dir="$env:TEMP\edge-pdf"` para usar un
  perfil aislado y evitar bloqueos.
- Alternativa sin comandos: abre el `.html` y usa **Imprimir → Guardar como PDF**.

### 5.3 Alternativas

- `wkhtmltopdf out\<Unicode>.html out\<Unicode>.pdf` si está instalado.
- `sharp` o ImageMagick solo si necesitas PNG (no para PDF).
- Para un PDF directo desde el servidor harían falta librerías nativas (`cairosvg`), por eso
  este flujo se resuelve en el cliente.


---

## 6. Fidelidad: constantes y decisiones del dibujo

Estas son las mismas que aplica el cliente; si se cambian, hay que cambiarlas en ambos sitios.

### Escalas y orígenes

| Vista | Tamaño | Escala | Origen |
|---|---|---|---|
| Frontal | 520×620 | `min(0.9, 530/max(Lp, beamBot, 1), 320/max(Bp,1))` | `cx=230`, `top=40` |
| Lateral | 580×620 | `min(0.85, 510/max(Lp,1), 420/(cd+tp+Lh·tan60))`, mínimo `0.12` | `cRight=cd·scale+90`, `top=40` |
| Superior | 500×380 | `min(0.8, 190/max(cd+tp,1))` | `x0=50`, `cy=180`, `beamPx=190` |

### Derivados (`viewModel`)

- `p1 = pfo + tf_viga + pfi`
- `steps = [p1, pb, p3…p12]` filtrando `> 0`
- `Lp = 2·e + Σsteps`
- `rows = [e, e+steps[0], e+steps[0]+steps[1], …]`
- `beamTop = e + pfo`; `beamBot = beamTop + d_viga`
- `boltDia = dígitos de BoltName_ep` (defecto 24)
- Cartela: `Lh` es altura; proyección horizontal `Lh·tan(60°)`.

### Colores

| Elemento | Color |
|---|---|
| Chapa frontal | `#cfd8e3` |
| Contorno viga | `#33475b` |
| Ala/cartela (frontal) | `#1e88e5` |
| Tornillos | `#ff4500` |
| Pilar | `#e6e6e6` / alas `#b0c4de` |
| Chapa (lateral) | `#708090` |
| Cartela (lateral) | `#a2b5cd` |
| Rigidizadores | `#00008b` |
| Placa alma | `#4169e1` |
| Cotas | `#D52B1E` |

### Detalles geométricos

- **Frontal:** chapa `Bp×Lp` centrada en `cx`; viga dibujada con alas y alma; cartela azul si
  `Lh>0`; tornillos a `±g/2` en cada fila `rows`; cotas `e, pfo, pfi, p2…, d_viga, Lh, Lp,
  Bp, g`.
- **Lateral:** pilar de altura `Lp`; chapa de espesor `tp`; viga hasta el borde derecho;
  cartela triangular `(vigaX, beamBot) → (vigaX+Lh·tan60·scale, beamBot) → (vigaX,
  beamBot+Lh·scale)`; placa alma `Bws×Lws` centrada en canto de pilar y viga, con `Bws` por
  encima de `tst`; rigidizadores `tst/ts/tbs`; líneas de tornillos discontinuas `4,2`; cotas
  `e, pfo, Lh, tp`.
- **Superior:** sección del pilar (alas + alma), placa `tp×Bp`, viga `beamPx×bf`, rigidizador
  `tws` en el alma del pilar, `tbs` en el alma de la viga; cotas `tp`, `tbs`, `tws`.

### Guardas

- `Math.max(0, …)` en alturas/espesores para no generar rectángulos negativos.
- Si `Lh = 0`, no se dibuja cartela ni su cota.
- Si `tws = 0` no hay placa alma; si `tbs = 0` no hay rigidizador de viga.
- Si falta un perfil, sus cotas son 0 y el dibujo degenera: resolver siempre `BEAM` y
  `COLUMN`.

---

## 7. Checklist para el agente

1. Obtener la predicción:
   - MCP: llamar `predecir_conexion` con `{ rows: [...], model: "" }`;
   - o REST: `POST /predict` con `{ model, rows }`.
2. Guardar la respuesta como `prediction.json` (o usar `rows` directamente).
3. Resolver perfiles:
   - `GET /profiles?names=<BEAM>,<COLUMN>,...`, o usar un `profiles.json` ya descargado.
4. Guardar el script de la sección 3 como `render.js`.
5. Ejecutar:
   ```bash
   node render.js --pred prediction.json --profiles profiles.json --out out
   ```
6. Verificar que existen `out/<Unicode>_front.svg`, `_side.svg`, `_top.svg` y que no están
   vacíos.
7. (Opcional) Convertir a PDF **sin** `svglib`/`cairosvg`: `node to_html.js out` y Edge/Chrome
   headless (sección 5).
8. Si se necesita otra vista o otro tamaño, cambiar solo las constantes `W`, `H`, `top`,
   `cx`/`cy` de la vista correspondiente; el resto es proporcional.

---

## 8. Resumen

- No hace falta implementar nada en el servidor: la predicción y el catálogo ya están
  expuestos.
- El dibujo es una función pura de `(row, beam, col)` → tres cadenas SVG.
- El port mantiene **las mismas coordenadas, escalas, colores y cotas** que
  `scripts/main.js`, por lo que las imágenes coinciden con el visor web.
- Solo hay que cuidar la resolución de perfiles y, si se rasteriza, la fuente.
- Para PDF no se necesitan `svglib` ni `cairosvg`: HTML autocontenido + navegador headless
  (sección 5). La herramienta MCP `disenar_escenarios_carga` no devuelve SVG.
