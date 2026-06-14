"use strict";

const PARAMS = [
  ["exposure", "Exposición", -2, 2, 0.05],
  ["temp", "Temperatura", -50, 50, 1],
  ["tint", "Tinte", -50, 50, 1],
  ["contrast", "Contraste", -100, 100, 1],
  ["highlights", "Luces", -100, 100, 1],
  ["shadows", "Sombras", -100, 100, 1],
  ["whites", "Blancos", -100, 100, 1],
  ["blacks", "Negros", -100, 100, 1],
  ["vibrance", "Intensidad", -100, 100, 1],
  ["saturation", "Saturación", -100, 100, 1],
  ["vignette", "Viñeta", 0, 0.6, 0.02],
  ["grain", "Grano", 0, 0.1, 0.005],
  ["sharpen", "Nitidez", 0, 1, 0.05],
];

const S = {
  kind: "photo", folder: "", photos: [], videos: [], current: null,
  params: {}, presets: [], presetFile: null,
  wm: { type: "none", logo: null, text: "MUNDIAL", scale: 0.16,
        opacity: 0.85, position: "br", xy: null },
  photoOverrides: {}, videoTrims: {}, vinfo: null,
};

const $ = (id) => document.getElementById(id);
const hexToRgb = (h) => {
  const n = parseInt(h.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
};
const rgbToHex = (a) => "#" + a.map(v =>
  Math.round(v * 255).toString(16).padStart(2, "0")).join("");

// ---------------------------------------------------------------- init
function buildSliders() {
  const box = $("sliders");
  box.innerHTML = "";
  for (const [k, label, mn, mx, st] of PARAMS) {
    const d = document.createElement("div");
    d.className = "slider";
    d.innerHTML = `<div class="lbl"><span>${label}</span><b id="v_${k}">0</b></div>
      <input type="range" id="p_${k}" min="${mn}" max="${mx}" step="${st}" value="0">`;
    box.appendChild(d);
    $(`p_${k}`).addEventListener("input", () => {
      $(`v_${k}`).textContent = $(`p_${k}`).value;
      gather(); render();
    });
  }
}

function setSliders(p) {
  for (const [k] of PARAMS) {
    const v = p[k] ?? 0;
    if ($(`p_${k}`)) { $(`p_${k}`).value = v; $(`v_${k}`).textContent = v; }
  }
  $("auto_white_balance").checked = !!p.auto_white_balance;
  $("auto_exposure").checked = !!p.auto_exposure;
  if (p.split_shadows) $("split_shadows").value = rgbToHex(p.split_shadows);
  if (p.split_highlights) $("split_highlights").value = rgbToHex(p.split_highlights);
  $("split_shadows_strength").value = p.split_shadows_strength ?? 0;
  $("split_highlights_strength").value = p.split_highlights_strength ?? 0;
}

function gather() {
  const p = { ...S.params };
  for (const [k] of PARAMS) p[k] = parseFloat($(`p_${k}`).value);
  p.auto_white_balance = $("auto_white_balance").checked;
  p.auto_exposure = $("auto_exposure").checked;
  p.split_shadows = hexToRgb($("split_shadows").value);
  p.split_highlights = hexToRgb($("split_highlights").value);
  p.split_shadows_strength = parseFloat($("split_shadows_strength").value);
  p.split_highlights_strength = parseFloat($("split_highlights_strength").value);
  S.params = p;
}

// ---------------------------------------------------------------- presets
async function loadPresets() {
  S.presets = await (await fetch("/api/presets")).json();
  const box = $("presets");
  box.innerHTML = "";
  S.presets.forEach((pr) => {
    const b = document.createElement("button");
    b.className = "preset";
    b.innerHTML = `<b>${pr.name}</b><small>${pr.description || ""}</small>`;
    b.onclick = () => {
      S.params = { ...pr.params };
      S.presetFile = pr.file;
      setSliders(S.params);
      document.querySelectorAll(".preset").forEach(e => e.classList.remove("sel"));
      b.classList.add("sel");
      gather(); render();
    };
    box.appendChild(b);
  });
  if (S.presets.length && !S.presetFile) {
    S.params = { ...S.presets[0].params };
    S.presetFile = S.presets[0].file;
    setSliders(S.params);
    box.firstChild.classList.add("sel");
    gather();
  }
}

// ---------------------------------------------------------------- files
async function openFolder() {
  const folder = $("folder").value.trim();
  const r = await fetch("/api/open", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder })
  });
  if (!r.ok) { alert((await r.json()).error); return; }
  const d = await r.json();
  S.folder = d.folder; S.photos = d.photos; S.videos = d.videos;
  renderFileList();
}

