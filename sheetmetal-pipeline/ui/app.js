// Sheet Metal Job Builder -- client-side validation mirroring
// scripts/bracket_model.py exactly. See that file for where these
// constants and formulas come from (Stage 3/5 of the pipeline README).

const MIN_BEND_RADIUS_TO_THICKNESS_RATIO = 1.0;
const MIN_FLANGE_LENGTH_FACTOR = 4.0;

const COLUMN_ORDER = [
  "JobID", "Material", "PlateLength", "PlateWidth", "Thickness", "FlangeLength",
  "BendAngle", "BendRadius", "HoleDia", "HoleX", "HoleY",
];

let kfactorTable = null;
let batch = []; // list of {values, kFactor, extrapolated, problems}

async function loadKFactorTable() {
  const res = await fetch("../config/kfactor_table.json");
  if (!res.ok) throw new Error(`Could not load kfactor_table.json (${res.status})`);
  return res.json();
}

function lookupKFactor(table, material, thickness) {
  const materials = table.materials;
  if (!(material in materials)) {
    const known = Object.keys(materials).sort().join(", ");
    throw new Error(`unknown material '${material}' (known materials: ${known})`);
  }
  const bands = materials[material];
  for (const band of bands) {
    if (thickness <= band.thickness_max) return { kFactor: band.k_factor, extrapolated: false };
  }
  return { kFactor: bands[bands.length - 1].k_factor, extrapolated: true };
}

function expectedFlatLength(plateLength, thickness, flangeLength, bendAngle, bendRadius, kFactor) {
  const t = kFactor * thickness;
  const ba = 2 * Math.PI * (bendRadius + t) * (bendAngle / 360.0);
  return plateLength + 2 * (flangeLength + ba);
}

// Mirrors bracket_model.validate_params. Returns a list of problem strings.
function validateParams(p) {
  const problems = [];
  if (p.thickness <= 0) problems.push(`thickness must be > 0 (got ${p.thickness})`);
  if (p.plateLength <= 0 || p.plateWidth <= 0)
    problems.push(`plate_length and plate_width must be > 0 (got ${p.plateLength}, ${p.plateWidth})`);
  if (p.bendRadius < 0) problems.push(`bend_radius must be >= 0 (got ${p.bendRadius})`);
  if (p.flangeLength <= 0) problems.push(`flange_length must be > 0 (got ${p.flangeLength})`);
  if (!(p.bendAngle > 0 && p.bendAngle <= 180))
    problems.push(`bend_angle must be in (0, 180] degrees (got ${p.bendAngle})`);

  if (p.thickness > 0 && p.bendRadius < MIN_BEND_RADIUS_TO_THICKNESS_RATIO * p.thickness) {
    problems.push(
      `bend_radius ${p.bendRadius}mm is below ${MIN_BEND_RADIUS_TO_THICKNESS_RATIO}x thickness ` +
      `(${p.thickness}mm) -- material will likely crack on a real press brake`
    );
  }
  const minFlange = MIN_FLANGE_LENGTH_FACTOR * p.thickness + p.bendRadius;
  if (p.flangeLength > 0 && p.flangeLength < minFlange) {
    problems.push(
      `flange_length ${p.flangeLength}mm is below the minimum ${minFlange.toFixed(2)}mm ` +
      `(${MIN_FLANGE_LENGTH_FACTOR}x thickness + bend_radius) -- too short for tooling clearance`
    );
  }
  return problems;
}

function readForm() {
  return {
    jobId: document.getElementById("jobId").value.trim(),
    material: document.getElementById("material").value,
    plateLength: parseFloat(document.getElementById("plateLength").value),
    plateWidth: parseFloat(document.getElementById("plateWidth").value),
    thickness: parseFloat(document.getElementById("thickness").value),
    flangeLength: parseFloat(document.getElementById("flangeLength").value),
    bendAngle: parseFloat(document.getElementById("bendAngle").value),
    bendRadius: parseFloat(document.getElementById("bendRadius").value),
    holeDia: parseFloat(document.getElementById("holeDia").value),
    holeX: parseFloat(document.getElementById("holeX").value),
    holeY: parseFloat(document.getElementById("holeY").value),
  };
}

function evaluate(p) {
  let kFactor, extrapolated, kFactorError = null;
  try {
    const r = lookupKFactor(kfactorTable, p.material, p.thickness);
    kFactor = r.kFactor;
    extrapolated = r.extrapolated;
  } catch (e) {
    kFactorError = e.message;
  }

  const problems = validateParams(p);
  const flatLength = kFactorError ? null : expectedFlatLength(
    p.plateLength, p.thickness, p.flangeLength, p.bendAngle, p.bendRadius, kFactor
  );

  return { p, kFactor, extrapolated, kFactorError, problems, flatLength };
}

