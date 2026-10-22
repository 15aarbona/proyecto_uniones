/* =====================================================================
   Estado Global
   ===================================================================== */
const $ = id => document.getElementById(id);
let SCHEMA = { model: null, inputs: [], result_columns: [] };

const state = { rows: [], results: [] };
let _checkTokens = {};

const escHtml = v => String(v == null ? "" : v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const escAttr = v => escHtml(v).replace(/"/g,"&quot;");

/* Helper seguro para obtener variaciones de una conexión */
function getConnVariations(connIdx) {
  const conn = state.results[connIdx];
  if (!conn) return [];
  if (Array.isArray(conn.variations) && conn.variations.length > 0) {
    return conn.variations;
  }
  const r = conn.data || conn;
  const lbl = r.Escenario || r.escenario || r.descripcion || "Diseño Principal";
  return [{
    label: lbl,
    tipo: "E1",
    data: r,
    adjusted: { ...r },
    raw: conn.raw || r,
    check: conn.check || null,
    adjustedCheck: conn.check ? JSON.parse(JSON.stringify(conn.check)) : null,
    status: conn.status || (conn.check?.cumple ? "CUMPLE" : "NO CUMPLE"),
    accepted: false
  }];
}

/* =====================================================================
   Formulario dinámico
   ===================================================================== */
function renderForm(){
  const form = $("form");
  form.innerHTML = "";
  if (!SCHEMA.inputs.length){
    form.innerHTML = `<div class="empty">Sin esquema: no hay modelo cargado.</div>`;
    return;
  }
  SCHEMA.inputs.forEach(c => {
    const box = document.createElement("div");
    box.className = "f"; box.dataset.key = c.key;
    const id = "in_" + c.key;
    const desc = c.description ? ` <small>· ${escHtml(c.description)}</small>` : "";
    const lab = `<label for="${id}">${escHtml(c.key)}${desc}</label>`;
    let ctl;
    if (c.type === "categorical"){
      const opts = c.options || [];
      if (opts.length > 25){
        const dl = "dl_" + c.key;
        ctl = `<input id="${id}" list="${dl}" autocomplete="off" placeholder="Escribe para buscar">` +
              `<datalist id="${dl}">${opts.map(o => `<option value="${escAttr(o)}">`).join("")}</datalist>`;
      } else {
        ctl = `<select id="${id}"><option value="">— Selecciona —</option>` +
              opts.map(o => `<option value="${escAttr(o)}">${escHtml(o)}</option>`).join("") + `</select>`;
      }
    } else if (c.type === "bool"){
      ctl = `<select id="${id}"><option value="">—</option><option value="true">true</option><option value="false">false</option></select>`;
    } else if (c.type === "number"){
      ctl = `<input id="${id}" type="number" step="any" autocomplete="off">`;
    } else {
      ctl = `<input id="${id}" type="text" autocomplete="off">`;
    }
    box.innerHTML = lab + ctl + `<div class="msg"></div>`;
    form.appendChild(box);
  });
}

function readForm(){
  let ok = true; const row = {};
  SCHEMA.inputs.forEach(c => {
    const box = $("form").querySelector(`[data-key="${c.key}"]`);
    const el = $("in_" + c.key);
    const val = (el && el.value != null ? el.value : "").trim();
    let msg = "";
    if (val !== "" && c.type === "categorical" && Array.isArray(c.options) && c.options.length){
      const m = c.options.find(o => String(o).toLowerCase() === val.toLowerCase());
      if (m === undefined) msg = "No está en el catálogo"; else row[c.key] = m;
    } else if (val !== ""){
      row[c.key] = (c.type === "number") ? Number(val) : val;
    }
    box.classList.toggle("err", !!msg);
    box.querySelector(".msg").textContent = msg;
    if (msg) ok = false;
  });
  return ok ? row : null;
}

/* =====================================================================
   Carga de Excel / CSV
   ===================================================================== */
$("btnUploadExcel").onclick = () => $("excelFileInput").click();

$("excelFileInput").onchange = (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (evt) => {
    try {
      const data = new Uint8Array(evt.target.result);
      const workbook = XLSX.read(data, { type: "array" });
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      const json = XLSX.utils.sheet_to_json(worksheet, { defval: "" });

      if (!json.length) { setStatus("bad", "El archivo Excel está vacío."); return; }

      if (json[0].Escenario || json[0]["Unicode origen"] || json[0].escenario) {
        state.results = parseScenariosResponse({ rows: json }, []);
        renderResults();
        renderAcceptedTable();
        setStatus("ok", `Se han cargado ${state.results.length} conexiones con sus variaciones desde "${file.name}".`);
        return;
      }

      if (!SCHEMA.inputs.length) { setStatus("bad", "No hay esquema de modelo cargado."); return; }

      let count = 0;
      json.forEach(rawRow => {
        const rowNorm = {};
        Object.keys(rawRow).forEach(k => { rowNorm[k.trim().toLowerCase()] = rawRow[k]; });
        const newRow = {};
        SCHEMA.inputs.forEach(c => {
          const keyLower = c.key.toLowerCase();
          if (rowNorm[keyLower] !== undefined && rowNorm[keyLower] !== "") {
            let val = rowNorm[keyLower];
            if (c.type === "number" && typeof val !== "number") {
              const num = Number(String(val).replace(",", "."));
              if (!isNaN(num)) val = num;
            }
            newRow[c.key] = val;
          }
        });
        if (Object.keys(newRow).length > 0) { state.rows.push(newRow); count++; }
      });
      renderTable();
      setStatus("ok", `Se han cargado ${count} filas desde "${file.name}".`);
    } catch (err) {
      setStatus("bad", "Error procesando el archivo", err.message);
    }
    $("excelFileInput").value = "";
  };
  reader.readAsArrayBuffer(file);
};

/* =====================================================================
   Tablas de Trabajo
   ===================================================================== */
function table(rows, cols, withDelete){
  if (!rows.length) return `<div class="empty">Todavía no hay combinaciones. Rellena el formulario o carga un Excel.</div>`;
  const head = cols.map(c => `<th>${escHtml(c)}</th>`).join("") + (withDelete ? "<th></th>" : "");
  const body = rows.map((r, i) =>
    "<tr>" + cols.map(c => `<td>${escHtml(r[c] ?? "")}</td>`).join("") +
    (withDelete ? `<td class="x"><button data-del="${i}" title="Quitar fila">✕</button></td>` : "") + "</tr>"
  ).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderTable(){
  const cols = SCHEMA.inputs.map(c => c.key);
  $("tbl").innerHTML = table(state.rows, cols, true);
  $("count").textContent = state.rows.length;
  $("send").disabled = $("clear").disabled = !state.rows.length;
  $("tbl").querySelectorAll("[data-del]").forEach(b => b.onclick = () => { state.rows.splice(+b.dataset.del, 1); renderTable(); });
}

/* =====================================================================
   Renderizado de la Pantalla Inicial (Sección 1: Resumen por Conexión)
   ===================================================================== */
function renderResults(){
  const res = state.results;
  $("resSec").style.display = res.length ? "" : "none";
  if (!res.length){ renderAcceptedTable(); return; }

  const head = `
    <th>Conexión (Unicode)</th>
    <th title="Visualizar Plano 2D">Plano 2D</th>
    <th>Selección de Variantes Aceptadas</th>
  `;

  const body = res.map((conn, connIdx) => {
    const vars = getConnVariations(connIdx);
    const activeVar = vars[conn.activeVarIndex || 0] || vars[0];
    const unicodeVal = activeVar?.data?.["Unicode origen"] || activeVar?.data?.Unicode || (`Conexión_${connIdx + 1}`);

    const cardsHtml = `<div class="var-cards-wrap">` +
      vars.map((v, vI) => {
        const st = v.status || (v.check?.cumple ? "CUMPLE" : "NO CUMPLE");
        const badgeCls = st === "CUMPLE" ? "ok" : st === "NO CUMPLE" ? "bad" : "mod";
        const isChecked = !!v.accepted;

        return `
          <div class="var-card-item ${isChecked ? "accepted" : ""}">
            <label>
              <input type="checkbox" class="var-accept-chk" data-conn="${connIdx}" data-var="${vI}" ${isChecked ? "checked" : ""}>
              <span>${escHtml(v.label)}</span>
            </label>
            <span class="badge ${badgeCls}">${escHtml(st)}</span>
          </div>
        `;
      }).join("") + `</div>`;

    return `<tr>` +
      `<td><b style="color:var(--tr-navy); font-size:14px;">${escHtml(unicodeVal)}</b></td>` +
      `<td><button class="btn ghost vbtn" data-view-conn="${connIdx}" data-view-var="${conn.activeVarIndex || 0}" style="padding:4px 10px; font-size:13px;">👁 Ver Plano 2D</button></td>` +
      `<td>${cardsHtml}</td>` +
    `</tr>`;
  }).join("");

  $("res").innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;

  $("res").querySelectorAll("input.var-accept-chk").forEach(chk => {
    chk.addEventListener("change", () => {
      const cI = +chk.dataset.conn;
      const vI = +chk.dataset.var;
      const vars = getConnVariations(cI);
      if (vars[vI]) {
        vars[vI].accepted = chk.checked;
      }
      renderResults();
      renderAcceptedTable();
      if (VIEW && VIEW.connIdx === cI) buildViewerPanel();
    });
  });

  $("res").querySelectorAll("button.vbtn").forEach(b => {
    b.onclick = () => openViewer(+b.dataset.viewConn, +b.dataset.viewVar);
  });

  renderAcceptedTable();
}

/* =====================================================================
   Renderizado de la Pantalla Inicial (Sección 2: Variantes Aceptadas)
   ===================================================================== */
function renderAcceptedTable(){
  const acceptedList = [];

  state.results.forEach((conn, connIdx) => {
    const vars = getConnVariations(connIdx);
    vars.forEach((v, vIdx) => {
      if (v.accepted) {
        acceptedList.push({
          connIdx,
          varIdx: vIdx,
          unicode: v.data["Unicode origen"] || v.data.Unicode || (`Conexión_${connIdx + 1}`),
          label: v.label,
          data: v.data,
          check: v.check,
          status: v.status || (v.check?.cumple ? "CUMPLE" : "NO CUMPLE")
        });
      }
    });
  });

  const sec = $("acceptedSec");
  $("acceptedCount").textContent = acceptedList.length;
  $("sendAccepted").disabled = !acceptedList.length;

  if (!state.results.length) {
    sec.style.display = "none";
    return;
  }
  sec.style.display = "";

  const container = $("acceptedTbl");
  if (!acceptedList.length) {
    container.innerHTML = `<div class="empty">No has marcado ninguna variante como aceptada todavía. Haz clic en los casilleros para agregar diseños a la lista final.</div>`;
    return;
  }

  const sampleData = acceptedList[0].data;
  const cols = SCHEMA.result_columns.length ? SCHEMA.result_columns : Object.keys(sampleData).filter(k => k !== "raw" && k !== "check" && k !== "adjusted" && k !== "adjustedCheck");

  const head = `<th>Visualizar</th><th>Variante Aceptada</th>` +
    cols.map(c => `<th>${escHtml(c)}</th>`).join("") +
    `<th>Comprobación AISC</th><th>Quitar</th>`;

  const body = acceptedList.map((item) => {
    const r = item.data;
    const st = item.status;
    const stCls = st === "CUMPLE" ? "ok" : st === "NO CUMPLE" ? "bad" : "mod";

    return `<tr>` +
      `<td><button class="vbtn" data-view-conn="${item.connIdx}" data-view-var="${item.varIdx}" title="Ver en 2D">👁</button></td>` +
      `<td><b style="color:var(--tr-navy);">${escHtml(item.label)}</b></td>` +
      cols.map(c => `<td>${escHtml(r[c] ?? "")}</td>`).join("") +
      `<td class="st ${stCls}">${escHtml(st)}</td>` +
      `<td class="x"><button class="discard-btn" data-conn="${item.connIdx}" data-var="${item.varIdx}" title="Quitar de aceptadas">✕</button></td>` +
    `</tr>`;
  }).join("");

  container.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;

  container.querySelectorAll("button.discard-btn").forEach(b => {
    b.onclick = () => {
      const cI = +b.dataset.conn;
      const vI = +b.dataset.var;
      const vars = getConnVariations(cI);
      if (vars[vI]) vars[vI].accepted = false;
      renderResults();
      renderAcceptedTable();
      if (VIEW && VIEW.connIdx === cI) buildViewerPanel();
    };
  });

  container.querySelectorAll("button.vbtn").forEach(b => {
    b.onclick = () => openViewer(+b.dataset.viewConn, +b.dataset.viewVar);
  });
}

/* =====================================================================
   Exportación Excel
   ===================================================================== */
$("exportCheckExcel").onclick = () => {
  const acceptedList = [];
  state.results.forEach((conn, connIdx) => {
    const vars = getConnVariations(connIdx);
    vars.forEach((v, vIdx) => {
      if (v.accepted) acceptedList.push({ connIdx, vIdx, v });
    });
  });

  if (!acceptedList.length) { setStatus("bad", "No hay variantes aceptadas para exportar."); return; }

  const exportRows = [];
  acceptedList.forEach(({ connIdx, vIdx, v }) => {
    const chk = v.check || {};
    const rowObj = {
      "Conexión #": connIdx + 1,
      "Variación": v.label || (`Variación ${vIdx + 1}`),
      "UNICODE": v.data.Unicode || v.data.UNICODE || (connIdx + 1),
      "Estado Global": v.status || (chk.cumple ? "CUMPLE" : "NO CUMPLE"),
      "Ratio Pésimo": chk.ratio_pesimo ?? "",
      "Chequeo Crítico": chk.descripcion_ratio_pesimo || ""
    };
    Object.keys(v.data).forEach(k => {
      if (!["ratios", "complementarios", "cumple", "ratio_pesimo", "descripcion_ratio_pesimo", "raw", "adjusted", "adjustedCheck", "check"].includes(k)) {
        rowObj[k] = v.data[k];
      }
    });
    if (Array.isArray(chk.ratios)) {
      chk.ratios.forEach(ratioItem => { rowObj[`Ratio: ${ratioItem.descripcion}`] = ratioItem.ratio ?? "N/A"; });
    }
    if (Array.isArray(chk.complementarios)) {
      chk.complementarios.forEach(compItem => { rowObj[`Geometría: ${compItem.descripcion}`] = compItem.resultado; });
    }
    exportRows.push(rowObj);
  });

  const worksheet = XLSX.utils.json_to_sheet(exportRows);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Comprobaciones AISC360");
  XLSX.writeFile(workbook, `Comprobaciones_VariantesAceptadas_${new Date().toISOString().slice(0, 10)}.xlsx`);
  setStatus("ok", "Exportación de comprobaciones de variantes aceptadas a Excel completada.");
};

$("exportAcceptedExcel").onclick = () => {
  const acceptedList = [];
  state.results.forEach((conn, connIdx) => {
    const vars = getConnVariations(connIdx);
    vars.forEach((v, vIdx) => {
      if (v.accepted) acceptedList.push({ connIdx, vIdx, v });
    });
  });

  if (!acceptedList.length) { setStatus("bad", "No hay variantes aceptadas para exportar."); return; }

  const exportRows = acceptedList.map(({ connIdx, vIdx, v }) => {
    const cleanObj = { "Conexión #": connIdx + 1, "Variación": v.label || (`Variación ${vIdx + 1}`) };
    Object.keys(v.data).forEach(k => {
      if (!["raw", "adjusted", "adjustedCheck", "check"].includes(k)) cleanObj[k] = v.data[k];
    });
    return cleanObj;
  });

  const worksheet = XLSX.utils.json_to_sheet(exportRows);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Variantes Aceptadas");
  XLSX.writeFile(workbook, `Variantes_Aceptadas_${new Date().toISOString().slice(0, 10)}.xlsx`);
  setStatus("ok", "Variantes aceptadas exportadas a Excel.");
};

function setStatus(kind, text, detail){
  const s = $("status");
  s.className = kind; s.style.display = text ? "block" : "none";
  s.innerHTML = `<b>${escHtml(text)}</b>` + (detail ? `<pre></pre>` : "");
  if (detail) s.querySelector("pre").textContent = detail;
}

/* =====================================================================
   Visualizador 2D
   ===================================================================== */
const PROFILE_CACHE = {};
let VIEW = null;

const P_KEYS = ["p3","p4","p5","p6","p7","p8","p9","p10","p11","p12"];
const VIEW_FIELDS = [
  {sec:"Chapa frontal"}, 
  {k:"b_ep", label:"Bp · ancho chapa", type:"num"},
  {k:"ThicknessName_t_ep", label:"tp · espesor chapa", type:"mm"},
  {k:"Lh", label:"Lh · largo cartela", type:"num"},
  {sec:"Tornillería"},
  {k:"p2_ep", label:"g · gramil (horizontal)", type:"num"},
  {k:"dev", label:"e · borde → 1ª fila", type:"num"},
  {k:"pfo", label:"pfo · 1ª fila → ala sup. viga", type:"num"},
  {k:"pfi", label:"pfi · ala sup. → 2ª fila", type:"num"},
  {k:"pb", label:"p2 · 2ª → 3ª fila", type:"num"},
];
P_KEYS.forEach(k => VIEW_FIELDS.push({k, label:k, type:"num"}));
VIEW_FIELDS.push(
  {sec:"Rigidizadores"},
  {k:"ThicknessName_t_webstiff", label:"tws · rigid. alma pilar", type:"mm"},
  {k:"Bws", label:"Bws · ancho placa alma", type:"num"},
  {k:"Lws", label:"Lws · alto placa alma", type:"num"},
  {k:"ThicknessName_t_compstiff", label:"ts · rigid. compresión pilar", type:"mm"},
  {k:"ThicknessName_t_BeamHcompstiff", label:"tbs · rigid. alma viga", type:"mm"},
  {k:"ThicknessName_t_tenstiff", label:"tst · rigid. tracción pilar", type:"mm"},
);

const SEC_FIELDS = [
  {sec:"Sección viga (catálogo)"},
  {k:"beam_d", label:"d_viga · canto"},
  {k:"beam_bf", label:"bf_viga · ancho ala"},
  {k:"beam_tw", label:"tw_viga · alma"},
  {k:"beam_tf", label:"tf_viga · ala"},
  {sec:"Sección pilar (catálogo)"},
  {k:"col_d", label:"d_pilar · canto"},
  {k:"col_bf", label:"bf_pilar · ancho ala"},
  {k:"col_tw", label:"tw_pilar · alma"},
  {k:"col_tf", label:"tf_pilar · ala"},
];

function vNum(v){
  const s = String(v == null ? "" : v).toLowerCase().replace("mm", "").replace(",", ".").trim();
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}
function vMmText(v){ return Math.round(vNum(v)) + "mm"; }
function fmt(n){ return String(Math.round(n * 10) / 10); }

async function fetchProfiles(names){
  const need = [...new Set(names.filter(Boolean).map(n => String(n).trim()))].filter(n => !(n in PROFILE_CACHE));
  if (need.length){
    try{
      const r = await fetch("/profiles?names=" + encodeURIComponent(need.join(",")));
      if (r.ok){ const d = await r.json(); Object.assign(PROFILE_CACHE, d.profiles || {}); }
    }catch(e){}
  }
  const out = {};
  names.filter(Boolean).forEach(n => { out[n] = PROFILE_CACHE[String(n).trim()] || null; });
  return out;
}

async function openViewer(connIdx, initialVarIdx = 0){
  const vars = getConnVariations(connIdx);
  if (!vars.length) return;

  VIEW = { connIdx, activeVarIndex: initialVarIdx };
  
  const activeVar = vars[initialVarIdx] || vars[0];
  const connTitle = state.results[connIdx]?.inputRow?.Unicode || 
                    activeVar?.data?.["Unicode origen"] || 
                    activeVar?.data?.Unicode || 
                    ("Conexión " + (connIdx + 1));
                    
  $("viewerTitle").textContent = "Visualización 2D · " + connTitle;

  await loadViewerVariation(initialVarIdx);

  $("viewer").style.display = "flex";
  document.body.classList.add("modal-open");
  updateSaveButton();
}

async function loadViewerVariation(varIdx){
  if (!VIEW) return;
  VIEW.activeVarIndex = varIdx;
  const vars = getConnVariations(VIEW.connIdx);
  const activeVar = vars[varIdx] || vars[0];
  if (!activeVar) return;

  const row = activeVar.data;
  const prof = await fetchProfiles([row.BEAM, row.COLUMN]);
  const beam = prof[row.BEAM] || null, col = prof[row.COLUMN] || null;

  VIEW.row = { ...row };
  VIEW.rowBaseline = { ...row };
  VIEW.check = activeVar.check ? JSON.parse(JSON.stringify(activeVar.check)) : null;
  VIEW.beam = beam; VIEW.col = col;
  VIEW.vals = {}; VIEW.sec = {}; VIEW.warn = "";

  VIEW_FIELDS.forEach(f => { if (f.k) VIEW.vals[f.k] = (row[f.k] ?? ""); });
  VIEW.sec = {
    beam_d: beam ? beam.d_mm : "", beam_bf: beam ? beam.bf_mm : "",
    beam_tw: beam ? beam.tw_mm : "", beam_tf: beam ? beam.tf_mm : "",
    col_d: col ? col.d_mm : "", col_bf: col ? col.bf_mm : "",
    col_tw: col ? col.tw_mm : "", col_tf: col ? col.tf_mm : "",
  };

  VIEW.baselineVals = JSON.parse(JSON.stringify(VIEW.vals));

  const missed = [];
  if (!String(row.BEAM || "").trim()) missed.push("viga (columna BEAM vacía)");
  else if (!beam) missed.push("viga '" + row.BEAM + "'");
  if (!String(row.COLUMN || "").trim()) missed.push("pilar (columna COLUMN vacía)");
  else if (!col) missed.push("pilar '" + row.COLUMN + "'");

  VIEW.warn = missed.length
    ? "No encontrado en el catálogo: " + missed.join(", ") + ". Introduce las cotas de sección a mano."
    : "";

  buildViewerPanel();
  drawAll();
  checkViewerConnection();
}

window.switchViewerTab = function(varIdx){
  if (!VIEW || VIEW.activeVarIndex === varIdx) return;
  if (state.results[VIEW.connIdx]) state.results[VIEW.connIdx].activeVarIndex = varIdx;
  loadViewerVariation(varIdx);
};

function buildViewerPanel(){
  const p = $("viewerPanel");
  let html = "";
  
  const vars = getConnVariations(VIEW.connIdx);
  if (vars.length > 0) {
    html += `<div class="view-sec" style="margin-top:0; color:var(--tr-navy);">Variaciones del Diseño</div>`;
    html += `<div style="display:flex; flex-direction:column; gap:8px; margin-bottom:14px;">` +
      vars.map((v, idx) => {
        const isActive = idx === VIEW.activeVarIndex;
        const st = isActive
          ? (VIEW.check ? (VIEW.check.cumple ? "CUMPLE" : "NO CUMPLE") : v.status)
          : (v.status || (v.check?.cumple ? "CUMPLE" : "NO CUMPLE"));
        const badgeCls = st === "CUMPLE" ? "ok" : st === "NO CUMPLE" ? "bad" : "mod";
        const btnBg = isActive ? "#002B5C" : "#F2F5F9";
        const btnColor = isActive ? "#FFFFFF" : "var(--tr-navy)";
        const border = isActive ? "2px solid #002B5C" : "1px solid var(--tr-line)";
        const isAccepted = !!v.accepted;

        return `
          <div style="display:flex; align-items:center; gap:8px; background:${btnBg}; border:${border}; border-radius:5px; padding:6px 10px;">
            <input type="checkbox" id="modal_accept_${idx}" class="modal-var-chk" data-var="${idx}" ${isAccepted ? "checked" : ""} style="width:16px; height:16px; cursor:pointer;" title="Aceptar variante">
            <button type="button" onclick="switchViewerTab(${idx})" style="
              flex:1; border:none; background:transparent; color:${btnColor}; cursor:pointer; font-weight:600; font-size:12.5px; text-align:left; padding:2px 0;
            ">
              <span>${escHtml(v.label)}</span>
            </button>
            <span class="badge ${badgeCls}">${escHtml(st)}</span>
          </div>
        `;
      }).join("") + `</div>`;
  }

  if (VIEW.warn) html += `<div class="view-warn">${escHtml(VIEW.warn)}</div>`;

  html += `<div id="viewerCheckSection">${checkSectionHtml()}</div>`;

  html += VIEW_FIELDS.map(f => {
    if (f.sec) return `<div class="view-sec">${escHtml(f.sec)}</div>`;
    return viewRow(f.label, "data-vkey", f.k, VIEW.vals[f.k], true);
  }).join("");
  html += SEC_FIELDS.map(f => {
    if (f.sec) return `<div class="view-sec">${escHtml(f.sec)}</div>`;
    return viewRow(f.label, "data-skey", f.k, VIEW.sec[f.k], true, false);
  }).join("");
  html += `<div class="view-sec">Derivados</div>` +
          `<div class="view-row ro"><label>p1 = pfo + tf_viga + pfi</label><div class="mm-wrap"><input id="vP1" readonly><span class="mm-suf">mm</span></div></div>` +
          `<div class="view-row ro"><label>Lp = 2·e + Σp (alto chapa)</label><div class="mm-wrap"><input id="vLp" readonly><span class="mm-suf">mm</span></div></div>`;

  p.innerHTML = html;

  p.querySelectorAll("input.modal-var-chk").forEach(chk => {
    chk.addEventListener("change", (e) => {
      e.stopPropagation();
      const vI = +chk.dataset.var;
      const vars = getConnVariations(VIEW.connIdx);
      if (vars[vI]) {
        vars[vI].accepted = chk.checked;
        renderResults();
        renderAcceptedTable();
      }
    });
  });

  p.querySelectorAll("[data-vkey]").forEach(inp => {
    inp.addEventListener("input", () => onField(inp, VIEW.vals, inp.dataset.vkey));
    inp.addEventListener("change", () => {
      onFieldBlur(inp, VIEW.vals, inp.dataset.vkey);
      checkViewerConnection();
    });
  });
}

function checkSectionHtml(){
  const vars = getConnVariations(VIEW.connIdx);
  const activeVar = vars[VIEW.activeVarIndex] || vars[0];
  const checkData = VIEW.check || (VIEW.checking ? null : activeVar?.check);
  const checking = !!VIEW.checking;

  if (checking) {
    return `
      <div class="view-sec" style="margin-top:0; color:var(--tr-navy);">Comprobación AISC 360-10</div>
      <div style="margin-bottom:10px;">
        <span class="badge mod">COMPROBANDO...</span>
      </div>
    `;
  }

  if (checkData){
    const st = checkData.cumple ? "CUMPLE" : "NO CUMPLE";
    const badgeCls = checkData.cumple ? "ok" : "bad";

    let out = `
      <div class="view-sec" style="margin-top:0; color:var(--tr-navy);">Comprobación AISC 360-10</div>
      <div style="margin-bottom:10px;">
        <span class="badge ${badgeCls}">${escHtml(st)}</span>
      </div>
    `;

    out += `
      <div style="font-size:12.5px; margin-bottom:8px; color:var(--tr-navy);">
        <div><b>Ratio pésimo:</b> <span style="color:var(--tr-navy); font-weight:bold;">${checkData.ratio_pesimo ?? 'N/A'}</span></div>
        <div style="margin-top:2px;"><b>Chequeo crítico:</b> <span style="color:var(--tr-navy);">${escHtml(checkData.descripcion_ratio_pesimo || 'N/A')}</span></div>
      </div>
    `;

    if (Array.isArray(checkData.complementarios) && checkData.complementarios.length > 0) {
      out += `
        <details style="margin-bottom:10px; background:#F7FAFD; padding:6px 8px; border:1px solid #D5DDE8; border-radius:4px; color:var(--tr-navy);">
          <summary style="font-weight:600; font-size:12px; cursor:pointer; color:var(--tr-navy);">Comprobaciones Geométricas (${checkData.complementarios.length})</summary>
          <ul style="margin:6px 0 0 0; padding-left:16px; font-size:11.5px; line-height:1.45; color:var(--tr-navy);">
            ${checkData.complementarios.map(c => `<li><b style="color:var(--tr-navy);">${escHtml(c.descripcion)}:</b> <span style="color:var(--tr-navy);">${escHtml(c.resultado)}</span></li>`).join("")}
          </ul>
        </details>
      `;
    }

    if (Array.isArray(checkData.ratios) && checkData.ratios.length > 0) {
      out += `
        <details style="margin-bottom:10px; background:#F7FAFD; padding:6px 8px; border:1px solid #D5DDE8; border-radius:4px; color:var(--tr-navy);">
          <summary style="font-weight:600; font-size:12px; cursor:pointer; color:var(--tr-navy);">Ratios de Resistencia (${checkData.ratios.length})</summary>
          <ul style="margin:6px 0 0 0; padding-left:16px; font-size:11.5px; line-height:1.45; color:var(--tr-navy);">
            ${checkData.ratios.map(f => {
              const val = f.ratio !== null && f.ratio !== undefined ? Number(f.ratio).toFixed(3) : 'N/A';
              const isBad = f.ratio > 1.0;
              return `<li><b style="color:var(--tr-navy);">${escHtml(f.descripcion)}:</b> <span style="${isBad ? 'color:var(--tr-red);font-weight:bold;' : 'color:var(--tr-navy);'}">${val}</span></li>`;
            }).join("")}
          </ul>
        </details>
      `;
    }
    return out;
  }

  return `
    <div class="view-sec" style="margin-top:0; color:var(--tr-navy);">Comprobación AISC 360-10</div>
    <div style="margin-bottom:12px; background:#EAF3FB; padding:10px; border-left:3px solid var(--tr-blue); border-radius:3px; font-size:12px; color:var(--tr-navy);">
      Esta variación no se ha comprobado aún.
    </div>
  `;
}

function renderCheckSection(){
  const el = $("viewerCheckSection");
  if (el) el.innerHTML = checkSectionHtml();
}

async function checkViewerConnection(){
  if (!VIEW) return;

  VIEW_FIELDS.forEach(f => {
    if (!f.k) return;
    const rawVal = VIEW.vals[f.k];
    if (f.type === "mm"){ VIEW.row[f.k] = vMmText(rawVal); }
    else {
      const s = String(rawVal).trim();
      VIEW.row[f.k] = s === "" ? "" : (isNaN(Number(s)) ? s : Number(s));
    }
  });

  const token = (VIEW.checkToken || 0) + 1;
  VIEW.checkToken = token;
  VIEW.checking = true;
  renderCheckSection();

  try {
    const r = await fetch("/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: [VIEW.row] }),
    });
    const data = await r.json().catch(() => ({}));
    if (!VIEW || VIEW.checkToken !== token) return;
    if (r.ok && Array.isArray(data.rows) && data.rows.length > 0) {
      VIEW.check = data.rows[0];
    }
  } catch (e) {
    if (!VIEW || VIEW.checkToken !== token) return;
  } finally {
    if (VIEW && VIEW.checkToken === token) {
      VIEW.checking = false;
      renderCheckSection();
      drawAll();
      updateSaveButton();
    }
  }
}

function viewRow(label, bindAttr, key, value, inMm, editable=true){
  const shown = inMm ? mmInput(value) : String(value == null ? "" : value);
  const input = `<input ${bindAttr}="${escAttr(key)}" value="${escAttr(shown)}" inputmode="decimal" ${editable? "":"readonly"}>`;
  return `<div class="view-row ${editable? "":"ro"}"><label>${escHtml(label)}</label>` +
         `<div class="mm-wrap">${input}<span class="mm-suf">mm</span></div></div>`;
}

function mmInput(v){
  const s = String(v == null ? "" : v).trim();
  if (s === "") return "";
  return String(Math.round(vNum(s)));
}

function sanitizeNum(v){
  let s = String(v == null ? "" : v).replace(/[^\d.,]/g, "").replace(/,/g, ".");
  const i = s.indexOf(".");
  if (i >= 0) s = s.slice(0, i + 1) + s.slice(i + 1).replace(/\./g, "");
  return s;
}

function onField(inp, store, key){
  VIEW.checking = true;
  let s = sanitizeNum(inp.value);
  if (s === ""){ store[key] = ""; inp.value = ""; updateSaveButton(); drawAll(); return; }
  store[key] = s;
  if (inp.value !== s) inp.value = s;
  updateSaveButton();
  drawAll();
}

function onFieldBlur(inp, store, key){
  const s = sanitizeNum(inp.value);
  let n = (s === "" || isNaN(parseFloat(s))) ? 0 : parseFloat(s);
  if (n < 0) n = 0;
  store[key] = String(n);
  if (inp.value !== String(n)) inp.value = String(n);
  updateSaveButton();
  drawAll();
}

function updateSaveButton(){
  if (!VIEW) return;
  let dirty = false;
  for (const f of VIEW_FIELDS){
    if (!f.k) continue;
    if (vNum(VIEW.vals[f.k]) !== vNum(VIEW.baselineVals[f.k])){ dirty = true; break; }
  }
  const btn = $("viewerSave");
  if (btn) btn.disabled = !dirty;
}

/* Restaura la predicción AJUSTADA original que devolvió el modelo */
function loadAdjustedPrediction(){
  if (!VIEW) return;
  const vars = getConnVariations(VIEW.connIdx);
  const activeVar = vars[VIEW.activeVarIndex];
  const adjusted = activeVar?.adjusted || activeVar?.data;
  if (!adjusted){ alert("No hay predicción ajustada disponible."); return; }
  
  VIEW.vals = {};
  VIEW_FIELDS.forEach(f => { if (f.k) VIEW.vals[f.k] = (adjusted[f.k] ?? ""); });
  VIEW.row = { ...VIEW.rowBaseline, ...adjusted };
  VIEW.check = activeVar.adjustedCheck ? JSON.parse(JSON.stringify(activeVar.adjustedCheck)) : null;
  
  buildViewerPanel();
  drawAll();
  updateSaveButton();
  checkViewerConnection();
}

/* Restaura la predicción BRUTA (SIN AJUSTE) que devolvió el modelo */
function loadRawPrediction(){
  if (!VIEW) return;
  const vars = getConnVariations(VIEW.connIdx);
  const activeVar = vars[VIEW.activeVarIndex];
  const raw = activeVar?.raw;
  if (!raw){ alert("No hay predicción sin ajuste disponible para esta variación."); return; }
  
  VIEW.vals = {};
  VIEW_FIELDS.forEach(f => { if (f.k) VIEW.vals[f.k] = (raw[f.k] ?? ""); });
  VIEW.row = { ...VIEW.rowBaseline, ...raw };
  VIEW.check = null;
  
  buildViewerPanel();
  drawAll();
  updateSaveButton();
  checkViewerConnection();
}

function saveViewer(){
  if (!VIEW) return;
  const vars = getConnVariations(VIEW.connIdx);
  const activeVar = vars[VIEW.activeVarIndex];
  if (!activeVar) return;

  VIEW_FIELDS.forEach(f => {
    if (!f.k) return;
    const v = VIEW.vals[f.k];
    if (f.type === "mm"){ activeVar.data[f.k] = vMmText(v); }
    else { const s = String(v).trim(); activeVar.data[f.k] = s === "" ? "" : Number(s); }
  });

  if (VIEW.check) {
    activeVar.check = JSON.parse(JSON.stringify(VIEW.check));
    activeVar.status = VIEW.check.cumple ? "CUMPLE" : "NO CUMPLE";
  } else {
    activeVar.status = "MODIFICADO";
  }

  closeViewer();
  renderResults();
  renderAcceptedTable();
}

function closeViewer(){
  $("viewer").style.display = "none";
  document.body.classList.remove("modal-open");
  VIEW = null;
}

$("viewerBack").onclick = closeViewer;
$("viewerReset").onclick = loadAdjustedPrediction;
$("viewerRawReset").onclick = loadRawPrediction;
$("viewerSave").onclick = saveViewer;

/* ---------- Dibujo SVG ---------- */
function svgRect(x,y,w,h,fill,stroke,sw){ return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill||"none"}" stroke="${stroke||"black"}" stroke-width="${sw||1}"/>`; }
function svgCircle(cx,cy,r,fill){ return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" stroke="black" stroke-width="1"/>`; }
function svgLine(x1,y1,x2,y2,stroke,dash,sw){ return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke||"black"}" stroke-width="${sw||1}" stroke-dasharray="${dash||""}"/>`; }
function svgPoly(points,fill){ return `<polygon points="${points}" fill="${fill}" stroke="black" stroke-width="1"/>`; }
function svgText(x,y,t,anchor,color,size){ return `<text x="${x}" y="${y}" font-size="${size||11}" font-family="Segoe UI,Arial" fill="${color||"#1B2733"}" text-anchor="${anchor||"start"}">${escHtml(t)}</text>`; }
function dimV(x,y1,y2,label,side){
  side = side || "left";
  const tx = side === "left" ? x - 4 : x + 4, anc = side === "left" ? "end" : "start";
  return svgLine(x,y1,x,y2,"#D52B1E") + svgLine(x-3,y1,x+3,y1,"#D52B1E") + svgLine(x-3,y2,x+3,y2,"#D52B1E") + svgText(tx,(y1+y2)/2+4,label,anc,"#D52B1E");
}
function dimH(y,x1,x2,label){
  return svgLine(x1,y,x2,y,"#D52B1E") + svgLine(x1,y-3,x1,y+3,"#D52B1E") + svgLine(x2,y-3,x2,y+3,"#D52B1E") + svgText((x1+x2)/2,y-5,label,"middle","#D52B1E");
}

function viewModel(){
  const V = VIEW.vals, S = VIEW.sec;
  const tf = vNum(S.beam_tf), bf = vNum(S.beam_bf), tw = vNum(S.beam_tw), bd = vNum(S.beam_d);
  const ctf = vNum(S.col_tf), cbf = vNum(S.col_bf), ctw = vNum(S.col_tw), cd = vNum(S.col_d);
  const e = vNum(V.dev), g = vNum(V.p2_ep), Bp = vNum(V.b_ep), tp = vNum(V.ThicknessName_t_ep), Lh = vNum(V.Lh);
  const pfo = vNum(V.pfo), pfi = vNum(V.pfi), pb = vNum(V.pb);
  const p1 = pfo + tf + pfi;
  const steps = [p1, pb, ...P_KEYS.map(k => vNum(V[k]))].filter(x => x > 0);
  const sumP = steps.reduce((a,b) => a+b, 0);
  const Lp = 2*e + sumP;
  const rows = [e]; let y = e;
  steps.forEach(s => { y += s; rows.push(y); });
  const beamTop = e + pfo, beamBot = beamTop + bd;
  const boltDia = parseInt(String(VIEW.row.BoltName_ep || "").replace(/\D/g,""), 10) || 24;
  return {
    tf,bf,tw,bd,ctf,cbf,ctw,cd,e,g,Bp,tp,Lh,pfo,pfi,pb,p1,steps,sumP,Lp,rows,beamTop,beamBot,boltDia,
    Hhaunch: Math.max(0, Lp - beamBot),
    tws: vNum(V.ThicknessName_t_webstiff), ts: vNum(V.ThicknessName_t_compstiff),
    tbs: vNum(V.ThicknessName_t_BeamHcompstiff), tst: vNum(V.ThicknessName_t_tenstiff),
    bws: vNum(V.Bws), lws: vNum(V.Lws),
  };
}

function drawAll(){
  if (!VIEW) return;
  const m = viewModel();
  if ($("vP1")) $("vP1").value = fmt(m.p1);
  if ($("vLp")) $("vLp").value = fmt(m.Lp);
  drawFront(m); drawSide(m); drawTop(m);
}

function drawFront(m){
  const W = 520, H = 620, cx = 230, top = 40;
  const maxH = Math.max(m.Lp, m.beamBot, 1);
  const scale = Math.min(0.9, (H - 90)/maxH, (W - 200)/Math.max(m.Bp, 1));
  const Y = v => top + v*scale, X = v => cx + v*scale;
  let s = "";
  s += svgRect(cx - (m.Bp/2)*scale, top, m.Bp*scale, m.Lp*scale, "#cfd8e3");
  s += svgRect(cx - (m.bf/2)*scale, Y(m.beamTop), m.bf*scale, m.tf*scale, "none", "#33475b", 1.5);
  s += svgRect(cx - (m.tw/2)*scale, Y(m.beamTop + m.tf), m.tw*scale, Math.max(0,(m.bd - 2*m.tf))*scale, "none", "#33475b", 1.5);
  s += svgRect(cx - (m.bf/2)*scale, Y(m.beamBot - m.tf), m.bf*scale, m.tf*scale, "none", "#33475b", 1.5);
  if (m.Lh > 0){
    const hz = m.Lh;
    s += svgRect(cx - (m.tw/2)*scale, Y(m.beamBot), m.tw*scale, Math.max(0, hz - m.tf)*scale, "none", "#1e88e5", 1.5);
    s += svgRect(cx - (m.bf/2)*scale, Y(m.beamBot + hz - m.tf), m.bf*scale, m.tf*scale, "none", "#1e88e5", 1.5);
  }
  const r = Math.max(3, (m.boltDia/2)*scale*0.8);
  m.rows.forEach(yy => {
    s += svgCircle(X(-m.g/2), Y(yy), r, "#ff4500");
    s += svgCircle(X(m.g/2), Y(yy), r, "#ff4500");
  });
  const xL = cx - (m.Bp/2)*scale - 18;
  const xR = cx + (m.Bp/2)*scale + 22;
  s += dimV(xL, Y(0), Y(m.rows[0]), "e=" + fmt(m.e));
  s += dimV(xL, Y(m.rows[0]), Y(m.beamTop), "pfo=" + fmt(m.pfo));
  if (m.rows[1] != null && m.rows[1] > m.beamTop + m.tf)
    s += dimV(xL, Y(m.beamTop + m.tf), Y(m.rows[1]), "pfi=" + fmt(m.pfi));
  const pit = ["p2=" + fmt(m.pb), ...P_KEYS.map(k => k + "=" + fmt(vNum(VIEW.vals[k])))];
  for (let i = 1; i < m.rows.length - 1; i++)
    s += dimV(xL, Y(m.rows[i]), Y(m.rows[i+1]), pit[i-1] || "");
  s += dimV(xR, Y(m.beamTop), Y(m.beamBot), "d_viga=" + fmt(m.bd), "right");
  if (m.Lh > 0)
    s += dimV(xR, Y(m.beamBot), Y(m.beamBot + m.Lh), "Lh=" + fmt(m.Lh), "right");
  s += dimV(xR + 72, Y(0), Y(m.Lp), "Lp=" + fmt(m.Lp), "right");
  s += dimH(top - 14, X(-m.Bp/2), X(m.Bp/2), "Bp=" + fmt(m.Bp));
  s += dimH(Y(m.Lp) + 18, X(-m.g/2), X(m.g/2), "g=" + fmt(m.g));
  $("vFront").innerHTML = s;
}

function drawSide(m){
  const W = 580, H = 620, top = 40;
  const t = Math.tan(Math.PI / 3);
  const hxMM = m.Lh * t;
  let scale = Math.min(0.85, (H - 110)/Math.max(m.Lp, 1));
  const denom = m.cd + m.tp + Math.max(hxMM, 0);
  if (denom > 0) scale = Math.min(scale, (W - 160)/denom);
  scale = Math.max(scale, 0.12);
  const cRight = m.cd*scale + 90;
  const Y = v => top + v*scale;
  let s = "";
  const colTop = top - 20, colBot = top + m.Lp*scale + 20;
  s += svgRect(cRight - m.cd*scale, colTop, m.cd*scale, colBot - colTop, "#e6e6e6", "gray");
  s += svgRect(cRight - m.ctf*scale, colTop, m.ctf*scale, colBot - colTop, "#b0c4de");
  s += svgRect(cRight - m.cd*scale, colTop, m.ctf*scale, colBot - colTop, "#b0c4de");
  if (m.tws > 0 && m.bws > 0 && m.lws > 0){
    const wx = cRight - (m.cd/2)*scale - (m.bws/2)*scale;
    const wy = Y(m.beamTop + m.bd/2) - (m.lws/2)*scale;
    s += svgRect(wx, wy, m.bws*scale, m.lws*scale, "#4169e1", "#1e3a8a", 1.2);
    const bwsY = Math.min(wy, Y(m.beamTop)) - 18;
    s += dimH(bwsY, wx, wx + m.bws*scale, "Bws=" + fmt(m.bws));
    s += dimV(wx - 8, wy, wy + m.lws*scale, "Lws=" + fmt(m.lws), "left");
  }
  s += svgRect(cRight, top, m.tp*scale, m.Lp*scale, "#708090");
  const vigaX = cRight + m.tp*scale;
  const beamPx = W - vigaX;
  s += svgRect(vigaX, Y(m.beamTop), beamPx, m.tf*scale, "#b0c4de");
  s += svgRect(vigaX, Y(m.beamTop + m.tf), beamPx, Math.max(0,(m.bd - 2*m.tf))*scale, "#b0c4de");
  s += svgRect(vigaX, Y(m.beamBot - m.tf), beamPx, m.tf*scale, "#b0c4de");
  if (m.Lh > 0){
    const hx = vigaX + hxMM*scale;
    s += svgPoly(`${vigaX},${Y(m.beamBot)} ${hx},${Y(m.beamBot)} ${vigaX},${Y(m.beamBot + m.Lh)}`, "#a2b5cd");
  }
  if (m.tst > 0) s += svgRect(cRight - m.cd*scale + m.ctf*scale, Y(m.beamTop), Math.max(0,(m.cd - 2*m.ctf))*scale, m.tst*scale, "#00008b");
  if (m.ts > 0) s += svgRect(cRight - m.cd*scale + m.ctf*scale, Y(m.beamBot - m.ts), Math.max(0,(m.cd - 2*m.ctf))*scale, m.ts*scale, "#00008b");
  if (m.tbs > 0) s += svgRect(vigaX + beamPx - 30, Y(m.beamTop + m.tf), m.tbs*scale, Math.max(0,(m.bd - 2*m.tf))*scale, "#00008b");
  m.rows.forEach(yy => { s += svgLine(cRight - m.ctf*scale - 10, Y(yy), vigaX, Y(yy), "#ff4500", "4,2"); });
  const xL = cRight - m.cd*scale - 18;
  s += dimV(xL, Y(0), Y(m.rows[0]), "e=" + fmt(m.e));
  s += dimV(xL, Y(m.rows[0]), Y(m.beamTop), "pfo=" + fmt(m.pfo));
  if (m.Lh > 0)
    s += dimV(vigaX + hxMM*scale, Y(m.beamBot), Y(m.beamBot + m.Lh), "Lh=" + fmt(m.Lh), "right");
  s += dimH(top - 14, cRight, vigaX, "tp=" + fmt(m.tp));
  $("vSide").innerHTML = s;
}

function drawTop(m){
  const W = 500, cy = 180;
  const x0 = 50, beamPx = 190;
  const avail = W - x0 - beamPx - 70;
  const scale = Math.min(0.8, avail / Math.max(m.cd + m.tp, 1));
  const cx = x0 + m.cd*scale;
  const yTop = v => cy - v*scale;
  const steel = "#b0c4de", plate = "#708090", stiff = "#00008b", webStiff = "#4169e1";
  let s = "";
  s += svgRect(cx - m.cd*scale, cy - (m.cbf/2)*scale, m.ctf*scale, m.cbf*scale, steel, "#33475b", 1);
  s += svgRect(cx - m.ctf*scale, cy - (m.cbf/2)*scale, m.ctf*scale, m.cbf*scale, steel);
  s += svgRect(cx - m.cd*scale + m.ctf*scale, yTop(m.ctw/2), Math.max(0,(m.cd - 2*m.ctf))*scale, m.ctw*scale, steel);
  if (m.tws > 0) s += svgRect(cx - m.cd*scale + m.ctf*scale, yTop(m.ctw/2) - m.tws*scale, Math.max(0,(m.cd - 2*m.ctf))*scale, m.tws*scale, webStiff);
  s += svgRect(cx, cy - (m.Bp/2)*scale, m.tp*scale, m.Bp*scale, plate);
  s += svgRect(cx + m.tp*scale, cy - (m.bf/2)*scale, beamPx, m.bf*scale, steel);
  s += svgLine(cx + m.tp*scale, cy, cx + m.tp*scale + beamPx, cy, "black", "5,5");
  if (m.tbs > 0) s += svgRect(cx + m.tp*scale + beamPx - 30, cy - (m.bf/2)*scale, m.tbs*scale, m.bf*scale, stiff);
  s += dimH(cy + m.Bp*scale/2 + 16, cx, cx + m.tp*scale, "tp=" + fmt(m.tp));
  if (m.tbs > 0){
    const tx = cx + m.tp*scale + beamPx - 30 + m.tbs*scale;
    s += svgLine(tx, cy - (m.bf/2)*scale, tx + 18, cy - (m.bf/2)*scale - 12, "#D52B1E");
    s += svgText(tx + 20, cy - (m.bf/2)*scale - 14, "tbs=" + fmt(m.tbs), "start", "#D52B1E");
  }
  if (m.tws > 0){
    const wx = cx - m.cd*scale + (m.cd - 2*m.ctf)*scale*0.5;
    const wy = yTop(m.ctw/2) - m.tws*scale;
    s += svgLine(wx, wy, wx, wy - 18, "#D52B1E");
    s += svgText(wx + 4, wy - 20, "tws=" + fmt(m.tws), "start", "#D52B1E");
  }
  $("vTop").innerHTML = s;
}

/* =====================================================================
   Procesador de respuestas de POST /scenarios
   ===================================================================== */
function parseScenariosResponse(data, inputRow) {
  function buildCheck(r, fallback) {
    if (fallback) return fallback;
    const cumpleVal = r.cumple !== undefined ? r.cumple : (r.ratio_pesimo != null ? Number(r.ratio_pesimo) <= 1.0 : true);
    return {
      cumple: Boolean(cumpleVal),
      ratio_pesimo: r.ratio_pesimo ?? null,
      descripcion_ratio_pesimo: r.descripcion_ratio_pesimo || r.chequeo_critico || "",
      ratios: Array.isArray(r.ratios) ? r.ratios : [],
      complementarios: Array.isArray(r.complementarios) ? r.complementarios : []
    };
  }

  function getLabel(r, defaultIdx) {
    const raw = r.Escenario || r.escenario || r.descripcion || r.nombre || r.tipo || r.variacion || r.label;
    if (raw) return String(raw).trim();
    const defaults = ["E1 - Mayor carga sin cantonera", "E2 - Primer diseño con cantonera", "E3 - Mayor carga con cantonera"];
    return defaults[defaultIdx] || `Variación ${defaultIdx + 1}`;
  }

  function getTipoCode(label, idx) {
    if (!label) return `E${idx + 1}`;
    if (label.includes(" - ")) return label.split(" - ")[0].trim();
    if (label.includes(":")) return label.split(":")[0].trim();
    return label.length <= 6 ? label : `E${idx + 1}`;
  }

  if (Array.isArray(data.rows) && data.rows.length > 0) {
    const hasMultipleConns = data.rows.some(r => r["Unicode origen"] || r.Unicode_origen);
    
    if (hasMultipleConns) {
      const groupedMap = new Map();
      data.rows.forEach((r, rowIdx) => {
        let key = r["Unicode origen"] || r.Unicode_origen || r.UNICODE_origen;
        if (!key && r.Unicode) key = r.Unicode.includes("_E") ? r.Unicode.split("_E")[0] : r.Unicode;
        if (!key) key = "Conexión_1";
        if (!groupedMap.has(key)) groupedMap.set(key, []);
        groupedMap.get(key).push({ row: r, rawIdx: rowIdx });
      });

      const connections = [];
      groupedMap.forEach((items, key) => {
        const vars = items.map((item, idx) => {
          const r = item.row;
          const fallbackCheck = (Array.isArray(data.checks) && data.checks[item.rawIdx]) ? data.checks[item.rawIdx] : null;
          const fallbackRaw = (Array.isArray(data.rows_raw) && data.rows_raw[item.rawIdx]) ? data.rows_raw[item.rawIdx] : { ...r };
          const lbl = getLabel(r, idx);
          const chk = buildCheck(r, fallbackCheck);
          return {
            label: lbl,
            tipo: getTipoCode(lbl, idx),
            data: { ...r },
            adjusted: { ...r },
            raw: { ...fallbackRaw },
            check: chk,
            adjustedCheck: JSON.parse(JSON.stringify(chk)),
            status: chk.cumple ? "CUMPLE" : "NO CUMPLE",
            accepted: false
          };
        });
        connections.push({ inputRow: inputRow || {}, activeVarIndex: 0, variations: vars, marked: false });
      });
      return connections;
    }

    const vars = data.rows.map((v, idx) => {
      const lbl = getLabel(v, idx);
      const chk = buildCheck(v, data.checks ? data.checks[idx] : null);
      const raw = data.rows_raw ? data.rows_raw[idx] : { ...v };
      return {
        label: lbl,
        tipo: getTipoCode(lbl, idx),
        data: { ...v },
        adjusted: { ...v },
        raw: { ...raw },
        check: chk,
        adjustedCheck: JSON.parse(JSON.stringify(chk)),
        status: chk.cumple ? "CUMPLE" : "NO CUMPLE",
        accepted: false
      };
    });

    return [{
      inputRow: inputRow || {},
      activeVarIndex: 0,
      variations: vars,
      marked: false
    }];
  }

  return [];
}

/* =====================================================================
   Acciones principales (Llamadas a POST /scenarios)
   ===================================================================== */
$("add").onclick = () => {
  const row = readForm(); if (!row) return;
  state.rows.push(row); renderTable(); renderForm();
  const first = SCHEMA.inputs[0];
  if (first) $("in_" + first.key).focus();
};
$("reset").onclick = renderForm;
$("clear").onclick = () => {
  state.rows = []; state.results = []; _checkTokens = {};
  renderTable(); renderResults(); setStatus("", "");
};

$("send").onclick = async () => {
  const btn = $("send");
  btn.disabled = true; 
  setStatus("", "Pre-diseñando " + state.rows.length + " combinaciones (calculando 3 variaciones por conexión)…");

  try {
    const model = $("model").value;

    const promises = state.rows.map(row => 
      fetch("/scenarios", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: model,
          row: row,
          incremento: 0.05,
          max_pasos: 40
        })
      }).then(async r => {
        const json = await r.json().catch(() => ({}));
        return { ok: r.ok, status: r.status, data: json, inputRow: row };
      }).catch(err => ({ ok: false, error: err.message, inputRow: row }))
    );

    const responses = await Promise.all(promises);
    const parsedConns = [];
    let errorsCount = 0;

    responses.forEach(res => {
      if (res.ok && res.data) {
        const conns = parseScenariosResponse(res.data, res.inputRow);
        if (conns.length > 0) {
          parsedConns.push(...conns);
        }
      } else {
        errorsCount++;
      }
    });

    state.results = parsedConns;
    _checkTokens = {};
    renderResults();

    const totalVars = state.results.reduce((acc, c) => acc + getConnVariations(state.results.indexOf(c)).length, 0);
    
    if (errorsCount > 0) {
      setStatus("bad", `Finalizado con ${errorsCount} errores.`, `${parsedConns.length} conexiones procesadas correctamente (${totalVars} variaciones).`);
    } else {
      setStatus("ok", `Predicción completada: ${parsedConns.length} conexiones (${totalVars} variaciones obtenidas). Pulsa 👁 para ver en 2D.`);
    }

  } catch (e){
    setStatus("bad", "Error de conexión", e.message);
  }
  btn.disabled = !state.rows.length;
};