function currentList() { return S.kind === "photo" ? S.photos : S.videos; }

function renderFileList() {
  const box = $("filelist");
  const list = currentList();
  box.innerHTML = "";
  if (!list.length) { box.innerHTML = `<div class="hint">No hay ${S.kind === "photo" ? "fotos" : "vídeos"} en la carpeta.</div>`; return; }
  list.forEach((p) => {
    const name = p.split(/[\\/]/).pop();
    const t = document.createElement("div");
    t.className = "thumb" + (p === S.current ? " sel" : "");
    const has = S.kind === "photo" ? S.photoOverrides[p] : S.videoTrims[p];
    t.innerHTML = `<img loading="lazy" src="/api/thumb?path=${encodeURIComponent(p)}">
      <div class="ov">${name}</div>${has ? '<div class="badge">✓</div>' : ""}`;
    t.onclick = () => selectFile(p);
    box.appendChild(t);
  });
  if (!S.current && list.length) selectFile(list[0]);
}

async function selectFile(p) {
  S.current = p;
  renderFileList();
  if (S.kind === "video") {
    $("videobar").classList.remove("hidden");
    await loadVideoInfo(p);
  } else {
    $("videobar").classList.add("hidden");
    if (S.photoOverrides[p]) { S.params = { ...S.photoOverrides[p] }; setSliders(S.params); }
  }
  render();
}

async function loadVideoInfo(p) {
  S.vinfo = null;
  $("vscore").textContent = "…";
  const info = await (await fetch("/api/video_info?path=" + encodeURIComponent(p))).json();
  S.vinfo = info;
  $("vtime").max = info.duration || 1;
  $("vtime").value = Math.min(0.2 * (info.duration || 1), info.duration || 0);
  $("vtimelbl").textContent = (+$("vtime").value).toFixed(1) + "s";
  const seg = S.videoTrims[p] || info.best_segment || [0, info.duration];
  $("trimStart").value = seg[0]; $("trimEnd").value = seg[1];
  $("vscore").textContent = info.score != null ? "nota " + info.score : "";
}