function renderResult(evalResult) {
  const panel = document.getElementById("result");
  const { p, kFactor, extrapolated, kFactorError, problems, flatLength } = evalResult;
  const lines = [];

  if (kFactorError) {
    lines.push(`<div class="result-line bad">${escapeHtml(kFactorError)}</div>`);
  } else {
    lines.push(`<div class="result-line ok">K-factor (${p.material}, ${p.thickness}mm) = ${kFactor}${extrapolated ? " (extrapolated -- thickness exceeds this material's characterized range)" : ""}</div>`);
  }

  if (problems.length === 0 && !kFactorError) {
    lines.push(`<div class="result-line ok">Manufacturability check passed</div>`);
  } else {
    for (const prob of problems) lines.push(`<div class="result-line bad">${escapeHtml(prob)}</div>`);
  }

  if (flatLength !== null) {
    lines.push(`<div class="result-line ok">Expected flat pattern: ${flatLength.toFixed(3)} x ${p.plateWidth} mm</div>`);
  }

  const ok = problems.length === 0 && !kFactorError;
  panel.className = "result-panel " + (ok ? "pass" : "fail");
  panel.innerHTML = lines.join("");

  document.getElementById("add-row-btn").disabled = !ok;
  return ok;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function addRowToBatch(evalResult) {
  batch.push(evalResult);
  renderBatchTable();
}

function renderBatchTable() {
  const tbody = document.querySelector("#batch-table tbody");
  tbody.innerHTML = "";
  document.getElementById("batch-empty").style.display = batch.length ? "none" : "block";
  document.getElementById("download-btn").disabled = batch.filter(r => r.problems.length === 0 && !r.kFactorError).length === 0;

  batch.forEach((r, i) => {
    const tr = document.createElement("tr");
    const failed = r.problems.length > 0 || r.kFactorError;
    if (failed) tr.className = "row-fail";
    const p = r.p;
    tr.innerHTML = `
      <td>${escapeHtml(p.jobId)}</td>
      <td>${escapeHtml(p.material)}</td>
      <td>${p.plateLength}</td>
      <td>${p.plateWidth}</td>
      <td>${p.thickness}</td>
      <td>${p.flangeLength}</td>
      <td>${p.bendAngle}</td>
      <td>${p.bendRadius}</td>
      <td>${r.kFactorError ? "err" : r.kFactor}</td>
      <td><button class="row-remove" data-idx="${i}" title="Remove">&times;</button></td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".row-remove").forEach(btn => {
    btn.addEventListener("click", () => {
      batch.splice(parseInt(btn.dataset.idx, 10), 1);
      renderBatchTable();
    });
  });
}

function downloadBatchXlsx() {
  const rows = [COLUMN_ORDER];
  for (const r of batch) {
    if (r.problems.length > 0 || r.kFactorError) continue; // only export rows that pass
    const p = r.p;
    rows.push([
      p.jobId, p.material, p.plateLength, p.plateWidth, p.thickness, p.flangeLength,
      p.bendAngle, p.bendRadius, p.holeDia, p.holeX, p.holeY,
    ]);
  }
  const ws = XLSX.utils.aoa_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Parts");
  XLSX.writeFile(wb, "parts_batch.xlsx");
}

function previewUploadedFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const wb = XLSX.read(new Uint8Array(e.target.result), { type: "array" });
    const ws = wb.Sheets[wb.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json(ws, { defval: null });

    const container = document.getElementById("preview-wrap");
    let html = "<table><thead><tr><th>JobID</th><th>Material</th><th>Check</th></tr></thead><tbody>";
    for (const row of rows) {
      let checkHtml, rowClass = "";
      try {
        const p = {
          jobId: String(row.JobID ?? ""),
          material: String(row.Material ?? ""),
          plateLength: Number(row.PlateLength),
          plateWidth: Number(row.PlateWidth),
          thickness: Number(row.Thickness),
          flangeLength: Number(row.FlangeLength),
          bendAngle: Number(row.BendAngle),
          bendRadius: Number(row.BendRadius),
          holeDia: Number(row.HoleDia),
          holeX: Number(row.HoleX),
          holeY: Number(row.HoleY),
        };
        if (Object.values(p).some(v => typeof v === "number" && isNaN(v))) {
          throw new Error("missing or non-numeric column value");
        }
        const evalResult = evaluate(p);
        if (evalResult.kFactorError) throw new Error(evalResult.kFactorError);
        if (evalResult.problems.length > 0) throw new Error(evalResult.problems.join("; "));
        checkHtml = `OK -- flat ${evalResult.flatLength.toFixed(1)}mm, K=${evalResult.kFactor}`;
      } catch (e) {
        checkHtml = "FAIL -- " + escapeHtml(e.message);
        rowClass = "row-fail";
      }
      html += `<tr class="${rowClass}"><td>${escapeHtml(String(row.JobID ?? ""))}</td><td>${escapeHtml(String(row.Material ?? ""))}</td><td>${checkHtml}</td></tr>`;
    }
    html += "</tbody></table>";
    container.innerHTML = html;
  };
  reader.readAsArrayBuffer(file);
}

async function init() {
  try {
    kfactorTable = await loadKFactorTable();
  } catch (e) {
    document.getElementById("result").innerHTML =
      `<div class="result-line bad">Could not load K-factor table: ${escapeHtml(e.message)}. ` +
      `This page must be served over HTTP (e.g. GitHub Pages), not opened as a local file://.</div>`;
    return;
  }

  const select = document.getElementById("material");
  Object.keys(kfactorTable.materials).sort().forEach(name => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
  if (kfactorTable.default_material) select.value = kfactorTable.default_material;

  document.getElementById("part-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const p = readForm();
    const result = evaluate(p);
    renderResult(result);
    window._lastEval = result;
  });

  document.getElementById("add-row-btn").addEventListener("click", () => {
    if (window._lastEval) addRowToBatch(window._lastEval);
  });

  document.getElementById("download-btn").addEventListener("click", downloadBatchXlsx);
  document.getElementById("clear-btn").addEventListener("click", () => {
    batch = [];
    renderBatchTable();
  });

  document.getElementById("file-input").addEventListener("change", (e) => {
    if (e.target.files.length) previewUploadedFile(e.target.files[0]);
  });

  renderBatchTable();
}

init();