/* =====================================================================
   Envío de Variantes Aceptadas al Dataset de Reentreno
   ===================================================================== */
$("sendAccepted").onclick = async () => {
  const rowsToSend = [];
  state.results.forEach((conn, connIdx) => {
    const vars = getConnVariations(connIdx);
    vars.forEach((v) => {
      if (v.accepted) rowsToSend.push(v.data);
    });
  });

  if (!rowsToSend.length){ setStatus("bad", "No hay variantes aceptadas seleccionadas."); return; }
  if (!confirm("¿Enviar " + rowsToSend.length + " variantes aceptadas al dataset de reentreno?")) return;

  const btn = $("sendAccepted"); btn.disabled = true;
  setStatus("", "Enviando " + rowsToSend.length + " variantes aceptadas…");
  try {
    const r = await fetch("/dataset/append", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: rowsToSend }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok){ setStatus("bad", `Error (${r.status})`, JSON.stringify(data)); }
    else {
      setStatus("ok", `Guardadas: ${data.added} nuevas, ${data.updated} actualizadas. Pendientes reentreno: ${data.retrain?.pending ?? 0}/${data.retrain?.threshold ?? 0}` + (data.retrain_started ? " · reentreno iniciado" : ""), data.rejected?.length ? "Rechazadas:\n" + data.rejected.join("\n") : "");
    }
  } catch (e){ setStatus("bad", "Error de conexión", e.message); }
  btn.disabled = false;
};

/* =====================================================================
   Inicialización
   ===================================================================== */
async function loadModels(){
  try{
    const r = await fetch("/models");
    const o = await r.json();
    const sel = $("model");
    const models = o.available_models || [];
    sel.innerHTML = models.map(m => `<option value="${escAttr(m)}">${escHtml(m)}</option>`).join("");
    if (o.default_model && models.includes(o.default_model)) sel.value = o.default_model;
  } catch(e){}
}

async function loadSchema(){
  const model = $("model").value;
  if (!model) return;
  try{
    const r = await fetch("/schema?model=" + encodeURIComponent(model));
    if (!r.ok) throw new Error("HTTP " + r.status);
    SCHEMA = await r.json();
    renderForm(); renderTable();
  } catch (e){ setStatus("bad", "Error cargando esquema", e.message); }
}

$("model").onchange = () => {
  state.rows = []; state.results = []; _checkTokens = {};
  renderTable(); renderResults(); loadSchema();
};

loadModels().then(loadSchema);