// ---------------------------------------------------------------- render
let renderTimer = null, renderBusy = false, renderQueued = false;
function render() {
  clearTimeout(renderTimer);
  renderTimer = setTimeout(doRender, 90);
}
async function doRender() {
  if (!S.current) return;
  if (renderBusy) { renderQueued = true; return; }
  renderBusy = true;
  $("loading").classList.remove("hidden");
  const body = {
    path: S.current, kind: S.kind, params: S.params,
    watermark: { type: "none" },                 // la marca se dibuja en cliente
    time: S.kind === "video" ? parseFloat($("vtime").value || 0) : 0,
    aspect: S.kind === "video" ? $("aspect").value : "keep",
  };
  try {
    const r = await fetch("/api/render", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (r.ok) {
      const url = URL.createObjectURL(await r.blob());
      const img = $("preview");
      img.onload = () => { URL.revokeObjectURL(url); positionWatermark(); };
      img.src = url;
    }
  } finally {
    renderBusy = false;
    $("loading").classList.add("hidden");
    if (renderQueued) { renderQueued = false; doRender(); }
  }
}

// ---------------------------------------------------------------- watermark
function imgRect() {
  const img = $("preview"), stage = $("stage");
  const a = img.getBoundingClientRect(), b = stage.getBoundingClientRect();
  return { x: a.left - b.left, y: a.top - b.top, w: a.width, h: a.height };
}
function updateWatermark() {
  const el = $("wm");
  if (S.wm.type === "none" || !S.current) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  const r = imgRect();
  if (S.wm.type === "logo") {
    if (!S.wm.logo) { el.classList.add("hidden"); return; }
    el.className = "wm";
    el.innerHTML = `<img src="/api/file?path=${encodeURIComponent(S.wm.logo)}">`;
    el.style.width = (S.wm.scale * r.w) + "px";
    el.style.opacity = S.wm.opacity;
  } else {
    el.className = "wm text";
    el.innerHTML = "";
    el.textContent = S.wm.text || "MUNDIAL";
    el.style.width = "auto";
    el.style.fontSize = (S.wm.scale * r.h) + "px";
    el.style.opacity = S.wm.opacity;
  }
  positionWatermark();
}
function positionWatermark() {
  const el = $("wm");
  if (el.classList.contains("hidden")) return;
  const r = imgRect();
  const m = 0.04 * r.w;
  const ew = el.offsetWidth, eh = el.offsetHeight;
  let x, y;
  if (S.wm.xy) { x = S.wm.xy[0] * r.w; y = S.wm.xy[1] * r.h; }
  else {
    const pos = S.wm.position;
    x = pos.includes("l") ? m : (pos === "center" ? (r.w - ew) / 2 : r.w - ew - m);
    y = pos.includes("t") ? m : (pos === "center" ? (r.h - eh) / 2 : r.h - eh - m);
  }
  el.style.left = (r.x + x) + "px";
  el.style.top = (r.y + y) + "px";
}
function dragWatermark() {
  const el = $("wm");
  let sx, sy, ox, oy;
  el.addEventListener("pointerdown", (e) => {
    if (S.wm.type === "none") return;
    el.setPointerCapture(e.pointerId);
    sx = e.clientX; sy = e.clientY;
    ox = el.offsetLeft; oy = el.offsetTop;
    const move = (ev) => {
      const r = imgRect();
      let nx = ox + (ev.clientX - sx), ny = oy + (ev.clientY - sy);
      nx = Math.max(r.x, Math.min(nx, r.x + r.w - el.offsetWidth));
      ny = Math.max(r.y, Math.min(ny, r.y + r.h - el.offsetHeight));
      el.style.left = nx + "px"; el.style.top = ny + "px";
      S.wm.xy = [(nx - r.x) / r.w, (ny - r.y) / r.h];
    };
    const up = (ev) => {
      el.releasePointerCapture(e.pointerId);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  });
}

function exportWatermark() {
  if (S.wm.type === "none") return { type: "none" };
  return { ...S.wm };
}

// ---------------------------------------------------------------- events
function wireEvents() {
  $("openBtn").onclick = openFolder;
  $("folder").addEventListener("keydown", e => { if (e.key === "Enter") openFolder(); });

  document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    S.kind = t.dataset.kind; S.current = null;
    renderFileList();
  });

  $("auto_white_balance").onchange = () => { gather(); render(); };
  $("auto_exposure").onchange = () => { gather(); render(); };
  ["split_shadows", "split_highlights", "split_shadows_strength",
    "split_highlights_strength"].forEach(id =>
      $(id).addEventListener("input", () => { gather(); render(); }));

  $("resetBtn").onclick = () => {
    if (S.presetFile) {
      const pr = S.presets.find(x => x.file === S.presetFile);
      if (pr) { S.params = { ...pr.params }; setSliders(S.params); gather(); render(); }
    }
  };

  // watermark
  document.querySelectorAll("input[name=wmtype]").forEach(r => r.onchange = () => {
    S.wm.type = document.querySelector("input[name=wmtype]:checked").value;
    $("wmLogoRow").classList.toggle("hidden", S.wm.type !== "logo");
    $("wmTextRow").classList.toggle("hidden", S.wm.type !== "text");
    $("wmOpts").classList.toggle("hidden", S.wm.type === "none");
    updateWatermark();
  });
  $("logoFile").onchange = async (e) => {
    const fd = new FormData(); fd.append("file", e.target.files[0]);
    const d = await (await fetch("/api/upload?kind=logo", { method: "POST", body: fd })).json();
    S.wm.logo = d.path; updateWatermark();
  };
  $("wmText").oninput = () => { S.wm.text = $("wmText").value; updateWatermark(); };
  $("wmScale").oninput = () => { S.wm.scale = +$("wmScale").value; updateWatermark(); };
  $("wmOpacity").oninput = () => { S.wm.opacity = +$("wmOpacity").value; updateWatermark(); };
  $("wmPos").onchange = () => { S.wm.position = $("wmPos").value; S.wm.xy = null; updateWatermark(); };

  // video controls
  $("vtime").oninput = () => { $("vtimelbl").textContent = (+$("vtime").value).toFixed(1) + "s"; render(); };
  $("aspect").onchange = () => render();
  $("bestSeg").onclick = () => {
    if (S.vinfo && S.vinfo.best_segment) {
      $("trimStart").value = S.vinfo.best_segment[0];
      $("trimEnd").value = S.vinfo.best_segment[1];
    }
  };

  // overrides
  $("saveOverride").onclick = () => {
    if (!S.current) return;
    if (S.kind === "photo") S.photoOverrides[S.current] = { ...S.params };
    else S.videoTrims[S.current] = [+$("trimStart").value, +$("trimEnd").value];
    renderFileList();
  };
  $("clearOverride").onclick = () => {
    if (!S.current) return;
    delete S.photoOverrides[S.current]; delete S.videoTrims[S.current];
    renderFileList();
  };

  // presets
  $("savePreset").onclick = async () => {
    gather();
    const name = $("presetName").value.trim() || "Mi preset";
    await fetch("/api/save_preset", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, params: S.params })
    });
    await loadPresets();
  };
  $("exportLut").onclick = () => alert("Para exportar un LUT .cube usa:\n\npython make_lut.py --preset <preset.json> -o assets/look.cube\n\n(o guarda primero el preset y ejecútalo)");

  // references
  $("refUpload").onclick = () => $("refFile").click();
  $("refFile").onchange = async (e) => {
    const fd = new FormData(); fd.append("file", e.target.files[0]);
    const d = await (await fetch("/api/upload?kind=reference", { method: "POST", body: fd })).json();
    const img = document.createElement("img");
    img.src = "/api/file?path=" + encodeURIComponent(d.path);
    $("refstrip").appendChild(img);
  };

  // export modal
  $("exportBtn").onclick = () => {
    $("exportPhotoOpts").classList.toggle("hidden", S.kind !== "photo");
    $("exportModal").classList.remove("hidden");
  };
  $("exportCancel").onclick = () => $("exportModal").classList.add("hidden");
  $("exportRun").onclick = runExport;

  window.addEventListener("resize", () => positionWatermark());
}

// ---------------------------------------------------------------- export
async function runExport() {
  const files = currentList();
  if (!files.length) { alert("No hay archivos en esta pestaña."); return; }
  gather();
  const overrides = S.kind === "photo" ? S.photoOverrides
    : Object.fromEntries(Object.entries(S.videoTrims).map(([k, v]) => [k, { trim: v }]));
  const body = {
    kind: S.kind, folder: S.folder, output: $("outFolder").value.trim(),
    files, params: S.params, overrides, watermark: exportWatermark(),
    aspect: $("aspect").value, fit: $("fit").value,
    max_size: +$("maxSize").value, quality: +$("quality").value,
  };
  const r = await fetch("/api/export", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!r.ok) { alert((await r.json()).error); return; }
  $("exportProgress").classList.remove("hidden");
  poll();
}
async function poll() {
  const st = await (await fetch("/api/export_status")).json();
  const pct = st.total ? Math.round(100 * st.done / st.total) : 0;
  $("bar").style.width = pct + "%";
  $("exportMsg").textContent = `${st.done}/${st.total} — ${st.msg}`;
  if (st.running) setTimeout(poll, 600);
}

// ---------------------------------------------------------------- go
buildSliders();
wireEvents();
dragWatermark();
loadPresets();
